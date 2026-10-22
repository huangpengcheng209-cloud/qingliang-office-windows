"""Validate the published source overlay, lock file and cumulative patch paths."""
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def safe_relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '\\' in value or ':' in value:
        raise ValueError(f'Unsafe relative path: {value}')
    return path

def verify(root=ROOT):
    lock = json.loads((root / 'upstream.lock.json').read_text('utf-8'))
    manifest = json.loads((root / 'source-manifest.json').read_text('utf-8'))
    indexed = {x['repository']: x for x in lock}
    if len(indexed) != len(lock):
        raise ValueError('Duplicate upstream repository')
    for module, row in indexed.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]+', module) or not re.fullmatch(r'[a-f0-9]{40}', row['revision']):
            raise ValueError('Invalid upstream identity')
        expected = 'https://github.com/' + ('google/brotli' if module == 'brotli' else 'ONLYOFFICE/' + module)
        if row['url'] != expected:
            raise ValueError('Unexpected upstream URL')
    groups = {}
    seen = set()
    for row in manifest['modified_files']:
        module, name = row['repository'], row['file']
        if module not in indexed or (module, name) in seen:
            raise ValueError('Unknown module or duplicate source')
        safe_relative(name)
        seen.add((module, name))
        if sha(root / 'sources' / module / name) != row['sha256']:
            raise ValueError(f'Source hash mismatch: {module}/{name}')
        groups.setdefault(module, set()).add(name)
    actual = {(p.relative_to(root / 'sources').parts[0], '/'.join(p.relative_to(root / 'sources').parts[1:]))
              for p in (root / 'sources').rglob('*') if p.is_file()}
    if actual != seen:
        raise ValueError('Unlisted source files')
    patch_hashes = manifest['patch_sha256']
    if set(patch_hashes) != set(groups):
        raise ValueError('Patch hash module mismatch')
    for module, expected in groups.items():
        patch = root / 'patches' / (module + '.patch')
        if sha(patch) != patch_hashes[module]:
            raise ValueError(f'Patch hash mismatch: {module}')
        data = patch.read_text('utf-8')
        paths = set(re.findall(r'^diff --git a/(.+) b/\1$', data, re.M))
        if paths != expected:
            raise ValueError(f'Patch/source path mismatch: {module}')
    for row in json.loads((root / 'historical-build/manifest.json').read_text('utf-8')):
        name = row['archive_path'].removeprefix('windows-build/')
        safe_relative(name)
        if sha(root / 'historical-build' / name) != row['sha256']:
            raise ValueError(f'Historical input hash mismatch: {name}')
    return lock, manifest, groups

if __name__ == '__main__':
    lock, manifest, groups = verify()
    print(json.dumps({'modified_files': len(manifest['modified_files']), 'patches': len(groups), 'locked_upstreams': len(lock), 'ok': True}))
