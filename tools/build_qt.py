"""Build the Qt desktop shell around the already built native host; editing resources remain separate."""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tarfile
import zipfile
from pathlib import Path
from build_dependencies import acquire_archive, sha
from build_host import MODULES, verify_host_inputs
from build_windows import discover_vs, execute, msvc_environment
from verify_sources import ROOT, safe_relative


def verify_inputs():
    host = verify_host_inputs()
    lock = json.loads((ROOT / 'qt.inputs.lock.json').read_text('utf-8'))
    for name in ('host', 'ui'):
        if sha(ROOT / (name + '.inputs.lock.json')) != lock[name + '_input_lock_sha256']:
            raise ValueError('Qt prerequisite source lock differs: ' + name)
    ui = json.loads((ROOT / 'ui.inputs.lock.json').read_text('utf-8'))['upstream']
    for key in ('revision', 'url', 'sha256', 'root', 'archive'):
        if lock['desktop_apps'][key] != ui[key] or lock['core'][key] != host['core_archive'][key]:
            raise ValueError('Qt source archive differs from pinned upstream')
    for family in ('desktop_apps', 'core', 'vlc_source', 'vlc_runtime'):
        row = lock[family]
        safe_relative(row['archive']); safe_relative(row['root'])
        if not re.fullmatch('[a-f0-9]{64}', row['sha256']):
            raise ValueError('Invalid Qt archive identity')
        seen = set()
        for item in row['files']:
            safe_relative(item['file'])
            if item['file'].casefold() in seen:
                raise ValueError('Duplicate Qt source input')
            seen.add(item['file'].casefold())
            if not re.fullmatch('[a-f0-9]{64}', item['sha256']):
                raise ValueError('Invalid Qt source hash')
            for field in ('source', 'patch'):
                if field in item:
                    safe_relative(item[field])
                    expected = item['patch_sha256'] if field == 'patch' else item['sha256']
                    if sha(ROOT / item[field]) != expected:
                        raise ValueError('Qt published source or patch differs')
    for section in (lock['qt_sdk']['files'], lock['compiler_inputs']):
        seen = set()
        for row in section:
            safe_relative(row['file'])
            if row['file'].casefold() in seen or not re.fullmatch('[a-f0-9]{64}', row['sha256']):
                raise ValueError('Invalid or duplicate Qt compiler input')
            seen.add(row['file'].casefold())
    providers = {}
    for row in host['compiler_inputs']:
        module, relative = row['file'][1:].split('/', 1)
        providers[MODULES[module] + '/' + relative] = row['sha256']
    for family, folder in [('desktop_sdk', 'desktop-sdk'), ('cef_sdk', 'cef'), ('cef_source', 'cef')]:
        providers.update({'sources/' + folder + '/' + row['file']: row['sha256'] for row in host[family]['files']})
    for family, folder in [('desktop_apps', 'desktop-apps'), ('core', 'core'), ('vlc_source', 'vlc')]:
        providers.update({'sources/' + folder + '/' + row['file']: row['sha256'] for row in lock[family]['files']})
    providers['sources/vlc/include/vlc/libvlc_version.h'] = lock['vlc_version_header_sha256']
    for row in lock['compiler_inputs']:
        if providers.get(row['file']) != row['sha256']:
            raise ValueError('Qt compiler input differs from its fixed source provider')
    return lock


def materialize(row, destination, archive):
    """Preflight all selected archive bytes and existing edits before writing any source."""
    selected = {r['file']: r for r in row['files']}
    source = zipfile.ZipFile(archive) if archive.suffix == '.zip' else tarfile.open(archive, 'r:xz')
    pending, members = [], {}
    try:
        for member in source.infolist() if isinstance(source, zipfile.ZipFile) else source.getmembers():
            name = member.filename if isinstance(source, zipfile.ZipFile) else member.name
            safe_relative(name)
            prefix = row['root'] + '/'
            if not name.startswith(prefix):
                if name.rstrip('/') == row['root']: continue
                raise ValueError('Unexpected Qt archive root')
            relative = name[len(prefix):]
            if relative not in selected: continue
            linked = stat.S_ISLNK(member.external_attr >> 16) if isinstance(source, zipfile.ZipFile) else not member.isfile()
            if relative.casefold() in members or linked:
                raise ValueError('Duplicate or linked Qt archive member')
            members[relative.casefold()] = member
        for name, item in selected.items():
            safe_relative(name)
            target = (destination / name).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError('Qt destination escapes source directory')
            member = members.get(name.casefold())
            if member is None: raise ValueError('Missing selected Qt archive member')
            data = source.read(member) if isinstance(source, zipfile.ZipFile) else source.extractfile(member).read()
            base = item.get('base_sha256', item['sha256'])
            if hashlib.sha256(data).hexdigest() != base:
                raise ValueError('Qt archive source hash differs')
            if 'source' in item:
                data = (ROOT / item['source']).read_bytes()
                if hashlib.sha256(data).hexdigest() != item['sha256']:
                    raise ValueError('Qt overlay bytes differ')
            allowed = {base, item['sha256'], item.get('parent_sha256'), item.get('frozen_parent_sha256')}
            if target.exists() and sha(target) not in allowed:
                raise ValueError('Unknown Qt source edit preserved: ' + name)
            pending.append((target, data))
        for target, data in pending:
            if not target.exists() or target.read_bytes() != data:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
    finally:
        source.close()


