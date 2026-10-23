"""Build fixed desktop SDKJS and web editors, then lay out the source-built Qt development runtime."""
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
from build_converter import prepare_sdk, verify_converter_inputs
from build_dependencies import acquire_archive, sha
from build_qt import verify_inputs as verify_qt_inputs
from build_windows import execute
from verify_sources import ROOT, safe_relative

EDITORS = ['documenteditor', 'spreadsheeteditor', 'presentationeditor', 'pdfeditor', 'visioeditor']
SDKS = ['word', 'cell', 'slide', 'visio']


def sdk_overlays(lock, parent):
    indexed = {r['file']: r['sha256'] for r in parent['files']}
    result = {}
    for row in lock.get('sdk_overlays', []):
        name = row['file']
        safe_relative(name)
        for key in ('source', 'patch'): safe_relative(row[key])
        if name.casefold() in result or row['source'] != 'editor-sources/sdkjs/' + name or not row['patch'].startswith('editor-patches/'):
            raise ValueError('Duplicate or invalid desktop SDK overlay')
        if indexed.get(name) != row['parent_sha256']:
            raise ValueError('Desktop SDK overlay parent differs from fixed converter input')
        if any(not re.fullmatch('[a-f0-9]{64}', row[key]) for key in ('parent_sha256', 'sha256', 'patch_sha256')):
            raise ValueError('Invalid desktop SDK overlay identity')
        if sha(ROOT / row['source']) != row['sha256'] or sha(ROOT / row['patch']) != row['patch_sha256']:
            raise ValueError('Published desktop SDK overlay differs')
        result[name.casefold()] = row
    return result


def sdk_input_paths(lock, source, names):
    parent = json.loads((ROOT / 'converter.inputs.lock.json').read_text('utf-8'))['sdkjs']
    indexed = {r['file']: r['sha256'] for r in parent['files']}
    overlays = sdk_overlays(lock, parent)
    paths, inputs = {}, {}
    for name in names:
        safe_relative(name)
        if indexed.get(name) != sha(source / name):
            raise ValueError('Desktop SDK fixed parent source differs')
        row = overlays.get(name.casefold())
        paths[name] = ROOT / row['source'] if row else source / name
        inputs[name] = sha(paths[name])
        if inputs[name] != (row['sha256'] if row else indexed[name]):
            raise ValueError('Desktop SDK effective input differs')
    return paths, inputs


