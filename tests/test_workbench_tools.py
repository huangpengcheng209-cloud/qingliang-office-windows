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
import build_workbench


class WorkbenchSourcePreparationTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='workbench-source-', dir=parent)
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        (self.work / 'archives').mkdir()
        self.archive = self.work / 'archives/source.zip'
        self.lock = {'upstream': {'archive': 'source.zip', 'root': 'desktop-pin',
                                'files': [{'file': 'a.js', 'sha256': hashlib.sha256(b'original').hexdigest()}]}, 'overlays': []}

    def archive_with(self, entries):
        with zipfile.ZipFile(self.archive, 'w') as z:
            for name, contents in entries:
                z.writestr(name, contents)
        self.lock['upstream']['sha256'] = hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def test_traversal_fails_before_any_source_write(self):
        self.archive_with([('desktop-pin/a.js', b'original'), ('desktop-pin/../../outside', b'escape')])
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            build_workbench.prepare_ui(self.lock, self.work)
        self.assertFalse((self.work / 'sources').exists())

    def test_case_colliding_selected_archive_paths_rejected(self):
        self.archive_with([('desktop-pin/a.js', b'original'), ('desktop-pin/A.js', b'other')])
        with self.assertRaisesRegex(ValueError, 'Duplicate or linked'):
            build_workbench.prepare_ui(self.lock, self.work)
        self.assertFalse((self.work / 'sources').exists())

    def test_unknown_local_edit_preserved(self):
        self.archive_with([('desktop-pin/a.js', b'original')])
        source = self.work / 'sources/desktop-apps/a.js'
        source.parent.mkdir(parents=True)
        source.write_bytes(b'user edit')
        with self.assertRaisesRegex(ValueError, 'Unknown UI edit preserved'):
            build_workbench.prepare_ui(self.lock, self.work)
        self.assertEqual(source.read_bytes(), b'user edit')

    def test_locked_source_hash_checked_before_materialization(self):
        self.archive_with([('desktop-pin/a.js', b'tampered')])
        with self.assertRaisesRegex(ValueError, 'source hash differs'):
            build_workbench.prepare_ui(self.lock, self.work)
        self.assertFalse((self.work / 'sources').exists())

    def test_modified_prior_generated_source_is_preserved(self):
        self.archive_with([('desktop-pin/a.js', b'original')])
        source = self.work / 'sources/desktop-apps/a.js'
        source.parent.mkdir(parents=True)
        source.write_bytes(b'user edit')
        (self.work / 'workbench-build-report.json').write_text(json.dumps({'generated_source_files': {'a.js': hashlib.sha256(b'generated').hexdigest()}}), 'utf-8')
        with self.assertRaisesRegex(ValueError, 'Unknown UI edit preserved'):
            build_workbench.prepare_ui(self.lock, self.work)
        self.assertEqual(source.read_bytes(), b'user edit')


if __name__ == '__main__':
    unittest.main()
