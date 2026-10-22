"""Build locked x265/libde265/libheif with VS2022 and exercise real HEIC encoding and decoding."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from build_dependencies import acquire_archive, sha
from build_fonts import extract_selected
from build_kernel import prepare_kernel_sources
from build_windows import discover_vs, execute, msvc_environment
from verify_sources import ROOT, safe_relative


def verify_heif_inputs():
    lock = json.loads((ROOT / 'heif.inputs.lock.json').read_text('utf-8'))
    upstream = json.loads((ROOT / 'upstream.lock.json').read_text('utf-8'))
    if set(lock['archives']) != {'x265', 'libde265', 'libheif'}:
        raise ValueError('Expected all three HEIF codec archives')
    for row, name in [(lock, 'core'), (lock['upstream_setup'], 'build_tools')]:
        if row['repository'] != 'https://github.com/ONLYOFFICE/' + name or row['revision'] != next(r['revision'] for r in upstream if r['repository'] == name):
            raise ValueError('HEIF profile identity differs from fixed upstream')
    safe_relative(lock['upstream_setup']['file'])
    if not re.fullmatch('[a-f0-9]{64}', lock['upstream_setup']['sha256']):
        raise ValueError('Invalid HEIF upstream setup hash')
    for row in lock['files']:
        safe_relative(row['file'])
        if not re.fullmatch('[a-f0-9]{64}', row['sha256']):
            raise ValueError('Invalid HEIF core input hash')
    for name, row in lock['archives'].items():
        for field in ('archive', 'root', 'destination'):
            safe_relative(row[field])
        if not re.fullmatch('[a-f0-9]{40}', row['revision']) or not re.fullmatch('[a-f0-9]{64}', row['sha256']):
            raise ValueError('Invalid HEIF archive identity')
        repository = 'https://bitbucket.org/multicoreware/x265_git' if name == 'x265' else 'https://github.com/strukturag/' + name
        expected = repository + '/get/' + row['revision'] + '.zip' if name == 'x265' else repository.replace('github.com/', 'codeload.github.com/') + '/zip/' + row['revision']
        if row['repository'] != repository or row['url'] != expected:
            raise ValueError('Unexpected HEIF archive origin')
        names = set()
        for entry in row['files']:
            safe_relative(entry['file'])
            if entry['file'].casefold() in names or not re.fullmatch('[a-f0-9]{64}', entry['sha256']):
                raise ValueError('Duplicate HEIF input or invalid hash')
            names.add(entry['file'].casefold())
        for overlay in row.get('patches', []):
            for field in ('file', 'patch', 'modified_source'):
                safe_relative(overlay[field])
            if sha(ROOT / overlay['patch']) != overlay['patch_sha256'] or sha(ROOT / overlay['modified_source']) != overlay['result_sha256']:
                raise ValueError('HEIF adaptation patch/source hash mismatch')
            if next(e['sha256'] for e in row['files'] if e['file'] == overlay['file']) != overlay['base_sha256']:
                raise ValueError('HEIF adaptation base differs from archive')
        profile = lock['profiles'][name]
        for field in ('source_subdirectory', 'library'):
            safe_relative(profile[field])
        if any(not re.fullmatch('[A-Za-z0-9_]+=[A-Za-z0-9_ .+:/=-]+', option) for option in profile['options']):
            raise ValueError('Invalid HEIF CMake option')
    for row in lock['generated_files']:
        for field in ('file', 'source'):
            safe_relative(row[field])
        if sha(ROOT / row['source']) != row['sha256']:
            raise ValueError('Generated HEIF input hash mismatch')
    if (lock['generator'], lock['architecture'], lock['configuration'], lock['runtime']) != ('Visual Studio 17 2022', 'x64', 'Release', 'MultiThreadedDLL'):
        raise ValueError('Unexpected HEIF build profile')
    return lock


def prepare_heif(work, lock, archive_cache=None, source_cache=None):
    core = prepare_kernel_sources(lock, work, source_cache)
    for name, row in lock['archives'].items():
        archive = acquire_archive(row, work, archive_cache)
        destination = extract_selected(archive, row, core)
        for overlay in row.get('patches', []):
            target = destination / overlay['file']
            if sha(target) == overlay['base_sha256']:
                if not (core / '.git').exists():
                    subprocess.run(['git', 'init', '--quiet', str(core)], check=True)
                cmd = ['git', '-c', 'core.autocrlf=false', '-C', str(core), 'apply', '--whitespace=nowarn']
                subprocess.run(cmd + ['--check', str(ROOT / overlay['patch'])], check=True)
                subprocess.run(cmd + [str(ROOT / overlay['patch'])], check=True)
            if sha(target) != overlay['result_sha256']:
                raise ValueError('Prepared HEIF adaptation hash mismatch')
        print(f'{name}: {len(row["files"])} archive inputs verified and prepared', flush=True)
    for row in lock['generated_files']:
        target = core / row['file']
        if not target.resolve().is_relative_to(core.resolve()):
            raise ValueError('Generated HEIF input escapes source workspace')
        if target.exists() and sha(target) != row['sha256']:
            raise ValueError('Unknown generated HEIF input modification; preserved')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / row['source']).read_bytes())
    return core


def cmake_tool(vs_root, explicit=None):
    tool = explicit or vs_root / 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
    if not Path(tool).is_file():
        tool = shutil.which('cmake')
    if not tool:
        raise ValueError('CMake >=3.21,<4 required; install the VS CMake tools or pass --cmake')
    version = subprocess.check_output([str(tool), '--version'], text=True).splitlines()[0]
    match = re.search(r'version (\d+)\.(\d+)', version)
    if not match or int(match[1]) != 3 or int(match[2]) < 21:
        raise ValueError('This pinned profile requires CMake >=3.21,<4: ' + version)
    return str(tool), version


def build_codecs(work, core, lock, vs_root=None, cmake=None):
    vcvars = discover_vs(vs_root, version_range='[17.0,18.0)')
    vs = vcvars.parents[3]
    env = msvc_environment(vcvars, work)
    env['VSLANG'] = '1033'
    tool, version = cmake_tool(vs, cmake)
    env['PATH'] = str(Path(tool).parent) + os.pathsep + env['PATH']
    log = work / 'heif-build.log'
    report_path = work / 'heif-build-report.json'
    if report_path.exists():
        report_path.unlink()
    builds = {}
    for name in ('x265', 'libde265', 'libheif'):
        row = lock['archives'][name]
        source = core / row['destination']
        folder = source / 'build/win_64/release'
        if not folder.resolve().is_relative_to(work.resolve()):
            raise ValueError('HEIF build output escapes selected workspace')
        folder.mkdir(parents=True, exist_ok=True)
        cache = folder / 'CMakeCache.txt'
        if cache.exists():
            text = cache.read_text('utf-8')
            if ('CMAKE_HOME_DIRECTORY:INTERNAL=' + str((source / lock['profiles'][name]['source_subdirectory']).resolve()).replace('\\','/')) not in text:
                raise ValueError('Different project in existing CMake build directory; preserved')
        query = folder / '.cmake/api/v1/query/codemodel-v2'
        query.parent.mkdir(parents=True, exist_ok=True)
        query.touch()
        profile = lock['profiles'][name]
        args = [tool, '-S', str(source / profile['source_subdirectory']), '-B', str(folder),
                '-G', lock['generator'], '-A', 'x64', '-DCMAKE_GENERATOR_INSTANCE=' + str(vs),
                '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL']
        if 'preset' in profile:
            args += ['--preset', profile['preset']]
        args += ['-D' + option for option in profile['options']]
        if name == 'libheif':
            args += ['-DLIBDE265_INCLUDE_DIR=' + str(builds['libde265']),
                     '-DX265_INCLUDE_DIR=' + str(builds['x265']),
                     '-DLIBDE265_LIBRARY=' + str(builds['libde265'] / lock['profiles']['libde265']['library']),
                     '-DX265_LIBRARY=' + str(builds['x265'] / lock['profiles']['x265']['library'])]
        execute(args, source, env, log)
        execute([tool, '--build', str(folder), '--config', 'Release', '--target', profile['target'], '--parallel', '4'], source, env, log)
        if not (folder / profile['library']).is_file():
            raise RuntimeError('Expected HEIF static library absent: ' + name)
        builds[name] = folder
        if name == 'x265':
            shutil.copyfile(source / 'source/x265.h', folder / 'x265.h')
        if name == 'libde265':
            shutil.copyfile(source / 'libde265/de265.h', folder / 'libde265/de265.h')
        print(name + ': static library built', flush=True)
    return test_codecs(work, core, lock, builds, env, tool, version)


def test_codecs(work, core, lock, builds, env, cmake, cmake_version):
    folder = work / 'heif-test-build'
    folder.mkdir(exist_ok=True)
    log = work / 'heif-build.log'
    compiler = shutil.which('cl.exe', path=env['PATH'])
    executable = work / 'bin/heif-test.exe'
    executable.parent.mkdir(exist_ok=True)
    test_source = ROOT / 'tests/native/heif_test.cpp'
    heif = core / lock['archives']['libheif']['destination']
    execute([compiler, '/nologo', '/std:c++17', '/O2', '/MD', '/EHsc', '/utf-8', '/DNOMINMAX',
             '/DLIBHEIF_STATIC_BUILD', '/DLIBDE265_STATIC_BUILD', '/I' + str(heif / 'libheif/api'),
             '/I' + str(builds['libheif']), '/I' + str(builds['x265']), '/I' + str(builds['libde265']),
             str(test_source), '/Fo' + str(folder / 'native-test.obj'), '/Fe' + str(executable), '/link',
             *[str(builds[name] / lock['profiles'][name]['library']) for name in ('libheif','x265','libde265')],
             'advapi32.lib', 'user32.lib', 'ws2_32.lib'], folder, env, log)
    execute([sys.executable, str(ROOT / 'tests/run_heif_tests.py'), '--exe', str(executable),
             '--work-dir', str(work)], folder, env, log)
    result = json.loads((work / 'heif-test-result.json').read_text('utf-8'))
    if result != {'passed':16, 'failed':0}:
        raise RuntimeError('HEIF native integration tests did not fully pass')
    units = {}
    for name, build in builds.items():
        paths = set()
        for file in (build / '.cmake/api/v1/reply').glob('target-*-Release-*.json'):
            data = json.loads(file.read_text('utf-8'))
            for row in data.get('sources', []):
                if 'compileGroupIndex' in row and Path(row['path']).suffix in ('.c','.cc','.cpp','.cxx'):
                    paths.add(row['path'])
        units[name] = len(paths)
    report = {'core_revision':lock['revision'],'source_manifest_sha256':sha(ROOT / 'heif.inputs.lock.json'),
              'native_test_source_sha256':sha(test_source),'test_driver_sha256':sha(ROOT / 'tests/run_heif_tests.py'),
              'archives':{name:{'revision':row['revision'],'sha256':row['sha256'],'files':len(row['files'])} for name,row in lock['archives'].items()},
              'compile_units':units,'native_tests':result,
              'artifacts':{name:{'sha256':sha(builds[name] / lock['profiles'][name]['library'])} for name in builds},
              'compiler':compiler,'cmake':cmake_version,'runtime':'MSVC x64 /MD',
              'static_hevc_encoder':'x265','static_hevc_decoder':'libde265','dynamic_plugins':False,
              'full_graphics_built':False,'x2t_converter_built':False,'full_office_built':False,
              'application_gui_tested':False,'old_office_baseline_used':False}
    (work / 'heif-build-report.json').write_text(json.dumps(report,indent=2),'utf-8')
    print(json.dumps(report),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify','build'))
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--archive-cache', type=Path)
    parser.add_argument('--source-cache', type=Path)
    parser.add_argument('--vs-root', type=Path)
    parser.add_argument('--cmake', type=Path)
    args = parser.parse_args()
    lock = verify_heif_inputs()
    if args.command == 'verify':
        print(json.dumps({'ok':True,'archives':3,'archive_inputs':sum(len(row['files']) for row in lock['archives'].values())}))
        return
    if os.name != 'nt' or not args.work_dir:
        parser.error('Building requires Windows and an explicit --work-dir')
    work = args.work_dir.resolve()
    if work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise ValueError('Select a build workspace outside this repository')
    marker = work / '.qingliang-dependency-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():
        raise ValueError('Unknown nonempty HEIF build workspace; preserved')
    work.mkdir(parents=True,exist_ok=True)
    marker.write_text('One stable dependency/kernel/graphics prerequisite workspace.\n','utf-8')
    lockfile = work / '.build.lock'
    fd = os.open(lockfile,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,str(os.getpid()).encode('ascii'))
        core = prepare_heif(work,lock,args.archive_cache,args.source_cache)
        build_codecs(work,core,lock,args.vs_root,args.cmake)
    finally:
        os.close(fd)
        lockfile.unlink()


if __name__ == '__main__':
    main()
