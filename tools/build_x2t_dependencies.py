"""Build x2t prerequisites: Boost.Regex/DateTime and the pinned CompoundFileLib, then test Windows OLE interoperability."""
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from build_dependencies import prepare, build as build_dependencies, sha
from build_kernel import (prepare_kernel_sources, verify_kernel_inputs, compile_kernel,
                          dependencies_current, response_file)
from build_windows import discover_vs, msvc_environment, execute
from verify_sources import ROOT, safe_relative


def verify_x2t_inputs():
    lock = json.loads((ROOT / 'x2t.inputs.lock.json').read_text('utf-8'))
    upstream = json.loads((ROOT / 'upstream.lock.json').read_text('utf-8'))
    expected = next(row['revision'] for row in upstream if row['repository'] == 'core')
    if lock['repository'] != 'https://github.com/ONLYOFFICE/core' or lock['revision'] != expected:
        raise ValueError('x2t prerequisite identity differs from pinned core')
    for rows in (lock['files'], lock['boost']['files']):
        names = set()
        for row in rows:
            safe_relative(row['file'])
            if row['file'] in names or not re.fullmatch(r'[a-f0-9]{64}', row['sha256']):
                raise ValueError('Duplicate input or invalid source hash')
            names.add(row['file'])
    if lock['boost']['version'] != '1.72.0' or lock['boost']['icu_regex_enabled']:
        raise ValueError('Unexpected Boost configuration')
    for row in lock['files']:
        if row['origin'] not in ('pinned-upstream', 'community-overlay'):
            raise ValueError('Unknown x2t prerequisite source origin')
        if row['origin'] == 'community-overlay':
            for key in ('patch', 'modified_source'):
                safe_relative(row[key])
            if not re.fullmatch(r'[a-f0-9]{64}', row['base_sha256']):
                raise ValueError('Invalid prerequisite patch base hash')
            if sha(ROOT / row['modified_source']) != row['sha256'] or sha(ROOT / row['patch']) != row['patch_sha256']:
                raise ValueError('Published prerequisite patch/source hash mismatch')
    groups = [(lock['sources'], lock['files'], 13),
              (lock['boost']['regex_sources'], lock['boost']['files'], 17),
              (lock['boost']['date_time_sources'], lock['boost']['files'], 3)]
    for sources, rows, count in groups:
        if len(sources) != count or len({Path(name).stem.lower() for name in sources}) != count:
            raise ValueError('Unexpected compile unit count or object basename collision')
        if not set(sources).issubset({row['file'] for row in rows}):
            raise ValueError('Unpinned compile unit')
    return lock


def verify_boost_sources(lock, boost):
    for row in lock['boost']['files']:
        if sha(boost / row['file']) != row['sha256']:
            raise ValueError('Boost prerequisite source hash mismatch; preserved: ' + row['file'])


def kernel_current(work):
    report_path = work / 'kernel-build-report.json'
    if not report_path.is_file():
        return False
    report = json.loads(report_path.read_text('utf-8'))
    if report.get('native_tests') != {'passed': 22, 'failed': 0}:
        return False
    if report.get('kernel_input_manifest_sha256') != sha(ROOT / 'kernel.inputs.lock.json'):
        return False
    names = {'kernel.dll': 'kernel_dll_sha256', 'kernel.lib': 'kernel_import_library_sha256',
             'UnicodeConverter.dll': 'unicode_converter_dll_sha256', 'icuuc74.dll': 'icu_common_dll_sha256',
             'icudt74.dll': 'icu_data_dll_sha256'}
    return all((work / 'bin' / name).is_file() and sha(work / 'bin' / name) == report.get(key)
               for name, key in names.items())


