"""Source-build Windows kernel_network and CryptoPPLib, then test loopback downloads and crypto primitives/wrappers."""
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from build_dependencies import prepare, build as build_dependencies, sha
from build_kernel import prepare_kernel_sources, verify_kernel_inputs, compile_kernel, dependencies_current, response_file
from build_x2t_dependencies import kernel_current
from build_windows import discover_vs, msvc_environment, execute
from verify_sources import ROOT, safe_relative


def verify_transport_inputs():
    lock = json.loads((ROOT / 'transport.inputs.lock.json').read_text('utf-8'))
    upstream = json.loads((ROOT / 'upstream.lock.json').read_text('utf-8'))
    revision = next(row['revision'] for row in upstream if row['repository'] == 'core')
    if lock['repository'] != 'https://github.com/ONLYOFFICE/core' or lock['revision'] != revision:
        raise ValueError('Transport source identity differs from pinned core')
    indexed = {}
    for row in lock['files']:
        safe_relative(row['file'])
        if row['file'] in indexed or not re.fullmatch(r'[a-f0-9]{64}', row['sha256']):
            raise ValueError('Duplicate transport input or invalid source hash')
        if row['origin'] not in ('pinned-upstream', 'community-overlay'):
            raise ValueError('Unknown transport source origin')
        if row['origin'] == 'community-overlay':
            for key in ('patch', 'modified_source'):
                safe_relative(row[key])
            if not re.fullmatch(r'[a-f0-9]{64}', row['base_sha256']):
                raise ValueError('Invalid transport patch base')
            if sha(ROOT / row['modified_source']) != row['sha256'] or sha(ROOT / row['patch']) != row['patch_sha256']:
                raise ValueError('Published transport patch/source hash mismatch')
        indexed[row['file']] = row
    for name, count in [('network', 4), ('crypto', 181)]:
        profile = lock['profiles'][name]
        sources = profile['sources']
        if len(sources) != count or len(set(sources)) != count or len({Path(x).stem.lower() for x in sources}) != count:
            raise ValueError('Invalid transport compile units or object basename collision')
        if not set(sources).issubset(indexed):
            raise ValueError('Unpinned transport compile unit')
        for directory in profile['include_directories']:
            safe_relative(directory)
    if lock['crypto_asm_enabled']:
        raise ValueError('Expected upstream portable CryptoPP profile')
    return lock


