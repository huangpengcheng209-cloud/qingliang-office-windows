import hashlib
import os
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_host


class HostSourcePreparationTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='host-input-', dir=parent)
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.archive = self.work / 'source.zip'
        self.destination = self.work / 'source'
        self.row = {'root':'source-pin', 'files':[{'file':'a.h', 'sha256':hashlib.sha256(b'original').hexdigest()}]}

    def zip(self, entries):
        with zipfile.ZipFile(self.archive, 'w') as z:
            for name, data in entries:
                z.writestr(name, data)

    def test_traversal_is_rejected_before_any_write(self):
        self.zip([('source-pin/a.h', b'original'), ('source-pin/../../outside', b'escape')])
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            build_host.materialize(self.row, self.destination, self.archive)
        self.assertFalse(self.destination.exists())

    def test_unknown_local_source_edit_is_preserved(self):
        self.zip([('source-pin/a.h', b'original')])
        self.destination.mkdir()
        (self.destination/'a.h').write_bytes(b'user edit')
        with self.assertRaisesRegex(ValueError, 'Unknown existing host source edit preserved'):
            build_host.materialize(self.row, self.destination, self.archive)
        self.assertEqual((self.destination/'a.h').read_bytes(), b'user edit')

    def test_all_selected_hashes_checked_before_materialization(self):
        self.zip([('source-pin/a.h', b'original'), ('source-pin/b.h', b'wrong')])
        self.row['files'].append({'file':'b.h','sha256':hashlib.sha256(b'expected').hexdigest()})
        with self.assertRaisesRegex(ValueError, 'member hash differs'):
            build_host.materialize(self.row, self.destination, self.archive)
        self.assertFalse(self.destination.exists())

    def test_source_module_escape_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            build_host.source_path(self.work, '@core/../../outside.h')

    def test_host_patches_reconstruct_exact_originals_and_results(self):
        lock = build_host.verify_host_inputs()
        for family in ('desktop_sdk', 'cef_source'):
            for row in lock[family]['files']:
                if 'patch' not in row:continue
                folder = self.work / family
                target = folder / row['file']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / row['modified_source']).read_bytes())
                subprocess.run(['git','init','--quiet',str(folder)],check=True)
                command = ['git','-c','core.autocrlf=false','-C',str(folder),'apply','--whitespace=nowarn']
                subprocess.run(command+['--reverse','--check',str(ROOT / row['patch'])],check=True)
                subprocess.run(command+['--reverse',str(ROOT / row['patch'])],check=True)
                parent = row.get('frozen_parent_sha256', row['base_sha256'])
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), parent)
                subprocess.run(command+['--check',str(ROOT / row['patch'])],check=True)
                subprocess.run(command+[str(ROOT / row['patch'])],check=True)
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), row['sha256'])


if __name__ == '__main__':
    unittest.main()
