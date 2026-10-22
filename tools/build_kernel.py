"""Build the pinned 47-unit kernel with new ICU/UnicodeConverter and run linked native integration tests."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from build_dependencies import build as build_dependencies, prepare, sha, verify_dependencies
from build_windows import discover_vs, execute, msvc_environment
from verify_patches import download
from verify_sources import ROOT, safe_relative

def verify_kernel_inputs():
    lock = json.loads((ROOT / 'kernel.inputs.lock.json').read_text('utf-8'))
    upstream = json.loads((ROOT / 'upstream.lock.json').read_text('utf-8'))
    expected = next(x['revision'] for x in upstream if x['repository'] == 'core')
    if lock['repository'] != 'https://github.com/ONLYOFFICE/core' or lock['revision'] != expected:
        raise ValueError('Kernel source identity differs from main source lock')
    indexed = {}
    for row in lock['files']:
        safe_relative(row['file'])
        if row['file'] in indexed or not re.fullmatch(r'[a-f0-9]{64}', row['sha256']):
            raise ValueError('Duplicate kernel input or invalid hash')
        if row['origin'] not in ('pinned-upstream', 'community-overlay'):
            raise ValueError('Unknown kernel source origin')
        if row['origin'] == 'community-overlay':
            for key in ('patch', 'modified_source'):
                safe_relative(row[key])
            if not re.fullmatch(r'[a-f0-9]{64}', row['base_sha256']):
                raise ValueError('Invalid kernel patch base hash')
            if sha(ROOT / row['modified_source']) != row['sha256'] or sha(ROOT / row['patch']) != row['patch_sha256']:
                raise ValueError('Published kernel patch/source hash differs')
        indexed[row['file']] = row
    if len(lock['sources']) != 47 or len(set(lock['sources'])) != 47:
        raise ValueError('Expected the 47 pinned upstream kernel compile units')
    if not set(lock['sources']).issubset(indexed):
        raise ValueError('Kernel compile unit missing from input manifest')
    if len({Path(name).stem.lower() for name in lock['sources']}) != 47:
        raise ValueError('Object basename collision in kernel compile units')
    for value in lock['include_directories']:
        safe_relative(value)
    return lock

def prepare_kernel_sources(lock, work, source_cache=None):
    core = (work / 'sources/core').resolve()
    if not core.is_relative_to(work.resolve()):
        raise ValueError('Kernel source directory escapes the selected workspace')
    core.mkdir(parents=True, exist_ok=True)
    # Resolve and create directories before workers start. On Windows, resolving
    # paths while another thread creates their parents can yield transient paths.
    targets = {}
    for row in lock['files']:
        safe_relative(row['file'])
        target = core / row['file']
        if not target.resolve().is_relative_to(core):
            raise ValueError('Kernel path escapes the selected source directory: ' + row['file'])
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.parent.resolve().is_relative_to(core):
            raise ValueError('Kernel parent escapes the selected source directory: ' + row['file'])
        targets[row['file']] = target
    def fetch(row):
        target = targets[row['file']]
        if target.exists():
            if sha(target) not in {row['sha256'], row.get('base_sha256', row['sha256'])}:
                raise ValueError('Unknown existing kernel source modification; preserved: ' + row['file'])
            return
        if source_cache is not None and (source_cache / row['file']).is_file():
            data = (source_cache / row['file']).read_bytes()
        else:
            url = 'https://raw.githubusercontent.com/ONLYOFFICE/core/' + lock['revision'] + '/' + row['file']
            data = download(url)
        if hashlib.sha256(data).hexdigest() != row.get('base_sha256', row['sha256']):
            raise ValueError('Pinned kernel input hash mismatch: ' + row['file'])
        target.write_bytes(data)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(fetch, lock['files']))
    for row in lock['files']:
        target = targets[row['file']]
        if row['origin'] == 'community-overlay' and sha(target) == row['base_sha256']:
            if not (core / '.git').exists():
                subprocess.run(['git', 'init', '--quiet', str(core)], check=True)
            command = ['git', '-c', 'core.autocrlf=false', '-C', str(core), 'apply', '--whitespace=nowarn']
            subprocess.run(command + ['--check', str(ROOT / row['patch'])], check=True)
            subprocess.run(command + [str(ROOT / row['patch'])], check=True)
        if sha(target) != row['sha256']:
            raise ValueError('Prepared kernel input hash mismatch: ' + row['file'])
    print(f'Kernel: {len(lock["files"])} pinned source/header/license inputs prepared', flush=True)
    return core

def dependencies_current(work):
    report_path = work / 'dependency-build-report.json'
    if not report_path.is_file():
        return False
    report = json.loads(report_path.read_text('utf-8'))
    if report.get('native_tests') != {'passed': 14, 'failed': 0}:
        return False
    for name, entry in report['artifacts'].items():
        path = work / 'bin' / name
        if not path.is_file() or sha(path) != entry['sha256']:
            return False
    expected = verify_dependencies()['unicode_converter']['patches'][0]['result_sha256']
    return report.get('unicode_converter_source_sha256') == expected

def response_file(path, arguments):
    # Use Windows command-line quoting; UTF-16 response files also support non-ASCII workspace names.
    path.write_text('\n'.join(subprocess.list2cmdline([str(x)]) for x in arguments) + '\n', encoding='utf-16')

def compile_kernel(work, core, lock, vs_root=None):
    env = msvc_environment(discover_vs(vs_root), work)
    compiler = shutil.which('cl.exe', path=env['PATH'])
    linker = shutil.which('link.exe', path=env['PATH'])
    folder = work / 'kernel-build'
    objects = folder / 'objects'
    objects.mkdir(parents=True, exist_ok=True)
    output = work / 'bin'
    log = work / 'kernel-build.log'
    report_path = work / 'kernel-build-report.json'
    if report_path.exists():
        report_path.unlink()
    includes = ['/I' + str(core / name) for name in lock['include_directories']]
    flags = ['/nologo', '/c', '/O2', '/MD', '/EHsc', '/std:c++17', '/MP4', '/bigobj', '/utf-8',
             '/D_CRT_SECURE_NO_WARNINGS', '/Fo' + str(objects) + os.sep]
    flags += ['/D' + value for value in lock['defines']]
    flags += includes + [str(core / name) for name in lock['sources']]
    compile_rsp = folder / 'compile.rsp'
    response_file(compile_rsp, flags)
    execute([compiler, '@' + str(compile_rsp)], folder, env, log)
    input_objects = [objects / (Path(name).stem + '.obj') for name in lock['sources']]
    if not all(path.is_file() for path in input_objects):
        raise RuntimeError('One or more kernel object outputs are missing')
    link_rsp = folder / 'link.rsp'
    response_file(link_rsp, ['/NOLOGO', '/DLL', '/MACHINE:X64', '/OPT:REF', '/OPT:ICF',
                            '/OUT:' + str(output / 'kernel.dll'), '/IMPLIB:' + str(output / 'kernel.lib'),
                            *input_objects, output / 'UnicodeConverter.lib', *lock['system_libraries']])
    execute([linker, '@' + str(link_rsp)], folder, env, log)
    fixture_source = ROOT / 'tests/native/kernel_integration_test.cpp'
    executable = output / 'kernel-integration-test.exe'
    command = [compiler, '/nologo', '/std:c++17', '/EHsc', '/O2', '/MD', '/utf-8',
               '/DUNICODE', '/D_UNICODE', '/DWIN32', '/DNOMINMAX', '/D_CRT_SECURE_NO_WARNINGS',
               '/I' + str(core), str(fixture_source), '/Fo' + str(folder / 'integration.obj'),
               '/Fe' + str(executable), '/link', str(output / 'kernel.lib'), str(output / 'UnicodeConverter.lib')]
    execute(command, folder, env, log)
    fixtures = work / 'kernel-fixtures'
    fixtures.mkdir(exist_ok=True)
    if any(fixtures.iterdir()):
        raise ValueError('Prior kernel fixture evidence remains; inspect before reusing')
    result_path = work / 'kernel-test-result.json'
    if result_path.exists():
        result_path.unlink()
    execute([str(executable), str(fixtures), str(result_path)], output, env, log)
    result = json.loads(result_path.read_text('utf-8'))
    if result != {'passed': 18, 'failed': 0}:
        raise RuntimeError('Kernel integration suite did not fully pass')
    dumpbin = shutil.which('dumpbin.exe', path=env['PATH'])
    imports = subprocess.check_output([dumpbin, '/nologo', '/dependents', str(output / 'kernel.dll')], env=env)
    (work / 'kernel-imports.txt').write_bytes(imports)
    report = {'compile_units': len(lock['sources']), 'pinned_input_files': len(lock['files']),
              'native_tests': result, 'core_revision': lock['revision'],
              'kernel_input_manifest_sha256': sha(ROOT / 'kernel.inputs.lock.json'),
              'kernel_dll_sha256': sha(output / 'kernel.dll'), 'kernel_import_library_sha256': sha(output / 'kernel.lib'),
              'unicode_converter_dll_sha256': sha(output / 'UnicodeConverter.dll'),
              'icu_common_dll_sha256': sha(output / 'icuuc74.dll'), 'icu_data_dll_sha256': sha(output / 'icudt74.dll'),
              'kernel_imports_new_unicode_converter': b'UnicodeConverter.dll' in imports,
              'qt_tool_or_runtime_used': False, 'old_office_baseline_used': False,
              'full_office_built': False, 'x2t_converter_built': False, 'application_gui_tested': False}
    report_path.write_text(json.dumps(report, indent=2), 'utf-8')
    print(json.dumps(report), flush=True)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'build'))
    parser.add_argument('--work-dir', type=Path, help='Reuse the same dependency-build workspace')
    parser.add_argument('--archive-cache', type=Path)
    parser.add_argument('--source-cache', type=Path, help='Optional read-only pinned core source cache; every input is rehashed')
    parser.add_argument('--vs-root', type=Path)
    args = parser.parse_args()
    lock = verify_kernel_inputs()
    if args.command == 'verify':
        print(json.dumps({'ok': True, 'compile_units': len(lock['sources']), 'input_files': len(lock['files'])}))
        return
    if not args.work_dir:
        parser.error('--work-dir is required')
    if os.name != 'nt':
        parser.error('Kernel compilation requires Windows; no sources downloaded')
    work = args.work_dir.resolve()
    if work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise ValueError('Select a workspace outside this repository')
    marker = work / '.qingliang-dependency-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():
        raise ValueError('Unknown nonempty dependency/kernel workspace')
    work.mkdir(parents=True, exist_ok=True)
    marker.write_text('One stable dependency/kernel source and build workspace.\n', 'utf-8')
    lockfile = work / '.build.lock'
    fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        roots = prepare(work, args.archive_cache)
        if not dependencies_current(work):
            build_dependencies(work, roots, args.vs_root)
        core = prepare_kernel_sources(lock, work, args.source_cache)
        compile_kernel(work, core, lock, args.vs_root)
    finally:
        os.close(fd)
        lockfile.unlink()

if __name__ == '__main__':
    main()
