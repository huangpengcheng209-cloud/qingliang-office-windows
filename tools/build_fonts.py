"""Build pinned FreeType, Brotli decoder and patched HarfBuzz; check upstream shaping goldens."""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from build_dependencies import acquire_archive, sha
from build_kernel import prepare_kernel_sources, response_file
from build_windows import discover_vs, execute, msvc_environment
from verify_sources import ROOT, safe_relative


def verify_font_inputs():
    lock = json.loads((ROOT / 'fonts.inputs.lock.json').read_text('utf-8'))
    upstream = json.loads((ROOT / 'upstream.lock.json').read_text('utf-8'))
    expected = next(row['revision'] for row in upstream if row['repository'] == 'core')
    if lock['repository'] != 'https://github.com/ONLYOFFICE/core' or lock['revision'] != expected:
        raise ValueError('Font core identity differs from pinned upstream')
    indexed = set()
    for row in lock['files']:
        safe_relative(row['file'])
        if row['file'] in indexed or not re.fullmatch('[a-f0-9]{64}', row['sha256']):
            raise ValueError('Duplicate font input or invalid source hash')
        indexed.add(row['file'])
    for name, archive in lock['archives'].items():
        safe_relative(archive['destination'])
        safe_relative(archive['archive'])
        if not re.fullmatch('[a-f0-9]{64}', archive['sha256']):
            raise ValueError('Invalid font archive hash')
        expected_repo = 'https://github.com/' + ('harfbuzz/harfbuzz' if name == 'harfbuzz' else 'google/brotli')
        if archive['repository'] != expected_repo or archive['url'] != expected_repo.replace('github.com/', 'codeload.github.com/') + '/zip/' + archive['revision']:
            raise ValueError('Unexpected font archive origin')
        if name == 'brotli' and archive['revision'] != next(r['revision'] for r in upstream if r['repository'] == 'brotli'):
            raise ValueError('Brotli revision differs from main source lock')
        names = set()
        for row in archive['files']:
            safe_relative(row['file'])
            if row['file'] in names or not re.fullmatch('[a-f0-9]{64}', row['sha256']):
                raise ValueError('Duplicate archive input or invalid source hash')
            names.add(row['file'])
            indexed.add(archive['destination'] + '/' + row['file'])
        for overlay in archive.get('patches', []):
            for key in ('file', 'patch', 'modified_source'):
                safe_relative(overlay[key])
            if sha(ROOT / overlay['patch']) != overlay['patch_sha256'] or sha(ROOT / overlay['modified_source']) != overlay['result_sha256']:
                raise ValueError('Font adaptation patch/source hash mismatch')
            if next(r['sha256'] for r in archive['files'] if r['file'] == overlay['file']) != overlay['base_sha256']:
                raise ValueError('Font adaptation base differs from archive input')
    for name, count in [('freetype', 51), ('brotli', 10), ('harfbuzz', 75)]:
        profile = lock['profiles'][name]
        units = profile['sources']
        if len(units) != count or len({Path(p).stem.lower() for p in units}) != count:
            raise ValueError('Unexpected font compile units or object name collision')
        if not set(units).issubset(indexed):
            raise ValueError('Unpinned font compile unit')
        for directory in profile['include_directories']:
            safe_relative(directory)
    generated = lock['generated_project']
    for key in ('file', 'source'):
        safe_relative(generated[key])
    if sha(ROOT / generated['source']) != generated['sha256']:
        raise ValueError('Generated font project hash mismatch')
    for row in lock['freetype_license_supplements']:
        safe_relative(row['file'])
        if sha(ROOT / row['file']) != row['sha256']:
            raise ValueError('Supplemental FreeType license hash mismatch')
    hb_files = {r['file'] for r in lock['archives']['harfbuzz']['files']}
    if len(lock['golden_cases']) != 20:
        raise ValueError('Expected 20 pinned upstream shaping cases')
    for case in lock['golden_cases']:
        if not {case['font'], case['test']}.issubset(hb_files):
            raise ValueError('Unpinned font test fixture')
    return lock