def compile_libraries(work, core, boost, lock, vs_root=None):
    env = msvc_environment(discover_vs(vs_root, version_range='[17.0,18.0)'), work)
    env['VSLANG'] = '1033'
    compiler = shutil.which('cl.exe', path=env['PATH'])
    linker = shutil.which('link.exe', path=env['PATH'])
    librarian = shutil.which('lib.exe', path=env['PATH'])
    folder = work / 'transport-build'
    folder.mkdir(exist_ok=True)
    (work / 'lib').mkdir(exist_ok=True)
    log = work / 'transport-build.log'
    report_path = work / 'transport-build-report.json'
    if report_path.exists():
        report_path.unlink()
    for name in ('network', 'crypto'):
        profile = lock['profiles'][name]
        objects = folder / name
        objects.mkdir(exist_ok=True)
        flags = ['/nologo', '/c', '/O2', '/MD', '/EHsc', '/std:c++17', '/MP4', '/bigobj', '/utf-8',
                 '/DBOOST_ALL_NO_LIB', '/D_CRT_SECURE_NO_WARNINGS', '/I' + str(boost),
                 '/I' + str(core), '/Fo' + str(objects) + os.sep]
        flags += ['/D' + value for value in profile['defines']]
        flags += ['/I' + str(core / value) for value in profile['include_directories']]
        compile_rsp = folder / (name + '-compile.rsp')
        response_file(compile_rsp, flags + [core / source for source in profile['sources']])
        execute([compiler, '@' + str(compile_rsp)], folder, env, log)
        outputs = [objects / (Path(source).stem + '.obj') for source in profile['sources']]
        if not all(output.is_file() for output in outputs):
            raise RuntimeError('Missing transport compile output')
        link_rsp = folder / (name + '-link.rsp')
        if name == 'network':
            response_file(link_rsp, ['/NOLOGO', '/DLL', '/MACHINE:X64', '/OPT:REF',
                                    '/OUT:' + str(work / 'bin/kernel_network.dll'),
                                    '/IMPLIB:' + str(work / 'bin/kernel_network.lib'), *outputs,
                                    work / 'bin/kernel.lib', 'advapi32.lib', 'urlmon.lib', 'rpcrt4.lib',
                                    'shell32.lib', 'wininet.lib', 'ole32.lib'])
            execute([linker, '@' + str(link_rsp)], folder, env, log)
        else:
            response_file(link_rsp, ['/NOLOGO', '/MACHINE:X64', '/OUT:' + str(work / 'lib/CryptoPPLib.lib'), *outputs])
            execute([librarian, '@' + str(link_rsp)], folder, env, log)
    test_source = ROOT / 'tests/native/transport_crypto_test.cpp'
    executable = work / 'bin/transport-crypto-test.exe'
    execute([compiler, '/nologo', '/std:c++17', '/O2', '/MD', '/EHsc', '/utf-8', '/DNOMINMAX',
             '/DBOOST_ALL_NO_LIB', '/DCRYPTOPP_DISABLE_ASM', '/D_CRT_SECURE_NO_WARNINGS',
             '/I' + str(core), '/I' + str(boost), str(test_source), '/Fo' + str(folder / 'native-test.obj'),
             '/Fe' + str(executable), '/link', str(work / 'lib/CryptoPPLib.lib'),
             str(work / 'bin/kernel_network.lib'), str(work / 'bin/kernel.lib'),
             'bcrypt.lib', 'advapi32.lib', 'ole32.lib'], folder, env, log)
    # The driver owns a loopback-only HTTP server and bounds test-process runtime.
    execute(['python', str(ROOT / 'tests/run_transport_tests.py'), '--exe', str(executable),
             '--work-dir', str(work)], folder, env, log)
    result = json.loads((work / 'transport-test-result.json').read_text('utf-8'))
    if result != {'passed': 20, 'failed': 0}:
        raise RuntimeError('Transport/crypto suite did not fully pass')
    artifacts = [work / 'bin/kernel_network.dll', work / 'bin/kernel_network.lib', work / 'lib/CryptoPPLib.lib']
    report = {'core_revision': lock['revision'], 'source_inputs': len(lock['files']),
              'compile_units': {name: len(profile['sources']) for name, profile in lock['profiles'].items()},
              'source_manifest_sha256': sha(ROOT / 'transport.inputs.lock.json'),
              'native_test_source_sha256': sha(test_source), 'native_tests': result,
              'artifacts': {path.name: {'sha256': sha(path)} for path in artifacts},
              'kernel_dll_sha256': sha(work / 'bin/kernel.dll'), 'runtime': 'MSVC x64 /MD',
              'compiler': compiler, 'supported_default_toolchain': 'Visual Studio 2022',
              'crypto_asm_enabled': False, 'network_tests_loopback_only': True,
              'websocket_built': False, 'full_graphics_built': False, 'old_office_baseline_used': False,
              'x2t_converter_built': False, 'full_office_built': False, 'application_gui_tested': False}
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
    lock = verify_transport_inputs()
    if args.command == 'verify':
        print(json.dumps({'ok': True, 'source_inputs': len(lock['files']), 'network_units': 4, 'crypto_units': 181}))
        return
    if os.name != 'nt' or not args.work_dir:
        parser.error('Building requires Windows and an explicit --work-dir')
    work = args.work_dir.resolve()
    if work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise ValueError('Select a build workspace outside this repository')
    marker = work / '.qingliang-dependency-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():
        raise ValueError('Unknown nonempty dependency workspace; preserved')
    work.mkdir(parents=True, exist_ok=True)
    marker.write_text('One stable dependency/kernel/transport build workspace.\n', 'utf-8')
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
        compile_libraries(work, core, roots['boost'], lock, args.vs_root)
    finally:
        os.close(fd)
        lockfile.unlink()


if __name__ == '__main__':
    main()
