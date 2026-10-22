import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import prepare_sources
from verify_sources import safe_relative, verify

def digest(data):
    return hashlib.sha256(data).hexdigest()

class SourceToolTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='source-tool-', dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def git(self, *args):
        return subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'user.name=Source tool fixture',
                               '-c', 'user.email=fixture@example.invalid', '-C', str(self.root), *args],
                              check=True, capture_output=True)

    def repository(self):
        self.git('init', '--quiet')
        (self.root / 'sample.txt').write_bytes(b'base\n')
        self.git('add', 'sample.txt')
        self.git('commit', '--quiet', '-m', 'Fixture baseline')

    def source_fixture(self):
        source = self.root / 'sources/sdkjs/sample.js'
        source.parent.mkdir(parents=True)
        source.write_bytes(b'changed\n')
        patch = self.root / 'patches/sdkjs.patch'
        patch.parent.mkdir()
        patch.write_bytes(b'diff --git a/sample.js b/sample.js\n--- a/sample.js\n+++ b/sample.js\n@@ -1 +1 @@\n-base\n+changed\n')
        (self.root / 'historical-build').mkdir()
        (self.root / 'historical-build/manifest.json').write_text('[]', 'utf-8')
        (self.root / 'upstream.lock.json').write_text(json.dumps([
            {'repository': 'sdkjs', 'revision': 'a' * 40, 'url': 'https://github.com/ONLYOFFICE/sdkjs'}]), 'utf-8')
        manifest = {'modified_files': [{'repository': 'sdkjs', 'file': 'sample.js', 'sha256': digest(source.read_bytes()),
                                        'base_sha256': digest(b'base\n')}],
                    'patch_sha256': {'sdkjs': digest(patch.read_bytes())}}
        (self.root / 'source-manifest.json').write_text(json.dumps(manifest), 'utf-8')
        return source, patch

    def test_clean_repository_is_accepted(self):
        self.repository()
        prepare_sources.check_changes(self.root, [])

    def test_expected_overlay_is_accepted(self):
        self.repository()
        data = b'published modification\n'
        (self.root / 'sample.txt').write_bytes(data)
        prepare_sources.check_changes(self.root, [{'file': 'sample.txt', 'sha256': digest(data)}])

    def test_unknown_edit_is_preserved(self):
        self.repository()
        data = b'local work must survive\n'
        path = self.root / 'sample.txt'
        path.write_bytes(data)
        with self.assertRaises(RuntimeError):
            prepare_sources.check_changes(self.root, [])
        self.assertEqual(path.read_bytes(), data)

    def test_staged_edit_is_preserved(self):
        self.repository()
        path = self.root / 'sample.txt'
        path.write_bytes(b'staged local work\n')
        self.git('add', 'sample.txt')
        with self.assertRaises(RuntimeError):
            prepare_sources.check_changes(self.root, [])
        self.assertEqual(path.read_bytes(), b'staged local work\n')

    def test_unknown_untracked_file_is_preserved(self):
        self.repository()
        path = self.root / 'private.txt'
        path.write_bytes(b'local fixture only\n')
        with self.assertRaises(RuntimeError):
            prepare_sources.check_changes(self.root, [])
        self.assertEqual(path.read_bytes(), b'local fixture only\n')

    def test_deleted_file_is_rejected(self):
        self.repository()
        (self.root / 'sample.txt').unlink()
        with self.assertRaises(RuntimeError):
            prepare_sources.check_changes(self.root, [])

    def test_expected_new_overlay_file_is_accepted(self):
        self.repository()
        data = b'new source\n'
        (self.root / 'new.txt').write_bytes(data)
        prepare_sources.check_changes(self.root, [{'file': 'new.txt', 'sha256': digest(data)}])

    def test_valid_source_fixture(self):
        self.source_fixture()
        _, manifest, groups = verify(self.root)
        self.assertEqual(len(manifest['modified_files']), 1)
        self.assertEqual(groups, {'sdkjs': {'sample.js'}})

    def test_source_tampering_is_detected(self):
        source, _ = self.source_fixture()
        source.write_bytes(b'corruption\n')
        with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
            verify(self.root)

    def test_patch_hunk_tampering_is_detected(self):
        _, patch = self.source_fixture()
        patch.write_bytes(patch.read_bytes().replace(b'+changed', b'+corrupt'))
        with self.assertRaisesRegex(ValueError, 'Patch hash mismatch'):
            verify(self.root)

    def test_unlisted_source_is_rejected(self):
        source, _ = self.source_fixture()
        source.with_name('unexpected.js').write_bytes(b'extra\n')
        with self.assertRaisesRegex(ValueError, 'Unlisted source'):
            verify(self.root)

    def test_unexpected_upstream_is_rejected(self):
        self.source_fixture()
        path = self.root / 'upstream.lock.json'
        data = json.loads(path.read_text('utf-8'))
        data[0]['url'] = 'https://example.invalid/unexpected'
        path.write_text(json.dumps(data), 'utf-8')
        with self.assertRaisesRegex(ValueError, 'Unexpected upstream'):
            verify(self.root)

    def test_unsafe_paths_are_rejected(self):
        for name in ['../file', '/absolute', 'C:/file', 'parent\\file']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_relative(name)

if __name__ == '__main__':
    unittest.main()