def verify_inputs():
    qt = verify_qt_inputs()
    converter = verify_converter_inputs()
    lock = json.loads((ROOT / 'editor.inputs.lock.json').read_text('utf-8'))
    for name in ('converter', 'qt', 'ui'):
        if sha(ROOT / (name + '.inputs.lock.json')) != lock[name + '_input_lock_sha256']:
            raise ValueError('Desktop editor prerequisite lock differs: ' + name)
    upstream = {r['repository']: r for r in json.loads((ROOT / 'upstream.lock.json').read_text('utf-8'))}
    if lock['web_apps']['revision'] != upstream['web-apps']['revision'] or lock['dictionaries']['revision'] != upstream['dictionaries']['revision']:
        raise ValueError('Desktop editor source revision differs from pinned upstream')
    if lock['web_editors'] != EDITORS or set(lock['sdk_profiles']) != set(SDKS):
        raise ValueError('All desktop editor profiles must be retained')
    frozen = {r['file']: r for r in json.loads((ROOT / 'source-manifest.json').read_text('utf-8'))['modified_files'] if r['repository'] == 'web-apps'}
    for family, row in [('web-apps', lock['web_apps']), ('dictionaries', lock['dictionaries']), ('document-templates', lock['templates']), *lock['desktop_resources'].items()]:
        for field in ('archive', 'root'): safe_relative(row[field])
        if not re.fullmatch('[a-f0-9]{40}', row['revision']) or row['root'] != family + '-' + row['revision'] or row['url'] != 'https://codeload.github.com/ONLYOFFICE/' + family + '/zip/' + row['revision']:
            raise ValueError('Unpinned desktop editor archive origin')
        if not re.fullmatch('[a-f0-9]{64}', row['sha256']): raise ValueError('Invalid editor archive hash')
        seen = set()
        for item in row['files']:
            safe_relative(item['file'])
            if item['file'].casefold() in seen or not re.fullmatch('[a-f0-9]{64}', item['sha256']):
                raise ValueError('Duplicate or invalid editor source input')
            seen.add(item['file'].casefold())
            for field, digest in [('source', item['sha256']), ('patch', item.get('patch_sha256'))]:
                if field in item:
                    safe_relative(item[field])
                    if sha(ROOT / item[field]) != digest: raise ValueError('Editor published source or patch differs')
            if family == 'web-apps' and item['file'] in frozen and item['sha256'] != frozen[item['file']]['sha256']:
                if item.get('parent_sha256') != frozen[item['file']]['sha256'] or not item.get('patch') or not item.get('source', '').startswith('editor-sources/'):
                    raise ValueError('Frozen web editor parent identity must remain unchanged')
    sdk_parent = json.loads((ROOT / 'host.inputs.lock.json').read_text('utf-8'))['desktop_sdk']
    for module, parent in [('desktop-apps', qt['desktop_apps']), ('desktop-sdk', sdk_parent)]:
        if any(lock['desktop_resources'][module][key] != parent[key] for key in ('revision', 'url', 'archive', 'root', 'sha256')):
            raise ValueError('Additional desktop resource origin differs from its pinned native source')
    web = {r['file']: r for r in lock['web_apps']['files']}
    if not set(frozen).issubset(web) or any(web[n].get('base_sha256') != r['base_sha256'] for n, r in frozen.items()):
        raise ValueError('Frozen added or modified web source omitted')
    if web['build/package-lock.json']['sha256'] != lock['npm_lock_sha256']:
        raise ValueError('Editor npm lock differs')
    sdk_files = {r['file'] for r in converter['sdkjs']['files']}
    for profile in lock['sdk_profiles'].values():
        for name in profile['min'] + profile['common']:
            safe_relative(name)
            if name not in sdk_files: raise ValueError('Desktop SDK input omitted from fixed SDKJS archive')
    overlays = sdk_overlays(lock, converter['sdkjs'])
    selected = {n.casefold() for p in lock['sdk_profiles'].values() for n in p['min'] + p['common']}
    if not set(overlays).issubset(selected): raise ValueError('Unused desktop SDK overlay')
    for name in lock['sdk_assets']['files'] + lock['sdk_assets']['prefixes'] + [lock['sdk_assets']['stamp_prefix']]:
        safe_relative(name)
    for row in lock['image_tools']:
        if row['package'] not in ('gifsicle', 'jpegtran-bin', 'optipng-bin'):
            raise ValueError('Unexpected native image build tool')
        safe_relative(row['executable'])
    return lock


def state_path(work):
    return work / 'editor-generated-source-state.json'


def read_state(work, lock):
    path = state_path(work)
    if not path.exists(): return {}
    state = json.loads(path.read_text('utf-8'))
    if state['archive_sha256'] != lock['web_apps']['sha256']:
        raise ValueError('Different web editor source identity in generated-state record')
    return state['files']