def prepare(lock, work, cache):
    for family, folder in [('desktop_apps', 'desktop-apps'), ('core', 'core'),
                           ('vlc_source', 'vlc'), ('vlc_runtime', 'vlc-runtime')]:
        row = lock[family]
        materialize(row, work / 'sources' / folder, acquire_archive(row, work, cache))
    vlc = work / 'sources/vlc'
    text = (vlc / 'include/vlc/libvlc_version.h.in').read_text('utf-8')
    for name, value in {'MAJOR': '3', 'MINOR': '0', 'REVISION': '21', 'EXTRA': ''}.items():
        for prefix in ('VERSION_', 'LIBVLC_VERSION_'):
            text = text.replace('@' + prefix + name + '@', value)
    data = text.encode('utf-8')
    if re.search(r'@[A-Za-z_]+@', text) or hashlib.sha256(data).hexdigest() != lock['vlc_version_header_sha256']:
        raise ValueError('Generated official VLC version header differs')
    target = vlc / 'include/vlc/libvlc_version.h'
    if target.exists() and target.read_bytes() != data:
        raise ValueError('Unknown generated VLC header edit preserved')
    target.write_bytes(data)


def verify_sdk(lock, qt):
    for item in lock['qt_sdk']['files']:
        if sha(qt / item['file']) != item['sha256']:
            raise ValueError('Qt SDK identity differs: ' + item['file'])


