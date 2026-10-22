import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_x2t_dependencies as builder
from build_kernel import prepare_kernel_sources


class X2tDependencyToolTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='x2t-dependency-tool-', dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture_repository(self):
        for name in ['x2t.inputs.lock.json', 'upstream.lock.json']:
            shutil.copyfile(ROOT / name, self.root / name)
        manifest = json.loads((ROOT / 'x2t.inputs.lock.json').read_text('utf-8'))
        for row in manifest['files']:
            if row['origin'] == 'community-overlay':
                for key in ['patch', 'modified_source']:
                    target = self.root / row[key]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / row[key], target)
        return manifest

    def test_different_core_revision_is_rejected(self):
        manifest = self.fixture_repository()
        manifest['revision'] = '0' * 40
        (self.root / 'x2t.inputs.lock.json').write_text(json.dumps(manifest), 'utf-8')
        with patch.object(builder, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'identity differs'):
            builder.verify_x2t_inputs()

    def test_duplicate_compile_units_are_rejected(self):
        manifest = self.fixture_repository()
        manifest['sources'][1] = manifest['sources'][0]
        (self.root / 'x2t.inputs.lock.json').write_text(json.dumps(manifest), 'utf-8')
        with patch.object(builder, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'collision'):
            builder.verify_x2t_inputs()

    def test_modified_boost_input_is_preserved(self):
        source = self.root / 'file.cpp'
        source.write_bytes(b'user modified source')
        lock = {'boost': {'files': [{'file': source.name, 'sha256': '0' * 64}]}}
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            builder.verify_boost_sources(lock, self.root)
        self.assertEqual(source.read_bytes(), b'user modified source')

    def test_published_patch_tampering_is_rejected(self):
        manifest = self.fixture_repository()
        row = next(row for row in manifest['files'] if row['origin'] == 'community-overlay')
        (self.root / row['patch']).write_bytes(b'different patch')
        with patch.object(builder, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'hash mismatch'):
            builder.verify_x2t_inputs()

    def test_patches_reconstruct_exact_pinned_originals_and_results(self):
        manifest = builder.verify_x2t_inputs()
        rows = [row for row in manifest['files'] if row['origin'] == 'community-overlay']
        work = self.root / 'work'
        core = work / 'sources/core'
        core.mkdir(parents=True)
        subprocess.run(['git', 'init', '--quiet', str(core)], check=True)
        for row in rows:
            target = core / row['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / row['modified_source'], target)
            subprocess.run(['git', '-c', 'core.autocrlf=false', '-C', str(core), 'apply', '-R', str(ROOT / row['patch'])], check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), row['base_sha256'])
        prepare_kernel_sources({'files': rows, 'revision': manifest['revision']}, work)
        for row in rows:
            self.assertEqual((core / row['file']).read_bytes(), (ROOT / row['modified_source']).read_bytes())

    def test_changed_kernel_binary_is_not_reused(self):
        (self.root / 'bin').mkdir()
        entries = {'kernel.dll': 'kernel_dll_sha256', 'kernel.lib': 'kernel_import_library_sha256',
                   'UnicodeConverter.dll': 'unicode_converter_dll_sha256', 'icuuc74.dll': 'icu_common_dll_sha256',
                   'icudt74.dll': 'icu_data_dll_sha256'}
        report = {'native_tests': {'passed': 22, 'failed': 0},
                  'kernel_input_manifest_sha256': hashlib.sha256((ROOT / 'kernel.inputs.lock.json').read_bytes()).hexdigest()}
        for name, key in entries.items():
            (self.root / 'bin' / name).write_bytes(name.encode())
            report[key] = hashlib.sha256(name.encode()).hexdigest()
        (self.root / 'kernel-build-report.json').write_text(json.dumps(report), 'utf-8')
        self.assertTrue(builder.kernel_current(self.root))
        (self.root / 'bin/kernel.dll').write_bytes(b'different binary')
        self.assertFalse(builder.kernel_current(self.root))


if __name__ == '__main__':
    unittest.main()