def materialize(row, destination, archive, generated=None):
    """Preflight every selected member and existing source before materialization, including added frozen files."""
    generated = generated or {}
    indexed = {r['file']: r for r in row['files']}
    pending, members = [], {}
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            safe_relative(member.filename)
            prefix = row['root'] + '/'
            if not member.filename.startswith(prefix):
                if member.filename.rstrip('/') == row['root']: continue
                raise ValueError('Unexpected editor archive root')
            name = member.filename[len(prefix):]
            if name not in indexed: continue
            if name.casefold() in members or stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError('Duplicate or linked editor archive input')
            members[name.casefold()] = member
        for name, item in indexed.items():
            safe_relative(name)
            target = (destination / name).resolve()
            if not target.is_relative_to(destination.resolve()): raise ValueError('Editor destination escapes source directory')
            base = item.get('base_sha256', item['sha256'])
            member = members.get(name.casefold())
            if base is None:
                if member is not None: raise ValueError('Added editor source unexpectedly exists upstream')
                data = b''
            else:
                if member is None: raise ValueError('Selected editor archive input missing')
                data = source.read(member)
                if hashlib.sha256(data).hexdigest() != base: raise ValueError('Editor archive input hash differs')
            if 'source' in item: data = (ROOT / item['source']).read_bytes()
            if hashlib.sha256(data).hexdigest() != item['sha256']: raise ValueError('Editor overlay result differs')
            allowed = {base, item['sha256'], item.get('parent_sha256'), generated.get(name)}
            if target.exists() and sha(target) not in allowed:
                raise ValueError('Unknown editor source edit preserved: ' + name)
            pending.append((target, member, item, data if 'source' in item else None))
        for target, member, item, overlay in pending:
            if target.exists() and sha(target) == item['sha256']: continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(overlay if overlay is not None else source.read(member))


def prepare(lock, work, cache):
    generated = read_state(work, lock)
    source = work / 'sources/web-apps'
    known = {r['file'] for r in lock['web_apps']['files']}
    if source.exists():
        for folder, dirs, files in os.walk(source):
            dirs[:] = [d for d in dirs if d not in ('node_modules', 'deploy', '.git')]
            for filename in files:
                path = Path(folder) / filename
                name = path.relative_to(source).as_posix()
                if name in known: continue
                if name == 'build/qingliang-editors.grunt.js' and sha(path) in {sha(ROOT / 'tools/editor_grunt_hook.js'), generated.get(name)}: continue
                if generated_name(name) and generated.get(name) == sha(path): continue
                raise ValueError('Untracked editor source input preserved: ' + name)
    for row, folder in [(lock['web_apps'], 'web-apps'), (lock['templates'], 'document-templates'),
                        (lock['dictionaries'], 'dictionaries')]:
        materialize(row, work / 'sources' / folder, acquire_archive(row, work, cache), generated if folder == 'web-apps' else None)
    for module, row in lock['desktop_resources'].items():
        materialize(row, work / 'sources' / module, acquire_archive(row, work, cache))
    return prepare_sdk(work, json.loads((ROOT / 'converter.inputs.lock.json').read_text('utf-8')), cache)


def build_sdk(lock, work, source, jar, env, java):
    header = (source / 'build/license.header').read_text('utf-8')
    for a, b in {'@@AppCopyright': 'Copyright (C) Ascensio System SIA 2012-2026. All rights reserved', '@@PublisherUrl': 'https://www.onlyoffice.com/', '@@Version': '9.4.0', '@@Build': '129'}.items(): header = header.replace(a, b)
    externs = json.loads((source / 'configs/externs.json').read_text('utf-8'))['externs']
    results = {}
    for editor in SDKS:
        config = json.loads((source / ('configs/' + editor + '.json')).read_text('utf-8'))['sdk']
        profile = {'min': config['min'] + config['desktop']['min'], 'common': config['common'] + config['desktop']['common']}
        if profile != lock['sdk_profiles'][editor]: raise ValueError('Desktop SDK profile differs')
        minimum, common = profile['min'], profile['common']
        paths, inputs = sdk_input_paths(lock, source, externs + minimum + common)
        target = work / 'bin/editors/sdkjs' / editor
        target.mkdir(parents=True, exist_ok=True)
        arguments = ['-Xmx4096m', '-jar', jar.as_posix()] + ['--externs=' + paths[n].as_posix() for n in externs]
        arguments += ["--define=window.AscCommon.g_cCompanyName='onlyoffice'", "--define=window.AscCommon.g_cProductVersion='9.4.0'", "--define=window.AscCommon.g_cBuildNumber='129'", "--define=window.AscCommon.g_cIsBeta='false'", '--rewrite_polyfills=true', '--warning_level=QUIET', '--language_out=ECMASCRIPT5', '--compilation_level=ADVANCED']
        arguments += ['--js=' + paths[n].as_posix() for n in minimum] + ['--chunk=sdk-all-min:' + str(len(minimum))]
        arguments += ['--js=' + paths[n].as_posix() for n in common] + ['--chunk=sdk-all:' + str(len(common)) + ':sdk-all-min', '--chunk_output_path_prefix=' + target.as_posix() + '/']
        argfile = work / ('desktop-sdk-' + editor + '.rsp')
        argfile.write_text('\n'.join('"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"' for s in arguments), 'utf-8')
        print('Compiling desktop SDK ' + editor, flush=True)
        log = work / ('desktop-sdk-' + editor + '.log')
        execute([java, '@' + str(argfile)], source, env, log)
        outputs = {}
        for name in ['sdk-all-min.js', 'sdk-all.js']:
            path = target / name
            text = path.read_text('utf-8')
            if name == 'sdk-all.js': text = '(function(window, undefined) {' + text + '})(window);'
            path.write_text(header + '\n' + text, 'utf-8')
            execute([shutil.which('node'), '--check', str(path)], source, env, log)
            outputs[name] = sha(path)
        if sdk_input_paths(lock, source, list(inputs))[1] != inputs: raise ValueError('Desktop SDK source changed while compiling')
        results[editor] = {'source_units': len(minimum) + len(common), 'inputs': inputs, 'outputs': outputs, 'profile': 'desktop native API'}
    (work / 'desktop-sdk-build-report.json').write_text(json.dumps(results, indent=2) + '\n', 'utf-8')
    return results


