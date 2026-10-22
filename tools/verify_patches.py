"""Verify patches against selected pinned upstream files without cloning full source trees."""
import argparse
import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from verify_sources import ROOT, verify

MARKER = '.qingliang-selected-base-cache'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def download(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'qingliang-source-check'})
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)

def verify_patches(cache):
    lock, manifest, groups = verify()
    indexed = {row['repository']: row for row in lock}
    cache = cache.resolve()
    if cache == ROOT or cache in ROOT.parents or ROOT in cache.parents:
        raise ValueError('Select a cache outside the published repository')
    marker = cache / MARKER
    if cache.exists() and any(cache.iterdir()) and not marker.is_file():
        raise ValueError('Refusing to reuse an unrecognized nonempty directory')
    cache.mkdir(parents=True, exist_ok=True)
    marker.write_text('Selected source files only; no complete upstream checkout.\n', 'utf-8')
    blobs = cache / 'blobs'
    blobs.mkdir(exist_ok=True)
    rows = manifest['modified_files']

    def get_base(row):
        expected = row['base_sha256']
        if expected is None:
            return
        blob = blobs / expected
        if blob.exists():
            if sha(blob.read_bytes()) != expected:
                raise ValueError('Corrupt cached upstream base')
            return
        module = indexed[row['repository']]
        owner_repo = module['url'].removeprefix('https://github.com/')
        name = urllib.parse.quote(row['file'], safe='/')
        url = f'https://raw.githubusercontent.com/{owner_repo}/{module["revision"]}/{name}'
        data = download(url)
        if sha(data) != expected:
            raise ValueError(f'Pinned upstream byte mismatch: {row["repository"]}/{row["file"]}')
        blob.write_bytes(data)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(get_base, rows))
    count = 0
    for module in sorted(groups):
        folder = cache / 'work' / module
        folder.mkdir(parents=True, exist_ok=True)
        if not folder.resolve().is_relative_to(cache):
            raise ValueError('Cache path escapes selected directory')
        if not (folder / '.git').exists():
            subprocess.run(['git', 'init', '--quiet', str(folder)], check=True)
        expected_paths = {row['file'] for row in rows if row['repository'] == module}
        for path in folder.rglob('*'):
            if path.is_file() and '.git' not in path.relative_to(folder).parts:
                if path.relative_to(folder).as_posix() not in expected_paths:
                    raise ValueError(f'Unexpected file in selected-base workspace: {path.name}')
        module_rows = [row for row in rows if row['repository'] == module]
        # Reuse one selected-file workspace; restore only known base/result bytes.
        for row in module_rows:
            path = folder / row['file']
            if path.exists() and (not path.is_file() or sha(path.read_bytes()) not in (row['base_sha256'], row['sha256'])):
                raise ValueError(f'Unknown local content in selected-base workspace: {row["file"]}')
        for row in module_rows:
            path = folder / row['file']
            if row['base_sha256'] is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((blobs / row['base_sha256']).read_bytes())
        command = ['git', '-c', 'core.autocrlf=false', '-C', str(folder), 'apply', '--whitespace=nowarn']
        patch = str(ROOT / 'patches' / (module + '.patch'))
        subprocess.run(command + ['--check', patch], check=True)
        subprocess.run(command + [patch], check=True)
        for row in module_rows:
            if sha((folder / row['file']).read_bytes()) != row['sha256']:
                raise ValueError(f'Patch result mismatch: {module}/{row["file"]}')
            count += 1
        print(f'{module}: {len(module_rows)} patch result files verified', flush=True)
    result = {'ok': True, 'modified_files_verified': count, 'patches_verified': len(groups),
              'upstream_base_files': sum(row['base_sha256'] is not None for row in rows), 'build_performed': False}
    (cache / 'result.json').write_text(json.dumps(result, indent=2), 'utf-8')
    print(json.dumps(result))
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path, help='Explicit disposable directory for selected upstream files.')
    verify_patches(parser.parse_args().cache)
