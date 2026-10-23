"""Build the pinned native desktop spelling dependency; Qt/CEF/GUI remain separate."""
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from build_dependencies import acquire_archive, sha
from build_fonts import extract_selected
from build_kernel import response_file
from build_windows import discover_vs, execute, msvc_environment
from verify_sources import ROOT, safe_relative, verify


def verify_desktop_inputs():
    lock = json.loads((ROOT / 'desktop.inputs.lock.json').read_text('utf-8'))
    upstream = json.loads((ROOT / 'upstream.lock.json').read_text('utf-8'))
    core_revision = next(r['revision'] for r in upstream if r['repository'] == 'core')
    for key, repository, revision, destination in [
        ('core', 'https://github.com/ONLYOFFICE/core', core_revision, '.'),
        ('hunspell', 'https://github.com/hunspell/hunspell',
         '8a2fdfe5a6bb1cbafc04b0c8486abcefd17ad903', 'Common/3dParty/hunspell/hunspell')]:
        row = lock[key]
        if (row['repository'], row['revision'], row['destination']) != (repository, revision, destination):
            raise ValueError('Desktop dependency origin differs from fixed source')
        if row['url'] != repository.replace('https://github.com/', 'https://codeload.github.com/') + '/zip/' + revision:
            raise ValueError('Unexpected desktop archive URL')
        if row['root'] != repository.rsplit('/', 1)[1] + '-' + revision:
            raise ValueError('Unexpected desktop archive root')
        safe_relative(row['archive'])
        if not re.fullmatch('[a-f0-9]{64}', row['sha256']):
            raise ValueError('Invalid desktop archive hash')
        indexed = {}
        for item in row['files']:
            safe_relative(item['file'])
            if item['file'].casefold() in indexed or not re.fullmatch('[a-f0-9]{64}', item['sha256']):
                raise ValueError('Duplicate or invalid desktop input')
            indexed[item['file'].casefold()] = item
        patches = set()
        for item in row.get('patches', []):
            for name in ('file', 'patch', 'modified_source'):
                safe_relative(item[name])
            if item['file'] in patches or indexed[item['file'].casefold()]['sha256'] != item['base_sha256']:
                raise ValueError('Desktop patch base differs')
            patches.add(item['file'])
            if sha(ROOT / item['patch']) != item['patch_sha256'] or sha(ROOT / item['modified_source']) != item['result_sha256']:
                raise ValueError('Desktop adaptation hash differs')
    sources = lock['sources']
    if len(sources) != 10 or len(set(sources)) != 10:
        raise ValueError('Desktop Hunspell must retain all ten native units')
    indexed = {r['file'] for r in lock['hunspell']['files']}
    if not set(sources).issubset(indexed) or not {'COPYING', 'COPYING.LESSER', 'COPYING.MPL', 'license.hunspell'}.issubset(indexed):
        raise ValueError('Missing Hunspell source or license inputs')
    hashes = {r['file']: r['sha256'] for r in lock['hunspell']['files']}
    for name in ('COPYING', 'COPYING.LESSER', 'COPYING.MPL', 'license.hunspell'):
        if sha(ROOT / 'licenses/hunspell' / name) != hashes[name]:
            raise ValueError('Hunspell license copy differs from original')
    if lock['defines'] != ['WIN32', '_WINDOWS', 'NDEBUG', 'NOMINMAX', 'BUILDING_LIBHUNSPELL', '_CRT_SECURE_NO_WARNINGS']:
        raise ValueError('Unexpected native desktop build profile')
    return lock


def prepare_desktop(lock, work, archive_cache=None):
    core = work / 'sources/core'
    for key in ('core', 'hunspell'):
        row = lock[key]
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
                raise ValueError('Prepared desktop adaptation hash differs')
    prefix = core / 'Common/3dParty/hunspell'
    if (prefix / 'HEAD').read_text('utf-8').strip() != lock['hunspell']['revision']:
        raise ValueError('Hunspell HEAD differs from pinned core')
    pri = (prefix / 'qt/hunspell.pri').read_text('utf-8')
    selected = ['src/hunspell/' + n for n in re.findall(r'/hunspell/src/hunspell/([^/\s]+\.cxx)', pri)]
    if selected != lock['sources']:
        raise ValueError('Native Hunspell selection differs from upstream project')
    return core / lock['hunspell']['destination']


def audit_inputs(dependency_files, source, lock, env):
    """MSVC sourceDependencies uses JSON, independent of the compiler UI language."""
    overlays = {r['file']: r['result_sha256'] for r in lock['hunspell']['patches']}
    expected = {(source / r['file']).resolve(): overlays.get(r['file'], r['sha256']) for r in lock['hunspell']['files']}
    toolchain = [Path(env['VCTOOLSINSTALLDIR']).resolve(), Path(env['WINDOWSSDKDIR']).resolve()]
    used = set()
    system = set()
    for path in dependency_files:
        data = json.loads(path.read_text('utf-8-sig'))['Data']
        for name in [data['Source'], *data['Includes']]:
            item = Path(name).resolve()
            if item in expected:
                if sha(item) != expected[item]:
                    raise ValueError('Compiler read modified Hunspell source: ' + str(item))
                used.add(item.relative_to(source).as_posix())
            elif any(item.is_relative_to(root) for root in toolchain):
                system.add(str(item))
            else:
                raise ValueError('Compiler read unpinned input: ' + str(item))
    if not set(lock['sources']).issubset(used):
        raise ValueError('Compiler dependency records omit a native source')
    return {'locked_inputs_read': sorted(used), 'toolchain_headers': len(system), 'compile_units': len(dependency_files)}