def generated_name(name):
    return re.fullmatch(r'apps/(common|documenteditor|spreadsheeteditor|presentationeditor|pdfeditor|visioeditor)/main/(locale/[^/]+\.json|resources/(img|less)/.+\.(png|svg|less))', name) is not None


def reuse_sdk(lock, work, source):
    """Reuse one prior desktop SDK build only after checking its complete profile, actual inputs and outputs."""
    report = json.loads((work / 'desktop-sdk-build-report.json').read_text('utf-8'))
    if set(report) != set(SDKS): raise ValueError('Build all desktop SDK profiles before reusing them')
    externs = json.loads((source / 'configs/externs.json').read_text('utf-8'))['externs']
    for editor in SDKS:
        config = json.loads((source / ('configs/' + editor + '.json')).read_text('utf-8'))['sdk']
        profile = {'min': config['min'] + config['desktop']['min'], 'common': config['common'] + config['desktop']['common']}
        if profile != lock['sdk_profiles'][editor]: raise ValueError('Desktop SDK reuse profile differs')
        paths, inputs = sdk_input_paths(lock, source, externs + profile['min'] + profile['common'])
        row = report[editor]
        if row['inputs'] != inputs or row['source_units'] != len(profile['min']) + len(profile['common']) or row['profile'] != 'desktop native API':
            raise ValueError('Prior desktop SDK input report differs')
        if set(row['outputs']) != {'sdk-all-min.js', 'sdk-all.js'} or any(sha(work / 'bin/editors/sdkjs' / editor / name) != digest for name, digest in row['outputs'].items()):
            raise ValueError('Prior desktop SDK output differs; rebuild before reuse')
    return report


def audit_web_source(lock, work):
    source = work / 'sources/web-apps'
    indexed = {r['file']: r['sha256'] for r in lock['web_apps']['files']}
    overlays = {r['file'] for r in lock['web_apps']['files'] if 'source' in r}
    generated = {}
    for name, digest in indexed.items():
        actual = sha(source / name)
        if actual != digest:
            if not generated_name(name): raise ValueError('Build changed non-generated editor source: ' + name)
            generated[name] = actual
        elif name in overlays:
            # Preserve the identity of a successfully built overlay so a later published overlay can replace it safely.
            generated[name] = actual
    for folder, dirs, files in os.walk(source):
        dirs[:] = [d for d in dirs if d not in ('node_modules', 'deploy', '.git')]
        for filename in files:
            path = Path(folder) / filename
            name = path.relative_to(source).as_posix()
            if name in indexed: continue
            if name == 'build/qingliang-editors.grunt.js':
                generated[name] = sha(path)
                continue
            if not generated_name(name): raise ValueError('Untracked editor source input preserved: ' + name)
            generated[name] = sha(path)
    return generated


