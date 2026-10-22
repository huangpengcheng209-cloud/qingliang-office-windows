"""Prepare locked Boost/ICU sources and build ICU + UnicodeConverter without the old Office baseline."""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from build_windows import discover_vs, execute, msvc_environment
from verify_sources import ROOT, safe_relative

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def checked_member(name):
    return safe_relative(name.replace('\\', '/'))

def verify_dependencies():
    lock = json.loads((ROOT / 'dependencies.lock.json').read_text('utf-8'))
    for name, version in [('boost', '1.72.0'), ('icu', '74.2')]:
        row = lock[name]
        if row['version'] != version or not re.fullmatch(r'[a-f0-9]{64}', row['sha256']):
            raise ValueError('Unsupported dependency version or hash')
        checked_member(row['archive'])
    core = lock['unicode_converter']
    upstream = json.loads((ROOT / 'upstream.lock.json').read_text('utf-8'))
    expected = next(row['revision'] for row in upstream if row['repository'] == 'core')
    if core['repository'] != 'https://github.com/ONLYOFFICE/core' or core['revision'] != expected:
        raise ValueError('UnicodeConverter upstream must match the main source lock')
    for row in core['files']:
        checked_member(row['file'])
        if not re.fullmatch(r'[a-f0-9]{64}', row['sha256']):
            raise ValueError('Invalid pinned core file hash')
    for row in core.get('patches', []):
        for key in ['file', 'patch', 'modified_source']:
            checked_member(row[key])
        if sha(ROOT / row['patch']) != row['patch_sha256'] or sha(ROOT / row['modified_source']) != row['result_sha256']:
            raise ValueError('Dependency patch/modified source hash mismatch')
        original = next(x for x in core['files'] if x['file'] == row['file'])
        if original['sha256'] != row['base_sha256']:
            raise ValueError('Dependency patch base differs from pinned core file')
    return lock

def acquire_archive(row, work, external_cache):
    local = external_cache / row['archive'] if external_cache else None
    target = local if local and local.is_file() else work / 'archives' / row['archive']
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_suffix(target.suffix + '.part')
        request = urllib.request.Request(row['url'], headers={'User-Agent': 'qingliang-dependency-source-build'})
        with urllib.request.urlopen(request, timeout=120) as response, part.open('wb') as output:
            shutil.copyfileobj(response, output, 1024 * 1024)
        if sha(part) != row['sha256']:
            raise ValueError('Downloaded archive hash mismatch: ' + row['archive'])
        part.replace(target)
    if sha(target) != row['sha256']:
        raise ValueError('Archive hash mismatch; existing input preserved: ' + row['archive'])
    return target

def extract_source(row, archive, destination, seven_zip=None):
    marker = destination / '.source-archive.json'
    if marker.exists():
        if json.loads(marker.read_text('utf-8'))['sha256'] != row['sha256']:
            raise ValueError('Different source identity in extraction directory')
        return destination / row['root']
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Incomplete or unknown extraction directory; inspect before retrying')
    destination.mkdir(parents=True, exist_ok=True)
    if row['format'] == 'zip':
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                checked_member(member.filename)
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError('Archive symbolic link not permitted')
            source.extractall(destination)
    elif row['format'] == '7z':
        seven_zip = seven_zip or shutil.which('7z')
        if not seven_zip:
            raise ValueError('7-Zip is required for the locked Boost source archive')
        listing = subprocess.check_output([str(seven_zip), 'l', '-slt', '-ba', '-sccUTF-8', str(archive)]).decode('utf-8')
        for line in listing.splitlines():
            if line.startswith('Path = '):
                checked_member(line.removeprefix('Path = '))
            if line.startswith(('Symbolic Link = ', 'Hard Link = ')):
                raise ValueError('Archive links not permitted')
        log = destination / 'extraction.log'
        with log.open('wb') as output:
            subprocess.run([str(seven_zip), 'x', '-y', '-o' + str(destination), str(archive)],
                           check=True, stdout=output, stderr=output)
    else:
        raise ValueError('Unsupported source archive format')
    marker.write_text(json.dumps({'url': row['url'], 'sha256': row['sha256']}), 'utf-8')
    return destination / row['root']