def build_imports(work, env):
    folder = work / 'qt-player-build'
    folder.mkdir(exist_ok=True)
    for name, source in [('vlc', 'lib/libvlc.sym'), ('vlccore', 'src/libvlccore.sym')]:
        symbols = [s.strip() for s in (work / 'sources/vlc' / source).read_text('utf-8').splitlines()
                   if re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', s.strip())]
        if not symbols: raise ValueError('Official VLC source exports are empty')
        definition = folder / (name + '.def')
        definition.write_text('LIBRARY lib' + name + '.dll\nEXPORTS\n' + '\n'.join(symbols) + '\n', 'ascii')
        execute([shutil.which('lib.exe', path=env['PATH']), '/nologo', '/machine:x64', '/def:' + str(definition),
                 '/out:' + str(work / 'lib' / (name + '.lib'))], folder, env, work / 'qt-player-build.log')


def build_component(target, work, qt, env, rebuild=False):
    sdk = work / 'sources/desktop-sdk/ChromiumBasedEditors'
    projects = {'player': sdk / 'videoplayerlib/videoplayerlib.pro',
                'wrapper': sdk / 'lib/qt_wrapper/qtascdocumentscore.pro',
                'helper': sdk / 'lib/ascdocumentscore_helper.pro',
                'shell': work / 'sources/desktop-apps/win-linux/ASCDocumentEditor.pro'}
    folder = work / ('qt-' + target + '-build')
    folder.mkdir(exist_ok=True)
    objects, dependencies = folder / 'objects', folder / 'dependencies'
    objects.mkdir(exist_ok=True); dependencies.mkdir(exist_ok=True)
    if rebuild:
        for path in objects.rglob('*.obj'):
            if not path.resolve().is_relative_to(objects.resolve()):
                raise ValueError('Qt object path escapes its marked build directory')
            path.unlink()
    log = work / ('qt-' + target + '-build.log')
    command = [str(qt / 'bin/qmake.exe'), str(projects[target]), 'CONFIG-=debug',
               'CONFIG+=release vs2019 core_disable_all_warnings office_cef150 libvlc',
               'DEFINES+=ONLYOFFICE_CEF_150 BOOST_ALL_NO_LIB',
               'QMAKE_CXXFLAGS+=/MP4 /bigobj /utf-8 /Zc:__cplusplus /sourceDependencies ' + dependencies.as_posix() + '/',
               'LIBS+=-L' + str(work / 'lib'), '-after', 'OBJECTS_DIR=' + objects.as_posix(),
               'INCLUDEPATH-=/include', 'INCLUDEPATH+=' + str(work / 'sources/vlc/include'),
               'LIBS-=-lvlc -lvlccore', 'LIBS-=$$find(LIBS, .*libvlc.*build.*win_64.*)',
               'INCLUDEPATH-=$$find(INCLUDEPATH, .*libvlc.*build.*win_64.*)']
    if target == 'player':
        command.append('LIBS+=' + str(work / 'lib/vlc.lib') + ' ' + str(work / 'lib/vlccore.lib'))
    execute(command, folder, env, log)
    for path in (folder / 'Makefile', folder / 'Makefile.Release'):
        if path.is_file():
            for line in path.read_text('utf-8', errors='replace').splitlines():
                if line.startswith(('INCPATH ', 'LIBS ')) and re.search(r'libvlc[/\\]build[/\\]win_64', line):
                    raise ValueError('Old bundled VLC header or library path remains')
    execute([shutil.which('nmake.exe', path=env['PATH']), '/nologo'], folder, env, log)
    outputs = {'player': 'mediaplayer/videoplayer.dll', 'wrapper': 'qtascdocumentscore.dll',
               'helper': 'editors_helper.exe', 'shell': 'DesktopEditors.exe'}
    result = work / 'bin' / outputs[target]
    if target == 'shell':
        shutil.copy2(work / 'sources/desktop-apps/win-linux/build/win_64/DesktopEditors.exe', result)
    if not result.is_file(): raise ValueError('Qt component output missing')
    return {'output': result.relative_to(work).as_posix(), 'sha256': sha(result)}


def audit(lock, work, qt, env):
    expected = {(work / r['file']).resolve(): r['sha256'] for r in lock['compiler_inputs']}
    expected.update({(qt / r['file']).resolve(): r['sha256'] for r in lock['qt_sdk']['files']})
    generated, toolchain, used = {}, set(), set()
    roots = [Path(env[k]).resolve() for k in ('VCTOOLSINSTALLDIR', 'WINDOWSSDKDIR')]
    counts = {}
    for target, count in lock['compile_units'].items():
        files = list((work / ('qt-' + target + '-build/dependencies')).glob('*.json'))
        counts[target] = len(files)
        if count != len(files): raise ValueError('Missing or extra Qt compilation record: ' + target)
        for record in files:
            data = json.loads(record.read_text('utf-8-sig'))['Data']
            for item in [data['Source'], *data['Includes']]:
                path = Path(item).resolve()
                used.add(path)
                if path in expected:
                    if sha(path) != expected[path]: raise ValueError('Qt compiler source differs: ' + str(path))
                elif any(path.is_relative_to(root) for root in roots):
                    toolchain.add(path)
                elif path.is_relative_to(work) and (
                    re.fullmatch(r'sources/desktop-apps/win-linux/build/win_64/(moc|rcc)/[^/]+', path.relative_to(work).as_posix())
                    or re.fullmatch(r'sources/desktop-sdk/ChromiumBasedEditors/(lib/qt_wrapper|videoplayerlib)/core_build/win_64/release/(moc|rcc)/(mediaplayer/)?[^/]+', path.relative_to(work).as_posix())):
                    generated[path.relative_to(work).as_posix()] = sha(path)
                else: raise ValueError('Unpinned Qt compiler input: ' + str(path))
    return {'compile_units': counts, 'locked_inputs': len(used) - len(toolchain) - len(generated),
            'toolchain_headers': len(toolchain), 'generated_inputs': generated}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'prepare', 'build'))
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--qt-dir', type=Path)
    parser.add_argument('--archive-cache', type=Path)
    parser.add_argument('--rebuild', action='store_true', help='Recompile every Qt object in the existing staging tree')
    args = parser.parse_args()
    lock = verify_inputs()
    if args.command == 'verify':
        print(json.dumps({'ok': True, 'compile_units': lock['compile_units']})); return
    if not args.work_dir: parser.error('--work-dir is required')
    work = args.work_dir.resolve()
    if ROOT == work or ROOT in work.parents or work in ROOT.parents or not (work / '.qingliang-dependency-build').is_file():
        raise ValueError('Use the existing marked stable host build staging directory')
    fd = os.open(work / '.build.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        prepare(lock, work, args.archive_cache)
        if args.command == 'prepare': return
        if os.name != 'nt' or not args.qt_dir: parser.error('Windows and --qt-dir are required')
        qt = args.qt_dir.resolve()
        verify_sdk(lock, qt)
        host = json.loads((work / 'host-build-report.json').read_text('utf-8'))
        if host['input_manifest_sha256'] != lock['host_input_lock_sha256'] or sha(work / 'bin/ascdocumentscore.dll') != host['host_dll_sha256']:
            raise ValueError('Build the current native host first')
        env = msvc_environment(discover_vs(version_range='[17.0,18.0)'), work)
        env.update({'PRODUCT_VERSION': '9.4.0', 'BUILD_NUMBER': '129',
                    'DESTDIR_BUILD_OVERRIDE': str(work / 'bin'), 'VisualStudioVersion': '17.0'})
        env['PATH'] = str(qt / 'bin') + os.pathsep + env['PATH']
        (work / 'qt-build-report.json').unlink(missing_ok=True)
        build_imports(work, env)
        result = {name: build_component(name, work, qt, env, args.rebuild) for name in ('player', 'wrapper', 'helper', 'shell')}
        report = {'artifacts': result, 'input_manifest_sha256': sha(ROOT / 'qt.inputs.lock.json'),
                  'builder_sha256': sha(Path(__file__)), 'compiler_audit': audit(lock, work, qt, env),
                  'qt_sdk_prebuilt': True, 'vlc_runtime_prebuilt': True, 'old_office_dlls_used': False,
                  'runtime_tested': False, 'edit_save_tested': False, 'installer_built': False}
        (work / 'qt-build-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
        print(json.dumps({'artifacts': result, 'edit_save_tested': False}))
    finally:
        os.close(fd)
        (work / '.build.lock').unlink()


if __name__ == '__main__':
    main()