def build_web(lock, work, env, install):
    source, folder = work / 'sources/web-apps', work / 'sources/web-apps/build'
    if install:
        npm = shutil.which('npm.cmd') or shutil.which('npm')
        execute([npm, 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], folder, env, work / 'editor-web-npm.log')
        execute([npm, 'rebuild', 'optipng-bin', 'jpegtran-bin', 'gifsicle', '--foreground-scripts'], folder, env, work / 'editor-image-tools.log')
    if sha(folder / 'package-lock.json') != lock['npm_lock_sha256']: raise ValueError('Editor npm lock changed')
    for row in lock['image_tools']:
        root = folder / 'node_modules' / row['package']
        if json.loads((root / 'package.json').read_text('utf-8'))['version'] != row['version'] or sha(root / row['executable']) != row['sha256']:
            raise ValueError('Native image build tool identity differs')
    execute([sys.executable, 'merge_and_check.py'], source / 'translation', env, work / 'editor-locale-merge.log')
    hook = folder / 'qingliang-editors.grunt.js'
    if hook.exists() and sha(hook) not in {sha(ROOT / 'tools/editor_grunt_hook.js'), read_state(work, lock).get('build/qingliang-editors.grunt.js')}:
        raise ValueError('Unknown existing editor build hook preserved')
    shutil.copy2(ROOT / 'tools/editor_grunt_hook.js', hook)
    indexed = {r['file']: r['sha256'] for r in lock['web_apps']['files']}
    results = {}
    try:
        for editor in ['common'] + EDITORS:
            env['QINGLIANG_EDITOR'] = editor
            config = folder / (editor + '.json')
            before = config.read_bytes()
            tasks = ['deploy-common-component'] if editor == 'common' else ['init-build-' + editor, 'increment-build', 'deploy-app-main']
            print('Building desktop web interface ' + editor, flush=True)
            try:
                execute([shutil.which('node'), str(folder / 'node_modules/grunt/bin/grunt'), '--gruntfile', str(hook), '--desktop', '--no-color'] + tasks,
                        folder, env, work / ('editor-web-' + editor + '.log'))
            finally:
                after = config.read_bytes()
                if after != before:
                    a, b = json.loads(after), json.loads(before)
                    if a.pop('build') != b.pop('build') + 1 or a != b: raise ValueError('Unknown editor build metadata edit preserved')
                    config.write_bytes(before)
            amd = json.loads((work / ('editor-web-amd-' + editor + '.json')).read_text('utf-8'))
            if amd['exit'] != 0 or any(indexed.get(name) != digest for name, digest in amd['inputs'].items()):
                raise ValueError('Desktop AMD input differs from fixed source')
            outputs = {}
            if editor != 'common':
                if 'apps/common/main/lib/controller/Desktop.js' not in amd['inputs']: raise ValueError('Frozen desktop controller omitted')
                for name in ['app.js', 'resources/css/app.css', 'index.html']:
                    outputs[name] = sha(source / 'deploy/web-apps/apps' / editor / 'main' / name)
                for path in (source / 'apps' / editor / 'main/locale').glob('*.json'):
                    if json.loads(path.read_text('utf-8')) != json.loads((source / 'deploy/web-apps/apps' / editor / 'main/locale' / path.name).read_text('utf-8')):
                        raise ValueError('Deployed localization differs from merged source')
            results[editor] = {'amd_inputs': amd['inputs'], 'outputs': outputs, 'desktop_main_profile': True}
        (work / 'editor-web-build-report.json').write_text(json.dumps(results, indent=2) + '\n', 'utf-8')
        return results
    finally:
        generated = audit_web_source(lock, work)
        state_path(work).write_text(json.dumps({'archive_sha256': lock['web_apps']['sha256'], 'files': generated}, indent=2) + '\n', 'utf-8')


