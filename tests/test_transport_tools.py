import json
import os
import shutil
import sys
import tempfile
import hashlib
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_transport


class TransportToolTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='transport-tool-', dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lock = json.loads((ROOT / 'transport.inputs.lock.json').read_text('utf-8'))
        for name in ('transport.inputs.lock.json', 'upstream.lock.json'):
            shutil.copyfile(ROOT / name, self.root / name)
        for row in self.lock['files']:
            if row['origin'] == 'community-overlay':
                for key in ('patch', 'modified_source'):
                    target = self.root / row[key]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / row[key], target)

    def changed(self):
        (self.root / 'transport.inputs.lock.json').write_text(json.dumps(self.lock), 'utf-8')

    def test_different_core_revision_is_rejected(self):
        self.lock['revision'] = '0' * 40
        self.changed()
        with patch.object(build_transport, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'identity differs'):
            build_transport.verify_transport_inputs()

    def test_duplicate_compile_unit_is_rejected(self):
        sources = self.lock['profiles']['crypto']['sources']
        sources[1] = sources[0]
        self.changed()
        with patch.object(build_transport, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'compile units'):
            build_transport.verify_transport_inputs()

    def test_unpinned_unit_is_rejected(self):
        self.lock['profiles']['network']['sources'][0] = 'unlisted.cpp'
        self.changed()
        with patch.object(build_transport, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'Unpinned'):
            build_transport.verify_transport_inputs()

    def test_unsafe_include_path_is_rejected(self):
        self.lock['profiles']['network']['include_directories'].append('../../outside')
        self.changed()
        with patch.object(build_transport, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'Unsafe'):
            build_transport.verify_transport_inputs()

    def test_source_hash_change_is_rejected(self):
        self.lock['files'][0]['sha256'] = 'not-a-sha256'
        self.changed()
        with patch.object(build_transport, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'invalid source hash'):
            build_transport.verify_transport_inputs()

    def test_transfer_patch_reconstructs_pinned_original_and_result(self):
        from build_kernel import prepare_kernel_sources
        rows = [row for row in self.lock['files'] if row['origin'] == 'community-overlay']
        self.assertTrue(rows)
        work = self.root / 'build'
        core = work / 'sources/core'
        core.mkdir(parents=True)
        subprocess.run(['git', 'init', '--quiet', str(core)], check=True)
        for row in rows:
            target = core / row['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / row['modified_source'], target)
            subprocess.run(['git', '-c', 'core.autocrlf=false', '-C', str(core), 'apply', '-R', str(ROOT / row['patch'])], check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), row['base_sha256'])
        prepare_kernel_sources({'revision': self.lock['revision'], 'files': rows}, work)
        for row in rows:
            self.assertEqual((core / row['file']).read_bytes(), (ROOT / row['modified_source']).read_bytes())


if __name__ == '__main__':
    unittest.main()
