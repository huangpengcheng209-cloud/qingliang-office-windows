"""Fetch pinned upstream source and apply the verified overlay in an explicit target."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from verify_sources import ROOT, verify

def run(repo, *args, capture=False):
    return subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.longpaths=true', '-C', str(repo), *args],
                          check=True, stdout=subprocess.PIPE if capture else None,
                          text=capture, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})

def output(repo, *args):
    return run(repo, *args, capture=True).stdout.strip()

def destination(target, module):
    parent = target / 'upstream'
    return parent / module if module in ('DesktopEditors', 'build_tools', 'brotli') else parent / 'DesktopEditors' / module

def check_changes(repo, rows):
    expected = {x['file']: x for x in rows}
    changed = output(repo, 'diff', '--name-only', '--ignore-submodules=all', 'HEAD').splitlines()
    untracked = output(repo, 'ls-files', '--others', '--exclude-standard').splitlines()
    for name in set(changed + untracked):
        path = repo / name
        if name not in expected or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected[name]['sha256']:
            raise RuntimeError(f'Refusing unknown local change: {repo.name}/{name}')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path, help='Explicit source working directory; use a separate D: cache directory on Windows.')
    args = parser.parse_args()
    lock, manifest, groups = verify()
    target = args.target.resolve()
    if target == ROOT or target in ROOT.parents or ROOT in target.parents:
        raise RuntimeError('Target must be outside this published repository')
    indexed = {x['repository']: x for x in lock}
    ordered = ['DesktopEditors'] + [x['repository'] for x in lock if x['repository'] != 'DesktopEditors']
    # Complete all identity/local-change checks before applying any project patch.
    for module in ordered:
        row = indexed[module]
        repo = destination(target, module)
        if not repo.resolve().is_relative_to(target):
            raise RuntimeError('Repository path escapes the selected target')
        repo.mkdir(parents=True, exist_ok=True)
        if not (repo / '.git').exists():
            if any(repo.iterdir()):
                raise RuntimeError(f'Refusing nonempty non-repository directory: {repo}')
            subprocess.run(['git', 'init', str(repo)], check=True)
            run(repo, 'config', 'core.autocrlf', 'false')
            run(repo, 'config', 'core.longpaths', 'true')
            run(repo, 'remote', 'add', 'origin', row['url'])
        if output(repo, 'remote', 'get-url', 'origin').removesuffix('.git').rstrip('/') != row['url']:
            raise RuntimeError(f'Unexpected origin for {module}')
        head = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--verify', 'HEAD'], capture_output=True, text=True)
        if head.returncode:
            run(repo, 'fetch', '--depth=1', 'origin', row['revision'])
            run(repo, 'checkout', '--detach', row['revision'])
        elif head.stdout.strip() != row['revision']:
            raise RuntimeError(f'Unexpected existing commit for {module}; use a separate target')
        if output(repo, 'rev-parse', 'HEAD') != row['revision']:
            raise RuntimeError(f'Pinned commit mismatch for {module}')
        check_changes(repo, [x for x in manifest['modified_files'] if x['repository'] == module])
        print(f'Pinned {module}: {row["revision"]}', flush=True)
    for module in sorted(groups):
        repo = destination(target, module)
        rows = [x for x in manifest['modified_files'] if x['repository'] == module]
        complete = all((repo / x['file']).is_file() and hashlib.sha256((repo / x['file']).read_bytes()).hexdigest() == x['sha256'] for x in rows)
        if not complete:
            # Partial or different modifications never get overwritten.
            for row in rows:
                path = repo / row['file']
                current = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
                if current != row['base_sha256']:
                    raise RuntimeError(f'Partial overlay; refusing to overwrite {module}/{row["file"]}')
            patch = str(ROOT / 'patches' / (module + '.patch'))
            run(repo, 'apply', '--check', '--whitespace=nowarn', patch)
            run(repo, 'apply', '--whitespace=nowarn', patch)
        for row in rows:
            if hashlib.sha256((repo / row['file']).read_bytes()).hexdigest() != row['sha256']:
                raise RuntimeError(f'Applied source mismatch: {module}/{row["file"]}')
        print(f'Verified {module}: {len(rows)} modified files', flush=True)
    print(json.dumps({'ok': True, 'target': str(target), 'modified_files': len(manifest['modified_files']), 'build_performed': False}))

if __name__ == '__main__':
    main()