def layout(lock, work):
    folder = work / 'bin'
    copies = []
    def copy(source, target, origin):
        digest = sha(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha(target) != digest: shutil.copy2(source, target)
        if sha(target) != digest: raise ValueError('Editor runtime copy differs')
        copies.append({'source': source.relative_to(work).as_posix(), 'target': target.relative_to(work).as_posix(), 'sha256': digest, 'origin': origin})
    native = json.loads((work / 'converter-build-report.json').read_text('utf-8'))
    for name, digest in native['artifacts'].items():
        if sha(folder / name) != digest: raise ValueError('Source-built converter binary changed')
        copy(folder / name, folder / 'converter' / name, 'current source-built converter')
    for name in ['x2t.exe', 'icuuc74.dll', 'icudt74.dll']: copy(folder / name, folder / 'converter' / name, 'current source-built converter')
    web = work / 'sources/web-apps/deploy/web-apps'
    for source in web.rglob('*'):
        if source.is_file(): copy(source, folder / 'editors/web-apps' / source.relative_to(web), 'rebuilt desktop web interface')
    sdk = json.loads((ROOT / 'converter.inputs.lock.json').read_text('utf-8'))['sdkjs']
    assets = lock['sdk_assets']
    for row in sdk['files']:
        name = row['file']
        if name not in assets['files'] and not any(name.startswith(prefix) for prefix in assets['prefixes']) and not (name.startswith(assets['stamp_prefix']) and name.endswith('.json')): continue
        source = work / 'sources/sdkjs' / name
        if sha(source) != row['sha256']: raise ValueError('SDK runtime asset differs')
        copy(source, folder / 'editors/sdkjs' / name, 'fixed SDKJS runtime asset; checked-in WASM not rebuilt')
    for row in lock['templates']['files']:
        name = row['file']
        target = folder / 'converter/empty' / name.removeprefix('new/') if name.startswith('new/') else folder / 'licenses/document-templates' / name
        copy(work / 'sources/document-templates' / name, target, 'fixed Apache-2.0 template')
    for row in lock['dictionaries']['files']: copy(work / 'sources/dictionaries' / row['file'], folder / 'dictionaries' / row['file'], 'fixed dictionary and notices')
    for module, archive in lock['desktop_resources'].items():
        for row in archive['files']:
            name = row['file']
            if name.startswith('ChromiumBasedEditors/resources/local/'): target = folder / 'editors/sdkjs/common/Images/local' / name.removeprefix('ChromiumBasedEditors/resources/local/')
            elif name.startswith('common/templates/'): target = folder / 'converter/templates' / name.removeprefix('common/templates/')
            elif name.startswith('ChromiumBasedEditors/app/install/common/fonts/'): target = folder / 'fonts' / name.removeprefix('ChromiumBasedEditors/app/install/common/fonts/')
            else: raise ValueError('Unexpected desktop resource target')
            copy(work / 'sources' / module / name, target, 'fixed desktop resource')
    for module in ['sdkjs', 'web-apps']:
        for name in ['LICENSE.txt', '3DPARTY.md']: copy(work / 'sources' / module / name, folder / 'licenses' / module / name, 'source license and attribution')
    config = '<Settings>\n<file>../editors/sdkjs/common/Native/native.js</file>\n<file>../editors/sdkjs/common/Native/jquery_native.js</file>\n<allfonts>../editors/sdkjs/common/AllFonts.js</allfonts>\n<file>../editors/web-apps/vendor/xregexp/xregexp-all-min.js</file>\n<sdkjs>../editors/sdkjs</sdkjs>\n<dictionaries>../dictionaries</dictionaries>\n</Settings>\n'
    (folder / 'converter/DoctRenderer.config').write_text(config, 'utf-8')
    (work / 'editor-runtime-layout.json').write_text(json.dumps({'files': copies, 'edit_save_tested': False, 'installer_built': False}, indent=2) + '\n', 'utf-8')
    return copies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'prepare', 'build'))
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--archive-cache', type=Path)
    parser.add_argument('--java', type=Path)
    parser.add_argument('--skip-install', action='store_true', help='Reuse dependencies already installed in this stable directory')
    parser.add_argument('--reuse-sdk', action='store_true', help='Rebuild the web interface while verifying and reusing the existing desktop SDK inputs and outputs')
    args = parser.parse_args()
    lock = verify_inputs()
    if args.command == 'verify':
        print(json.dumps({'ok': True, 'sdk_profiles': SDKS, 'web_editors': EDITORS, 'fixed_web_files': len(lock['web_apps']['files'])})); return
    if not args.work_dir: parser.error('--work-dir is required')
    work = args.work_dir.resolve()
    if work == ROOT or ROOT in work.parents or work in ROOT.parents or not (work / '.qingliang-dependency-build').is_file(): raise ValueError('Use the existing marked stable Qt/host build directory')
    fd = os.open(work / '.build.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        if args.command == 'build' and os.name == 'nt' and (work / 'qt-runtime-launch.json').exists():
            import ctypes
            from ctypes import wintypes as wt
            pid = json.loads((work / 'qt-runtime-launch.json').read_text('utf-8')).get('pid')
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.restype = wt.HANDLE
            kernel.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
            kernel.CloseHandle.argtypes = [wt.HANDLE]
            handle = kernel.OpenProcess(0x1000, False, pid) if pid else None
            if handle:
                try:
                    image = ctypes.create_unicode_buffer(32768)
                    count = wt.DWORD(len(image))
                    if kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(count)) and Path(image.value).resolve() == work / 'bin/DesktopEditors.exe':
                        raise ValueError('Close the owned desktop preview normally before rebuilding its runtime resources')
                finally: kernel.CloseHandle(handle)
        if args.command == 'build': (work / 'editor-build-report.json').unlink(missing_ok=True)
        source, jar = prepare(lock, work, args.archive_cache)
        if args.command == 'prepare': return
        native = json.loads((work / 'qt-build-report.json').read_text('utf-8'))
        if native['input_manifest_sha256'] != lock['qt_input_lock_sha256'] or any(sha(work / row['output']) != row['sha256'] for row in native['artifacts'].values()): raise ValueError('Build the current Qt desktop components first')
        env = dict(os.environ)
        env.update({'TEMP': str(work / 'temp'), 'TMP': str(work / 'temp'), 'npm_config_cache': str(work / 'npm-cache'), 'QINGLIANG_WORK_DIR': str(work), 'SYSTEM_ENCODING': 'utf8', 'PRODUCT_VERSION': '9.4.0', 'BUILD_NUMBER': '129', 'DEFAULT_LANG': 'zh-CN'})
        java = str(args.java or shutil.which('java') or '')
        if not java or not shutil.which('node'): raise ValueError('Java 21 and Node.js are required')
        sdk = reuse_sdk(lock, work, source) if args.reuse_sdk else build_sdk(lock, work, source, jar, env, java)
        web = build_web(lock, work, env, not args.skip_install)
        runtime = layout(lock, work)
        report = {'input_manifest_sha256': sha(ROOT / 'editor.inputs.lock.json'), 'builder_sha256': sha(Path(__file__)), 'grunt_hook_sha256': sha(ROOT / 'tools/editor_grunt_hook.js'),
                  'sdk_profiles': {n: {'units': row['source_units'], 'outputs': row['outputs']} for n, row in sdk.items()}, 'web_editors': {n: {'amd_inputs': len(row['amd_inputs']), 'outputs': row['outputs']} for n, row in web.items()},
                  'runtime_files': len(runtime), 'sdk_reused_after_input_output_verification': args.reuse_sdk,
                  'node_version': subprocess.check_output([shutil.which('node'), '--version'], text=True).strip(),
                  'checked_in_wasm_rebuilt': False, 'plugins_complete': False, 'edit_save_tested': False, 'installer_built': False}
        (work / 'editor-build-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
        print(json.dumps({'runtime_files': len(runtime), 'web_editors': EDITORS, 'edit_save_tested': False}), flush=True)
    finally:
        os.close(fd)
        (work / '.build.lock').unlink()


if __name__ == '__main__':
    main()