def prepare(work, archive_cache=None):
    lock = verify_dependencies()
    roots = {}
    for name in ('boost', 'icu'):
        row = lock[name]
        archive = acquire_archive(row, work, archive_cache)
        roots[name] = extract_source(row, archive, work / 'sources' / name)
        print(f'{name} {row["version"]}: archive verified, source prepared', flush=True)
    if '#define BOOST_LIB_VERSION "1_72"' not in (roots['boost'] / 'boost/version.hpp').read_text('utf-8'):
        raise ValueError('Unexpected Boost source version')
    icu_version = (roots['icu'] / 'source/common/unicode/uvernum.h').read_text('utf-8')
    if not re.search(r'#define\s+U_ICU_VERSION_MAJOR_NUM\s+74\b', icu_version) or not re.search(r'#define\s+U_ICU_VERSION_MINOR_NUM\s+2\b', icu_version):
        raise ValueError('Unexpected ICU source version')
    core = work / 'sources/core'
    entry = lock['unicode_converter']
    overlays = {row['file']: row for row in entry.get('patches', [])}
    for row in entry['files']:
        checked_member(row['file'])
        target = core / row['file']
        if not target.exists():
            url = entry['repository'].replace('https://github.com/', 'https://raw.githubusercontent.com/') + '/' + entry['revision'] + '/' + row['file']
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('Pinned core download hash mismatch')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        allowed = {row['sha256']}
        if row['file'] in overlays:
            allowed.add(overlays[row['file']]['result_sha256'])
        if sha(target) not in allowed:
            raise ValueError('Unknown modification of prepared core source; preserved')
    for overlay in overlays.values():
        target = core / overlay['file']
        patch = ROOT / overlay['patch']
        published_source = ROOT / overlay['modified_source']
        if sha(patch) != overlay['patch_sha256'] or sha(published_source) != overlay['result_sha256']:
            raise ValueError('Published dependency patch/source hash mismatch')
        if sha(target) == overlay['base_sha256']:
            if not (core / '.git').exists():
                subprocess.run(['git', 'init', '--quiet', str(core)], check=True)
            command = ['git', '-c', 'core.autocrlf=false', '-C', str(core), 'apply', '--whitespace=nowarn']
            subprocess.run(command + ['--check', str(patch)], check=True)
            subprocess.run(command + [str(patch)], check=True)
        if sha(target) != overlay['result_sha256']:
            raise ValueError('Applied dependency patch result differs')
    roots['core'] = core
    report = {'archives': {name: {'version': lock[name]['version'], 'url': lock[name]['url'], 'sha256': lock[name]['sha256']} for name in ('boost', 'icu')},
              'unicode_converter_revision': entry['revision'], 'unicode_converter_files': entry['files'],
              'unicode_converter_patches': entry.get('patches', []),
              'source_roots': {name: str(path) for name, path in roots.items()}, 'old_office_baseline_used': False}
    (work / 'source-preparation-report.json').write_text(json.dumps(report, indent=2), 'utf-8')
    return roots