def extract_selected(archive, row, core):
    """Verify all ZIP paths first; skip only an explicitly identified documentation symlink.

    Materialize just locked inputs in the eventual upstream directory layout. No filesystem links
    are created. Unknown existing bytes are preserved, including locally edited source files.
    """
    destination = core / row['destination']
    if not destination.resolve().is_relative_to(core.resolve()):
        raise ValueError('Font extraction destination escapes source workspace')
    overlays = {p['file']: p for p in row.get('patches', [])}
    with zipfile.ZipFile(archive) as source:
        members = {}
        skipped = {}
        prefix = row['root'] + '/'
        for info in source.infolist():
            safe_relative(info.filename)
            if not info.filename.startswith(prefix):
                raise ValueError('Unexpected font archive root')
            name = info.filename[len(prefix):]
            if not name:
                continue
            safe_relative(name)
            if name.casefold() in members:
                raise ValueError('Duplicate or case-colliding font archive member')
            members[name.casefold()] = info
            if stat.S_ISLNK(info.external_attr >> 16):
                target = source.read(info).decode('utf-8')
                if row.get('skipped_symlinks', {}).get(name) != target:
                    raise ValueError('Unexpected font archive symbolic link')
                skipped[name] = target
        if skipped != row.get('skipped_symlinks', {}):
            raise ValueError('Font archive documentation link identity differs')
        # Preflight every target before writing anything.
        pending = []
        for entry in row['files']:
            name = entry['file']
            safe_relative(name)
            target = destination / name
            if not target.resolve().is_relative_to(core.resolve()):
                raise ValueError('Font extraction target escapes source workspace')
            info = members.get(name.casefold())
            if info is None or info.is_dir() or name in skipped:
                raise ValueError('Locked font input absent or not a regular file')
            data = source.read(info)
            if hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise ValueError('Font archive source hash mismatch')
            allowed = {entry['sha256'], overlays.get(name, {}).get('result_sha256')}
            if target.exists() and sha(target) not in allowed:
                raise ValueError('Unknown existing font source modification; preserved: ' + name)
            pending.append((target, data))
        for target, data in pending:
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
    return destination


def prepare_fonts(work, lock, archive_cache=None, source_cache=None):
    core = prepare_kernel_sources(lock, work, source_cache)
    for name, row in lock['archives'].items():
        archive = acquire_archive(row, work, archive_cache)
        destination = extract_selected(archive, row, core)
        for overlay in row.get('patches', []):
            target = destination / overlay['file']
            if sha(target) == overlay['base_sha256']:
                command = ['git', '-c', 'core.autocrlf=false', '-C', str(core), 'apply', '--whitespace=nowarn']
                if not (core / '.git').exists():
                    subprocess.run(['git', 'init', '--quiet', str(core)], check=True)
                subprocess.run(command + ['--check', str(ROOT / overlay['patch'])], check=True)
                subprocess.run(command + [str(ROOT / overlay['patch'])], check=True)
            if sha(target) != overlay['result_sha256']:
                raise ValueError('Prepared font adaptation hash mismatch')
        print(f'{name}: {len(row["files"])} locked source/header/license/fixture inputs prepared', flush=True)
    generated = lock['generated_project']
    target = core / generated['file']
    if not target.resolve().is_relative_to(core.resolve()):
        raise ValueError('Generated font project escapes source workspace')
    if target.exists() and sha(target) != generated['sha256']:
        raise ValueError('Unknown generated font project modification; preserved')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((ROOT / generated['source']).read_bytes())
    return core


def build_fonts(work, core, lock, vs_root=None):
    env = msvc_environment(discover_vs(vs_root, version_range='[17.0,18.0)'), work)
    env['VSLANG'] = '1033'
    compiler = shutil.which('cl.exe', path=env['PATH'])
    librarian = shutil.which('lib.exe', path=env['PATH'])
    folder = work / 'fonts-build'
    folder.mkdir(exist_ok=True)
    libraries = work / 'lib'
    libraries.mkdir(exist_ok=True)
    (work / 'bin').mkdir(exist_ok=True)
    log = work / 'fonts-build.log'
    report_path = work / 'fonts-build-report.json'
    if report_path.exists():
        report_path.unlink()
    for name in ('brotli', 'freetype', 'harfbuzz'):
        profile = lock['profiles'][name]
        objects = folder / name
        objects.mkdir(exist_ok=True)
        flags = ['/nologo', '/c', '/O2', '/MD', '/EHsc', '/MP4', '/bigobj', '/utf-8',
                 '/D_CRT_SECURE_NO_WARNINGS', '/DNOMINMAX', '/DNDEBUG', '/Fo' + str(objects) + os.sep]
        flags += ['/D' + value for value in profile['defines']]
        flags += ['/I' + str(core / value) for value in profile['include_directories']]
        if name == 'harfbuzz':
            flags += ['/std:c++17']
        compile_rsp = folder / (name + '-compile.rsp')
        response_file(compile_rsp, flags + [core / source for source in profile['sources']])
        execute([compiler, '@' + str(compile_rsp)], folder, env, log)
        outputs = [objects / (Path(source).stem + '.obj') for source in profile['sources']]
        if not all(path.is_file() for path in outputs):
            raise RuntimeError('Missing font library object output')
        library_rsp = folder / (name + '-library.rsp')
        response_file(library_rsp, ['/NOLOGO', '/MACHINE:X64', '/OUT:' + str(libraries / (name + '.lib')), *outputs])
        execute([librarian, '@' + str(library_rsp)], folder, env, log)
    return test_fonts(work, core, lock, env, compiler)


