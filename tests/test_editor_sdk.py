"""Check desktop-only SDK overlays without changing the converter's fixed source tree."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_editors


class EditorSdkTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        folder = tempfile.TemporaryDirectory(prefix='editor-sdk-', dir=parent)
        self.addCleanup(folder.cleanup)
        self.work = Path(folder.name)

    def test_actual_pdf_font_method_preserves_sync_and_async_input_contracts(self):
        subprocess.run(['node', str(ROOT / 'tests/ui/pdf_font_loading_fixture.js'),
                        str(ROOT / 'editor-sources/sdkjs/pdf/src/document.js')], check=True, capture_output=True)

    def test_sdk_overlay_patch_reconstructs_fixed_parent_and_completed_source(self):
        lock = build_editors.verify_inputs()
        for row in lock['sdk_overlays']:
            target = self.work / row['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / row['source']).read_bytes())
            subprocess.run(['git', 'init', '--quiet', str(self.work)], check=True)
            command = ['git', '-c', 'core.autocrlf=false', '-C', str(self.work), 'apply', '--whitespace=nowarn']
            subprocess.run(command + ['--reverse', str(ROOT / row['patch'])], check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), row['parent_sha256'])
            subprocess.run(command + [str(ROOT / row['patch'])], check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), row['sha256'])

    def test_sdk_overlay_cannot_redefine_fixed_converter_parent(self):
        lock = copy.deepcopy(build_editors.verify_inputs())
        lock['sdk_overlays'][0]['parent_sha256'] = '0' * 64
        parent = json.loads((ROOT / 'converter.inputs.lock.json').read_text('utf-8'))['sdkjs']
        with self.assertRaisesRegex(ValueError, 'overlay parent differs'):
            build_editors.sdk_overlays(lock, parent)

    def test_sdk_input_substitution_preserves_parent_and_rejects_unknown_edits(self):
        repo, source = self.work / 'repo', self.work / 'source'
        repo.mkdir(); source.mkdir()
        (source / 'a.js').write_bytes(b'fixed parent')
        overlay = repo / 'editor-sources/sdkjs/a.js'
        overlay.parent.mkdir(parents=True); overlay.write_bytes(b'modified desktop input')
        diff = repo / 'editor-patches/a.patch'; diff.parent.mkdir(); diff.write_bytes(b'retained patch')
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        parent = {'files':[{'file':'a.js','sha256':digest(source / 'a.js')}]}
        (repo / 'converter.inputs.lock.json').write_text(json.dumps({'sdkjs':parent}), 'utf-8')
        lock = {'sdk_overlays':[{'file':'a.js','parent_sha256':digest(source / 'a.js'), 'sha256':digest(overlay),
            'source':'editor-sources/sdkjs/a.js','patch':'editor-patches/a.patch','patch_sha256':digest(diff)}]}
        with patch.object(build_editors, 'ROOT', repo):
            paths, inputs = build_editors.sdk_input_paths(lock, source, ['a.js'])
            self.assertEqual(paths['a.js'], overlay)
            self.assertEqual(inputs['a.js'], digest(overlay))
            self.assertEqual((source / 'a.js').read_bytes(), b'fixed parent')
            (source / 'a.js').write_bytes(b'unknown user edit')
            with self.assertRaisesRegex(ValueError, 'fixed parent source differs'):
                build_editors.sdk_input_paths(lock, source, ['a.js'])
            self.assertEqual((source / 'a.js').read_bytes(), b'unknown user edit')
