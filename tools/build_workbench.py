"""Prepare and build the actual pinned desktop start page plus the quality overlay."""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path
from build_dependencies import acquire_archive, sha
from verify_sources import ROOT, safe_relative, verify


def verify_ui_inputs():
    verify()
    lock = json.loads((ROOT / 'ui.inputs.lock.json').read_text('utf-8'))
    row = lock['upstream']
    fixed = next(r for r in json.loads((ROOT / 'upstream.lock.json').read_text('utf-8')) if r['repository'] == 'desktop-apps')
    if row['revision'] != fixed['revision'] or row['repository'] != fixed['url']:
        raise ValueError('UI upstream differs from source lock')
    if row['url'] != 'https://codeload.github.com/ONLYOFFICE/desktop-apps/zip/' + fixed['revision']:
        raise ValueError('Unpinned UI archive URL')
    safe_relative(row['archive'])
    if row['root'] != 'desktop-apps-' + row['revision'] or not re.fullmatch('[a-f0-9]{64}', row['sha256']):
        raise ValueError('Invalid UI archive identity')
    seen = set()
    frozen = {r['file']: r for r in json.loads((ROOT / 'source-manifest.json').read_text('utf-8'))['modified_files'] if r['repository'] == 'desktop-apps'}
    for item in row['files']:
        safe_relative(item['file'])
        if item['file'].casefold() in seen or not re.fullmatch('[a-f0-9]{64}', item['sha256']):
            raise ValueError('Duplicate or invalid UI input')
        seen.add(item['file'].casefold())
        if 'frozen_source' in item:
            safe_relative(item['frozen_source'])
            old = frozen[item['file']]
            if item['sha256'] != old['base_sha256'] or item['frozen_sha256'] != old['sha256'] or sha(ROOT / item['frozen_source']) != old['sha256']:
                raise ValueError('UI frozen parent differs')
    files = {r['file']: r for r in row['files']}
    seen = set()
    for item in lock['overlays']:
        for key in ('file', 'source', 'patch'):
            safe_relative(item[key])
        if item['file'] in seen:
            raise ValueError('Duplicate UI overlay')
        seen.add(item['file'])
        parent = files.get(item['file'], {})
        if item['parent_sha256'] != parent.get('frozen_sha256', parent.get('sha256')):
            raise ValueError('UI overlay parent differs')
        if sha(ROOT / item['source']) != item['sha256'] or sha(ROOT / item['patch']) != item['patch_sha256']:
            raise ValueError('UI overlay hash differs')
    actual = {p.relative_to(ROOT / 'ui-sources/desktop-apps').as_posix() for p in (ROOT / 'ui-sources/desktop-apps').rglob('*') if p.is_file()}
    if actual != seen:
        raise ValueError('Unlisted UI source')
    return lock


def prepare_ui(lock, work):
    row = lock['upstream']
    archive = acquire_archive(row, work, None)
    source = work / 'sources/desktop-apps'
    overlays = {r['file']: r for r in lock['overlays']}
    original_hashes = {r['file']: r['sha256'] for r in row['files']}
    previous = work / 'workbench-build-report.json'
    previous_report = json.loads(previous.read_text('utf-8')) if previous.exists() else {}
    generated = previous_report.get('generated_source_files', {})
    old_inputs = {}
    old_lock = work / 'workbench-built-input-lock.json'
    if old_lock.is_file() and sha(old_lock) == previous_report.get('input_manifest_sha256'):
        old = json.loads(old_lock.read_text('utf-8'))
        old_inputs = {r['file']: r.get('frozen_sha256', r['sha256']) for r in old['upstream']['files']}
        old_inputs.update({r['file']: r['sha256'] for r in old['overlays']})
    pending = []
    with zipfile.ZipFile(archive) as z:
        wanted = {(row['root'] + '/' + item['file']).casefold() for item in row['files']}
        selected = set()
        for info in z.infolist():
            safe_relative(info.filename)
            if info.filename.casefold() in wanted:
                if info.filename.casefold() in selected or stat.S_ISLNK(info.external_attr >> 16) or info.is_dir():
                    raise ValueError('Duplicate or linked UI source archive input')
                selected.add(info.filename.casefold())
        for item in row['files']:
            relative = item['file']
            target = source / relative
            if not target.resolve().is_relative_to(source.resolve()):
                raise ValueError('UI target escapes work directory')
            data = z.read(row['root'] + '/' + relative)
            if hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError('UI archive source hash differs')
            allowed = {item['sha256'], item.get('frozen_sha256'), overlays.get(relative, {}).get('sha256'), generated.get(relative), old_inputs.get(relative)}
            if target.exists() and sha(target) not in allowed:
                raise ValueError('Unknown UI edit preserved: ' + relative)
            if 'frozen_source' in item:
                data = (ROOT / item['frozen_source']).read_bytes()
            pending.append((target, data))
        for relative, item in overlays.items():
            target = source / relative
            if not target.resolve().is_relative_to(source.resolve()):
                raise ValueError('UI overlay escapes source directory')
            if target.exists() and sha(target) not in {item['parent_sha256'], item['sha256'], original_hashes.get(relative), generated.get(relative), old_inputs.get(relative)}:
                raise ValueError('Unknown UI overlay edit preserved: ' + relative)
    for target, data in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for relative, item in overlays.items():
        if item['parent_sha256'] is None and (source / relative).exists() and sha(source / relative) != item['sha256']:
            # A recognized prior generated overlay is upgraded only after every preflight passes.
            (source / relative).write_bytes((ROOT / item['source']).read_bytes())
    if not (source / '.git').exists():
        subprocess.run(['git', 'init', '--quiet', str(source)], check=True)
    for item in lock['overlays']:
        target = source / item['file']
        if target.exists() and sha(target) == item['sha256']:
            continue
        command = ['git', '-c', 'core.autocrlf=false', '-C', str(source), 'apply', '--whitespace=nowarn']
        subprocess.run(command + ['--check', str(ROOT / item['patch'])], check=True)
        subprocess.run(command + [str(ROOT / item['patch'])], check=True)
        if sha(target) != item['sha256']:
            raise ValueError('Applied UI patch differs')
    return source


