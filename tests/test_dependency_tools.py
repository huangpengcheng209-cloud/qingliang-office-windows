import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_dependencies import acquire_archive, checked_member, extract_source

class DependencyToolTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='dependency-tool-', dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def row(self, archive):
        return {'url': 'https://example.invalid/fixture.zip', 'archive': archive.name, 'format': 'zip',
                'root': 'icu', 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}

    def test_archive_traversal_is_rejected(self):
        archive = self.root / 'unsafe.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('../escaped.txt', b'not allowed')
        with self.assertRaises(ValueError):
            extract_source(self.row(archive), archive, self.root / 'extract')
        self.assertFalse((self.root / 'escaped.txt').exists())

    def test_zip_symlink_is_rejected(self):
        archive = self.root / 'link.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            item = zipfile.ZipInfo('icu/link')
            item.create_system = 3
            item.external_attr = (0o120777 << 16)
            output.writestr(item, '../escape')
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            extract_source(self.row(archive), archive, self.root / 'extract')

    def test_existing_extraction_contents_are_preserved(self):
        archive = self.root / 'valid.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('icu/test.txt', b'upstream')
        destination = self.root / 'existing'
        destination.mkdir()
        local = destination / 'local.txt'
        local.write_bytes(b'local work')
        with self.assertRaisesRegex(ValueError, 'unknown extraction'):
            extract_source(self.row(archive), archive, destination)
        self.assertEqual(local.read_bytes(), b'local work')

    def test_verified_zip_source_can_be_reused(self):
        archive = self.root / 'valid.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('icu/test.txt', b'upstream')
        row = self.row(archive)
        destination = self.root / 'extract'
        self.assertEqual(extract_source(row, archive, destination), destination / 'icu')
        self.assertEqual(extract_source(row, archive, destination), destination / 'icu')
        self.assertEqual((destination / 'icu/test.txt').read_bytes(), b'upstream')

    def test_changed_source_identity_is_rejected(self):
        archive = self.root / 'valid.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('icu/test.txt', b'upstream')
        row = self.row(archive)
        destination = self.root / 'extract'
        extract_source(row, archive, destination)
        row['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Different source identity'):
            extract_source(row, archive, destination)

    def test_corrupt_external_archive_is_preserved(self):
        external = self.root / 'external'
        external.mkdir()
        archive = external / 'source.zip'
        archive.write_bytes(b'keep corrupt input for inspection')
        row = {'archive': archive.name, 'sha256': '0' * 64}
        with self.assertRaisesRegex(ValueError, 'Archive hash mismatch'):
            acquire_archive(row, self.root / 'work', external)
        self.assertEqual(archive.read_bytes(), b'keep corrupt input for inspection')

    def test_archive_paths_are_normalized_and_checked(self):
        self.assertEqual(str(checked_member('icu\\source\\test.h')), 'icu/source/test.h')
        for name in ['../file', 'icu/../../file', '/absolute', 'C:\\escape']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                checked_member(name)

if __name__ == '__main__':
    unittest.main()
