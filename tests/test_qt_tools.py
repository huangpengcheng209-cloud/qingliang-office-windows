import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_qt


class QtSourcePreparationTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='qt-input-', dir=parent)
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.archive = self.work / 'source.zip'
        self.destination = self.work / 'source'
        self.row = {'root': 'source-pin', 'files': [{'file': 'a.h', 'sha256': hashlib.sha256(b'original').hexdigest()}]}

    def zip(self, entries):
        with zipfile.ZipFile(self.archive, 'w') as z:
            for name, data in entries:
                z.writestr(name, data)

    def test_traversal_is_rejected_before_any_write(self):
        self.zip([('source-pin/a.h', b'original'), ('source-pin/../../outside', b'escape')])
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            build_qt.materialize(self.row, self.destination, self.archive)
        self.assertFalse(self.destination.exists())

    def test_unknown_source_edit_is_preserved(self):
        self.zip([('source-pin/a.h', b'original')])
        self.destination.mkdir()
        (self.destination / 'a.h').write_bytes(b'user edit')
        with self.assertRaisesRegex(ValueError, 'Unknown Qt source edit preserved'):
            build_qt.materialize(self.row, self.destination, self.archive)
        self.assertEqual((self.destination / 'a.h').read_bytes(), b'user edit')

    def test_late_hash_failure_does_not_partially_write(self):
        self.zip([('source-pin/a.h', b'original'), ('source-pin/b.h', b'wrong')])
        self.row['files'].append({'file': 'b.h', 'sha256': hashlib.sha256(b'expected').hexdigest()})
        with self.assertRaisesRegex(ValueError, 'source hash differs'):
            build_qt.materialize(self.row, self.destination, self.archive)
        self.assertFalse(self.destination.exists())

    def test_archive_links_are_rejected(self):
        with zipfile.ZipFile(self.archive, 'w') as z:
            member = zipfile.ZipInfo('source-pin/a.h')
            member.create_system = 3
            member.external_attr = 0o120777 << 16
            z.writestr(member, b'original')
        with self.assertRaisesRegex(ValueError, 'linked Qt archive member'):
            build_qt.materialize(self.row, self.destination, self.archive)
        self.assertFalse(self.destination.exists())

    def test_published_qt_patches_reconstruct_exact_parent_bytes(self):
        lock = build_qt.verify_inputs()
        for row in lock['desktop_apps']['files']:
            if 'patch' not in row: continue
            folder = self.work / row['file'].replace('/', '_')
            target = folder / row['file']
            target.parent.mkdir(parents=True)
            target.write_bytes((ROOT / row['source']).read_bytes())
            subprocess.run(['git', 'init', '--quiet', str(folder)], check=True)
            command = ['git', '-c', 'core.autocrlf=false', '-C', str(folder), 'apply', '--whitespace=nowarn']
            subprocess.run(command + ['--reverse', '--check', str(ROOT / row['patch'])], check=True)
            subprocess.run(command + ['--reverse', str(ROOT / row['patch'])], check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), row['parent_sha256'])
            subprocess.run(command + ['--check', str(ROOT / row['patch'])], check=True)
            subprocess.run(command + [str(ROOT / row['patch'])], check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), row['sha256'])


if __name__ == '__main__':
    unittest.main()