def test_fonts(work, core, lock, env, compiler):
    folder = work / 'fonts-build'
    libraries = work / 'lib'
    log = work / 'fonts-build.log'
    report_path = work / 'fonts-build-report.json'
    test_source = ROOT / 'tests/native/fonts_test.cpp'
    executable = work / 'bin/fonts-test.exe'
    includes = sorted({value for profile in lock['profiles'].values() for value in profile['include_directories']})
    execute([compiler, '/nologo', '/std:c++17', '/O2', '/MD', '/EHsc', '/utf-8', '/DNOMINMAX',
             '/D_CRT_SECURE_NO_WARNINGS', *['/I' + str(core / value) for value in includes],
             str(test_source), '/Fo' + str(folder / 'native-test.obj'), '/Fe' + str(executable), '/link',
             *[str(libraries / (name + '.lib')) for name in ('harfbuzz', 'freetype', 'brotli')]], folder, env, log)
    execute([sys.executable, str(ROOT / 'tests/run_font_tests.py'), '--exe', str(executable),
             '--work-dir', str(work)], folder, env, log)
    result = json.loads((work / 'fonts-test-result.json').read_text('utf-8'))
    if result != {'passed': 32, 'failed': 0}:
        raise RuntimeError('Font native suite did not fully pass')
    artifacts = [libraries / (name + '.lib') for name in ('brotli', 'freetype', 'harfbuzz')]
    report = {'core_revision':lock['revision'], 'core_inputs':len(lock['files']),
              'archive_inputs':{name:len(row['files']) for name,row in lock['archives'].items()},
              'compile_units':{name:len(row['sources']) for name,row in lock['profiles'].items()},
              'source_manifest_sha256':sha(ROOT / 'fonts.inputs.lock.json'), 'native_tests':result,
              'native_test_source_sha256':sha(test_source), 'test_driver_sha256':sha(ROOT / 'tests/run_font_tests.py'),
              'artifacts':{path.name:{'sha256':sha(path)} for path in artifacts},
              'test_executable_sha256':sha(executable), 'compiler':compiler, 'runtime':'MSVC x64 /MD',
              'supported_default_toolchain':'Visual Studio 2022', 'upstream_shaping_goldens':20,
              'generated_harfbuzz_pri_prepared':True, 'onlyoffice_hb_ft_patch_applied':True,
              'woff2_font_tested':False, 'full_graphics_built':False, 'heif_built':False,
              'old_office_baseline_used':False, 'x2t_converter_built':False, 'full_office_built':False,
              'application_gui_tested':False}
    report_path.write_text(json.dumps(report, indent=2), 'utf-8')
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'build'))
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--archive-cache', type=Path)
    parser.add_argument('--source-cache', type=Path)
    parser.add_argument('--vs-root', type=Path)
    args = parser.parse_args()
    lock = verify_font_inputs()
    if args.command == 'verify':
        print(json.dumps({'ok':True, 'compile_units':136, 'upstream_goldens':20}))
        return
    if os.name != 'nt' or not args.work_dir:
        parser.error('Building requires Windows and an explicit --work-dir')
    work = args.work_dir.resolve()
    if work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise ValueError('Select a build workspace outside this repository')
    marker = work / '.qingliang-dependency-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():
        raise ValueError('Unknown nonempty font workspace; preserved')
    work.mkdir(parents=True, exist_ok=True)
    marker.write_text('One stable dependency/kernel/fonts build workspace.\n', 'utf-8')
    lockfile = work / '.build.lock'
    fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        core = prepare_fonts(work, lock, args.archive_cache, args.source_cache)
        build_fonts(work, core, lock, args.vs_root)
    finally:
        os.close(fd)
        lockfile.unlink()


if __name__ == '__main__':
    main()