def build(work, roots, vs_root=None):
    if os.name != 'nt':
        raise ValueError('Dependency compilation requires Windows')
    vcvars = discover_vs(vs_root)
    env = msvc_environment(vcvars, work)
    msbuild = vcvars.parents[3] / 'MSBuild/Current/Bin/MSBuild.exe'
    if not msbuild.is_file():
        raise ValueError('MSBuild not found in selected Visual Studio installation')
    icu = roots['icu']
    solution = icu / 'source/allinone/allinone.sln'
    log = work / 'dependency-build.log'
    # One incremental release build; genccode's solution dependencies include the needed ICU libraries/tools.
    execute([str(msbuild), str(solution), '/nologo', '/m:2', '/t:genccode',
             '/p:Configuration=Release', '/p:Platform=x64', '/p:SkipUWP=true', '/v:minimal'], work, env, log)
    bin64 = icu / 'bin64'
    lib64 = icu / 'lib64'
    data = icu / 'source/data/in/icudt74l.dat'
    data_obj_dir = work / 'data-object'
    data_obj_dir.mkdir(exist_ok=True)
    execute([str(bin64 / 'genccode.exe'), '-o', '-e', 'icudt74', '-d', str(data_obj_dir), str(data)], work, env, log)
    objects = list(data_obj_dir.glob('*.obj'))
    if len(objects) != 1:
        raise ValueError('Expected one ICU data object')
    linker = shutil.which('link.exe', path=env['PATH'])
    # Build the data DLL from the verified release's packaged Unicode data, replacing only our own build's stub DLL.
    execute([linker, '/nologo', '/dll', '/noentry', '/machine:x64', '/export:icudt74_dat',
             '/out:' + str(bin64 / 'icudt74.dll'), '/implib:' + str(lib64 / 'icudt.lib'), str(objects[0])], work, env, log)
    output = work / 'bin'
    output.mkdir(exist_ok=True)
    compiler = shutil.which('cl.exe', path=env['PATH'])
    core = roots['core']
    source = core / 'UnicodeConverter/UnicodeConverter.cpp'
    common = ['/nologo', '/std:c++17', '/EHsc', '/O2', '/MD', '/utf-8', '/DNOMINMAX', '/D_CRT_SECURE_NO_WARNINGS']
    execute([compiler, *common, '/LD', '/DUNICODECONVERTER_USE_DYNAMIC_LIBRARY',
             '/I' + str(icu / 'source/common'), str(source), '/Fo' + str(work / 'UnicodeConverter.obj'),
             '/link', '/LIBPATH:' + str(lib64), 'icuuc.lib', '/OUT:' + str(output / 'UnicodeConverter.dll'),
             '/IMPLIB:' + str(output / 'UnicodeConverter.lib')], work, env, log)
    for name in ('icuuc74.dll', 'icudt74.dll'):
        shutil.copyfile(bin64 / name, output / name)
    test = ROOT / 'tests/native/unicode_converter_test.cpp'
    exe = output / 'unicode-converter-test.exe'
    execute([compiler, *common, '/I' + str(core / 'UnicodeConverter'), '/I' + str(roots['boost']),
             '/DBOOST_ALL_NO_LIB', str(test), '/Fo' + str(work / 'unicode-converter-test.obj'), '/Fe' + str(exe),
             '/link', '/LIBPATH:' + str(output), 'UnicodeConverter.lib'], work, env, log)
    result_path = work / 'unicode-test-result.json'
    if result_path.exists():
        result_path.unlink()
    execute([str(exe), str(result_path)], output, env, log)
    result = json.loads(result_path.read_text('utf-8'))
    if result.get('failed') != 0 or result.get('passed') != 14:
        raise RuntimeError('Unicode/Boost native tests did not all pass')
    artifacts = {name: {'sha256': sha(output / name), 'bytes': (output / name).stat().st_size}
                 for name in ('UnicodeConverter.dll', 'UnicodeConverter.lib', 'icuuc74.dll', 'icudt74.dll', 'unicode-converter-test.exe')}
    lock = verify_dependencies()
    report = {'icu_version': '74.2', 'boost_version': '1.72.0', 'native_tests': result,
              'unicode_converter_source_sha256': sha(source),
              'unicode_converter_patches': lock['unicode_converter'].get('patches', []),
              'artifacts': artifacts, 'icu_data_file_sha256': sha(data), 'icu_data_origin': 'packaged data in locked ICU source release',
              'old_office_baseline_used': False, 'full_office_built': False, 'application_gui_tested': False}
    (work / 'dependency-build-report.json').write_text(json.dumps(report, indent=2), 'utf-8')
    print(json.dumps({'built_icu_and_unicode_converter': True, 'native_tests': result, 'old_office_baseline_used': False, 'full_office_built': False}), flush=True)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'prepare', 'build'))
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--archive-cache', type=Path, help='Optional read-only directory containing already downloaded source archives')
    parser.add_argument('--vs-root', type=Path)
    args = parser.parse_args()
    if args.command == 'verify':
        lock = verify_dependencies()
        print(json.dumps({'ok': True, 'locked_archives': 2, 'core_files': len(lock['unicode_converter']['files']),
                          'patches': len(lock['unicode_converter'].get('patches', []))}))
        return
    if not args.work_dir:
        parser.error('--work-dir is required for prepare/build')
    if args.command == 'build' and os.name != 'nt':
        parser.error('The dependency build command requires Windows; no downloads performed')
    work = args.work_dir.resolve()
    if work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise ValueError('Select a dependency work directory outside the published repository')
    marker = work / '.qingliang-dependency-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():
        raise ValueError('Unknown nonempty dependency work directory; refusing to overwrite')
    work.mkdir(parents=True, exist_ok=True)
    marker.write_text('One stable dependency source/build workspace.\n', 'utf-8')
    lockfile = work / '.build.lock'
    fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        roots = prepare(work, args.archive_cache)
        if args.command == 'build':
            build(work, roots, args.vs_root)
    finally:
        os.close(fd)
        lockfile.unlink()

if __name__ == '__main__':
    main()