def build_prerequisites(work, roots, core, lock, vs_root=None):
    verify_boost_sources(lock, roots['boost'])
    env = msvc_environment(discover_vs(vs_root), work)
    compiler = shutil.which('cl.exe', path=env['PATH'])
    librarian = shutil.which('lib.exe', path=env['PATH'])
    folder = work / 'x2t-dependencies-build'
    folder.mkdir(exist_ok=True)
    libraries = work / 'lib'
    libraries.mkdir(exist_ok=True)
    log = work / 'x2t-dependencies-build.log'
    report_path = work / 'x2t-dependencies-build-report.json'
    if report_path.exists():
        report_path.unlink()
    groups = [('boost_regex', roots['boost'], lock['boost']['regex_sources'], []),
              ('boost_date_time', roots['boost'], lock['boost']['date_time_sources'], lock['boost']['date_time_defines']),
              ('CompoundFileLib', core, lock['sources'], lock['defines'])]
    for name, source, units, defines in groups:
        objects = folder / name
        objects.mkdir(exist_ok=True)
        flags = ['/nologo', '/c', '/O2', '/MD', '/EHsc', '/std:c++17', '/MP4', '/bigobj', '/utf-8',
                 '/DBOOST_ALL_NO_LIB', '/D_CRT_SECURE_NO_WARNINGS', '/DNOMINMAX', '/DNDEBUG',
                 '/I' + str(roots['boost']), '/I' + str(core), '/Fo' + str(objects) + os.sep]
        flags += ['/D' + define for define in defines]
        compile_rsp = folder / (name + '-compile.rsp')
        response_file(compile_rsp, flags + [source / unit for unit in units])
        execute([compiler, '@' + str(compile_rsp)], folder, env, log)
        output_objects = [objects / (Path(unit).stem + '.obj') for unit in units]
        if not all(path.is_file() for path in output_objects):
            raise RuntimeError('Missing prerequisite object output')
        library_rsp = folder / (name + '-library.rsp')
        response_file(library_rsp, ['/NOLOGO', '/MACHINE:X64', '/OUT:' + str(libraries / (name + '.lib')), *output_objects])
        execute([librarian, '@' + str(library_rsp)], folder, env, log)
    fixture_source = ROOT / 'tests/native/x2t_dependencies_test.cpp'
    executable = work / 'bin/x2t-dependencies-test.exe'
    execute([compiler, '/nologo', '/std:c++17', '/O2', '/MD', '/EHsc', '/utf-8',
             '/DBOOST_ALL_NO_LIB', '/DDATE_TIME_INLINE', '/DUNICODE', '/D_UNICODE', '/DNOMINMAX',
             '/D_CRT_SECURE_NO_WARNINGS', '/DKERNEL_USE_DYNAMIC_LIBRARY',
             '/I' + str(core), '/I' + str(roots['boost']), str(fixture_source),
             '/Fo' + str(folder / 'integration.obj'), '/Fe' + str(executable), '/link',
             *[str(libraries / (name + '.lib')) for name, _, _, _ in groups],
             str(work / 'bin/kernel.lib'), 'ole32.lib', 'advapi32.lib'], folder, env, log)
    fixtures = work / 'x2t-dependency-fixtures'
    fixtures.mkdir(exist_ok=True)
    if any(fixtures.iterdir()):
        raise ValueError('Prior x2t prerequisite fixture evidence remains; inspect before reusing')
    result_path = work / 'x2t-dependencies-test-result.json'
    if result_path.exists():
        result_path.unlink()
    execute([str(executable), str(fixtures), str(result_path)], work / 'bin', env, log)
    result = json.loads(result_path.read_text('utf-8'))
    if result != {'passed': 21, 'failed': 0}:
        raise RuntimeError('x2t prerequisite native suite did not fully pass')
    report = {'core_revision': lock['revision'], 'core_input_files': len(lock['files']),
              'compile_units': {name: len(units) for name, _, units, _ in groups},
              'source_manifest_sha256': sha(ROOT / 'x2t.inputs.lock.json'),
              'native_test_source_sha256': sha(fixture_source), 'native_tests': result,
              'artifacts': {name + '.lib': {'sha256': sha(libraries / (name + '.lib'))} for name, _, _, _ in groups},
              'test_executable_sha256': sha(executable), 'kernel_dll_sha256': sha(work / 'bin/kernel.dll'),
              'boost_regex_icu_enabled': False, 'runtime': 'MSVC x64 /MD', 'compiler': compiler,
              'old_office_baseline_used': False, 'x2t_converter_built': False,
              'full_office_built': False, 'application_gui_tested': False}
    report_path.write_text(json.dumps(report, indent=2), 'utf-8')
    print(json.dumps(report), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'build'))
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--archive-cache', type=Path)
    parser.add_argument('--source-cache', type=Path)
    parser.add_argument('--vs-root', type=Path)
    args = parser.parse_args()
    lock = verify_x2t_inputs()
    if args.command == 'verify':
        print(json.dumps({'ok': True, 'compound_compile_units': 13, 'boost_compile_units': 20,
                          'core_input_files': len(lock['files'])}))
        return
    if os.name != 'nt' or not args.work_dir:
        parser.error('Building requires Windows and an explicit --work-dir')
    work = args.work_dir.resolve()
    if work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise ValueError('Select a workspace outside this repository')
    marker = work / '.qingliang-dependency-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():
        raise ValueError('Unknown nonempty dependency workspace; preserved')
    work.mkdir(parents=True, exist_ok=True)
    marker.write_text('One stable dependency/kernel/x2t prerequisite workspace.\n', 'utf-8')
    lockfile = work / '.build.lock'
    fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        roots = prepare(work, args.archive_cache)
        if not dependencies_current(work):
            build_dependencies(work, roots, args.vs_root)
        if not kernel_current(work):
            kernel_lock = verify_kernel_inputs()
            core = prepare_kernel_sources(kernel_lock, work, args.source_cache)
            compile_kernel(work, core, kernel_lock, args.vs_root)
        core = prepare_kernel_sources(lock, work, args.source_cache)
        build_prerequisites(work, roots, core, lock, args.vs_root)
    finally:
        os.close(fd)
        lockfile.unlink()


if __name__ == '__main__':
    main()