def build_hunspell(lock, work, source, vs_root=None):
    report_path = work / 'desktop-build-report.json'
    report_path.unlink(missing_ok=True)
    result_path = work / 'desktop-test-result.json'
    result_path.unlink(missing_ok=True)
    env = msvc_environment(discover_vs(vs_root, version_range='[17.0,18.0)'), work)
    compiler = shutil.which('cl.exe', path=env['PATH'])
    linker = shutil.which('link.exe', path=env['PATH'])
    folder = work / 'desktop-build'
    folder.mkdir(exist_ok=True)
    output = work / 'bin'
    output.mkdir(exist_ok=True)
    log = work / 'desktop-build.log'
    objects, dependencies = [], []
    for name in lock['sources']:
        obj = folder / (Path(name).stem + '.obj')
        dep = obj.with_suffix('.deps.json')
        command = [compiler, '/nologo', '/c', '/O2', '/MD', '/EHsc', '/std:c++17', '/utf-8',
                   '/I' + str(source / 'src'), '/Fo' + str(obj), '/sourceDependencies', str(dep)]
        command += ['/D' + value for value in lock['defines']]
        execute(command + [str(source / name)], folder, env, log)
        objects.append(obj)
        dependencies.append(dep)
    audit = audit_inputs(dependencies, source, lock, env)
    (work / 'desktop-compiler-inputs.json').write_text(json.dumps(audit, indent=2) + '\n', 'utf-8')
    response = folder / 'link.rsp'
    response_file(response, ['/NOLOGO', '/DLL', '/MACHINE:X64', '/OPT:REF', '/OPT:ICF',
                             '/OUT:' + str(output / 'hunspell.dll'), '/IMPLIB:' + str(output / 'hunspell.lib'), *objects])
    execute([linker, '@' + str(response)], folder, env, log)
    fixture = ROOT / 'tests/native/desktop_spelling_test.cpp'
    executable = output / 'desktop-spelling-test.exe'
    execute([compiler, '/nologo', '/std:c++17', '/EHsc', '/O2', '/MD', '/utf-8', '/I' + str(source / 'src'),
             str(fixture), '/Fo' + str(folder / 'test.obj'), '/Fe' + str(executable),
             '/link', str(output / 'hunspell.lib')], folder, env, log)
    fixtures = folder / 'fixtures'
    fixtures.mkdir(exist_ok=True)
    execute([str(executable), str(fixtures), str(result_path)], output, env, log)
    result = json.loads(result_path.read_text('utf-8'))
    if result['failed'] != 0 or result['passed'] != 22 or len(result['cases']) != 22:
        raise RuntimeError('Native desktop spelling suite failed')
    dumpbin = shutil.which('dumpbin.exe', path=env['PATH'])
    imports = subprocess.check_output([dumpbin, '/nologo', '/dependents', str(output / 'hunspell.dll')], env=env)
    (work / 'desktop-imports.txt').write_bytes(imports)
    report = {'component': 'hunspell', 'compile_units': 10, 'locked_source_header_license_files': len(lock['hunspell']['files']),
              'hunspell_revision': lock['hunspell']['revision'], 'native_tests': result,
              'input_manifest_sha256': sha(ROOT / 'desktop.inputs.lock.json'), 'test_source_sha256': sha(fixture),
              'builder_source_sha256': sha(Path(__file__)),
              'hunspell_dll_sha256': sha(output / 'hunspell.dll'), 'hunspell_lib_sha256': sha(output / 'hunspell.lib'),
              'compiler_input_audit': audit, 'qt_or_cef_used': False, 'old_office_baseline_used': False,
              'desktop_host_built': False, 'application_gui_tested': False, 'installer_built': False}
    report_path.write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('native_tests','compiler_input_audit')}, indent=2), flush=True)
    print(json.dumps({'native_tests': {'passed': result['passed'], 'failed': result['failed']}}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'build'))
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--archive-cache', type=Path)
    parser.add_argument('--vs-root', type=Path)
    args = parser.parse_args()
    verify()
    lock = verify_desktop_inputs()
    if args.command == 'verify':
        print(json.dumps({'ok': True, 'compile_units': len(lock['sources']), 'input_files': len(lock['hunspell']['files']), 'adaptations': len(lock['hunspell']['patches'])}))
        return
    if os.name != 'nt' or not args.work_dir:
        parser.error('build requires Windows and --work-dir')
    work = args.work_dir.resolve()
    if work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise ValueError('Choose a build workspace outside the repository')
    marker = work / '.qingliang-dependency-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():
        raise ValueError('Refusing an unknown nonempty build workspace')
    work.mkdir(parents=True, exist_ok=True)
    marker.write_text('One stable community dependency build workspace.\n', 'utf-8')
    guard = work / '.build.lock'
    fd = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        source = prepare_desktop(lock, work, args.archive_cache)
        build_hunspell(lock, work, source, args.vs_root)
    finally:
        os.close(fd)
        guard.unlink()


if __name__ == '__main__':
    main()
