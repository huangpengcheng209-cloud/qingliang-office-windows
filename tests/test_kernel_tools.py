import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_kernel


class KernelToolTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='kernel-tool-', dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'build'
        self.cache = self.root / 'readonly-cache'
        self.cache.mkdir()

    def manifest(self, name='module/source.cpp', data=b'pinned source\n'):
        return {'revision': 'a' * 40, 'files': [
            {'file': name, 'sha256': hashlib.sha256(data).hexdigest(), 'origin': 'pinned-upstream'}]}

    def test_verified_sources_are_reused_without_network_or_cache_changes(self):
        manifest = self.manifest()
        source = self.cache / manifest['files'][0]['file']
        source.parent.mkdir()
        source.write_bytes(b'pinned source\n')
        with patch.object(build_kernel, 'download', side_effect=AssertionError('Unexpected network')):
            for _ in range(2):
                core = build_kernel.prepare_kernel_sources(manifest, self.work, self.cache)
        self.assertEqual((core / 'module/source.cpp').read_bytes(), source.read_bytes())
        self.assertEqual(source.read_bytes(), b'pinned source\n')

    def test_unknown_existing_source_is_preserved(self):
        target = self.work / 'sources/core/module/source.cpp'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'user changes')
        with self.assertRaisesRegex(ValueError, 'Unknown existing'):
            build_kernel.prepare_kernel_sources(self.manifest(), self.work)
        self.assertEqual(target.read_bytes(), b'user changes')

    def test_traversal_is_rejected_before_download(self):
        with patch.object(build_kernel, 'download') as download:
            with self.assertRaises(ValueError):
                build_kernel.prepare_kernel_sources(self.manifest('../../escape.cpp'), self.work)
        download.assert_not_called()
        self.assertFalse((self.work / 'escape.cpp').exists())

    def test_corrupt_download_is_not_written(self):
        with patch.object(build_kernel, 'download', return_value=b'tampered'):
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                build_kernel.prepare_kernel_sources(self.manifest(), self.work)
        self.assertFalse((self.work / 'sources/core/module/source.cpp').exists())

    def test_corrupt_external_cache_is_preserved(self):
        source = self.cache / 'module/source.cpp'
        source.parent.mkdir()
        source.write_bytes(b'unknown local cache')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            build_kernel.prepare_kernel_sources(self.manifest(), self.work, self.cache)
        self.assertEqual(source.read_bytes(), b'unknown local cache')

    def test_symlink_parent_cannot_redirect_source_writes(self):
        outside = self.root / 'outside'
        outside.mkdir()
        core = self.work / 'sources/core'
        core.mkdir(parents=True)
        try:
            (core / 'module').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('Creating symlinks requires Windows developer mode or privilege')
        with self.assertRaisesRegex(ValueError, 'escapes'):
            build_kernel.prepare_kernel_sources(self.manifest(), self.work)
        self.assertEqual(list(outside.iterdir()), [])

    def test_published_patches_apply_to_exact_upstream_bytes(self):
        manifest = build_kernel.verify_kernel_inputs()
        rows = [row for row in manifest['files'] if row['origin'] == 'community-overlay']
        # Reconstruct small original fixtures by reversing the published patches.
        core = self.work / 'sources/core'
        core.mkdir(parents=True)
        import subprocess
        subprocess.run(['git', 'init', '--quiet', str(core)], check=True)
        for row in rows:
            target = core / row['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / row['modified_source'], target)
            subprocess.run(['git', '-c', 'core.autocrlf=false', '-C', str(core), 'apply', '-R',
                            str(ROOT / row['patch'])], check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), row['base_sha256'])
        with patch.object(build_kernel, 'download', side_effect=AssertionError('Unexpected network')):
            build_kernel.prepare_kernel_sources({'revision': manifest['revision'], 'files': rows}, self.work)
        for row in rows:
            self.assertEqual((core / row['file']).read_bytes(), (ROOT / row['modified_source']).read_bytes())

    def test_changed_published_patch_is_rejected(self):
        fake = self.root / 'repository'
        fake.mkdir()
        manifest = json.loads((ROOT / 'kernel.inputs.lock.json').read_text('utf-8'))
        for name in ['kernel.inputs.lock.json', 'upstream.lock.json']:
            shutil.copyfile(ROOT / name, fake / name)
        for row in manifest['files']:
            if row['origin'] == 'community-overlay':
                for key in ['patch', 'modified_source']:
                    destination = fake / row[key]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / row[key], destination)
        row = next(row for row in manifest['files'] if row['origin'] == 'community-overlay')
        with (fake / row['patch']).open('ab') as output:
            output.write(b'tampering')
        with patch.object(build_kernel, 'ROOT', fake), self.assertRaisesRegex(ValueError, 'hash differs'):
            build_kernel.verify_kernel_inputs()


if __name__ == '__main__':
    unittest.main()