def run_build(lock, work, source, install=True):
    from build_windows import execute
    folder = source / 'common/loginpage/build'
    env = dict(os.environ)
    env['TEMP'] = env['TMP'] = str(work / 'temp')
    (work / 'temp').mkdir(exist_ok=True)
    env['npm_config_cache'] = str(work / 'npm-cache')
    npm = shutil.which('npm.cmd') or shutil.which('npm')
    node = shutil.which('node')
    if not npm or not node:
        raise ValueError('Node.js and npm are required')
    log = work / 'workbench-build.log'
    (work / 'workbench-build-report.json').unlink(missing_ok=True)
    if install:
        execute([npm, 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], folder, env, log)
    cli = folder / 'node_modules/grunt-cli/bin/grunt'
    if not cli.is_file():
        cli = folder / 'node_modules/grunt/bin/grunt'
    execute([node, str(cli)], folder, env, log)
    output = source / 'common/loginpage/deploy/index.html'
    if not output.is_file():
        raise ValueError('Start page output is missing')
    report = {'input_manifest_sha256': sha(ROOT / 'ui.inputs.lock.json'), 'upstream_revision': lock['upstream']['revision'],
              'node_version': subprocess.check_output([node, '--version'], text=True).strip(),
              'npm_lock_sha256': sha(folder / 'package-lock.json'), 'index_html_sha256': sha(output),
              'generated_source_files': {}, 'desktop_host_built': False, 'native_bridge_tested': False}
    final = {r['file']: r['sha256'] for r in lock['upstream']['files']}
    final.update({r['file']: r.get('frozen_sha256', r['sha256']) for r in lock['upstream']['files']})
    final.update({r['file']: r['sha256'] for r in lock['overlays']})
    for relative, expected in final.items():
        actual = sha(source / relative)
        if actual != expected:
            if not re.fullmatch(r'common/loginpage/src/css/toolicons(?:20)?@[\d.]+x.less', relative):
                raise ValueError('Build unexpectedly changed locked source: ' + relative)
            report['generated_source_files'][relative] = actual
    (work / 'workbench-build-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    (work / 'workbench-built-input-lock.json').write_bytes((ROOT / 'ui.inputs.lock.json').read_bytes())
    print(json.dumps({'output': str(output), 'sha256': report['index_html_sha256'], 'generated_sprite_styles': len(report['generated_source_files']), 'desktop_host_built': False}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'build', 'prepare'))
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--skip-install', action='store_true', help='Reuse the toolchain already installed in this same build directory')
    args = parser.parse_args()
    lock = verify_ui_inputs()
    if args.command == 'verify':
        print(json.dumps({'ok': True, 'source_inputs': len(lock['upstream']['files']), 'overlays': len(lock['overlays'])}))
        return
    if not args.work_dir:
        parser.error('--work-dir is required')
    work = args.work_dir.resolve()
    if work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise ValueError('Use an external stable build directory')
    marker = work / '.qingliang-dependency-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():
        raise ValueError('Unknown nonempty work directory')
    work.mkdir(parents=True, exist_ok=True)
    marker.write_text('One stable community build workspace.\n', 'utf-8')
    guard = work / '.build.lock'
    fd = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
        source = prepare_ui(lock, work)
        if args.command == 'build':
            run_build(lock, work, source, not args.skip_install)
    finally:
        os.close(fd)
        guard.unlink()


if __name__ == '__main__':
    main()
