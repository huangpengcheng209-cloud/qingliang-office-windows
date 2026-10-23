import hashlib
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_editors


class EditorSourcePreparationTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='editor-input-', dir=parent)
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.archive = self.work / 'source.zip'
        self.destination = self.work / 'source'
        self.row = {'root': 'source-pin', 'files': [{'file': 'a.h', 'sha256': hashlib.sha256(b'original').hexdigest()}]}

    def zip(self, entries):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name, data in entries: archive.writestr(name, data)

    def test_added_overlay_absent_from_archive_is_materialized(self):
        self.zip([('source-pin/a.h', b'original')])
        repo = self.work / 'repo'
        repo.mkdir()
        (repo / 'added.h').write_bytes(b'added frozen source')
        self.row['files'].append({'file': 'added.h', 'base_sha256': None, 'source': 'added.h',
                                  'sha256': hashlib.sha256(b'added frozen source').hexdigest()})
        with patch.object(build_editors, 'ROOT', repo):
            build_editors.materialize(self.row, self.destination, self.archive)
        self.assertEqual((self.destination / 'added.h').read_bytes(), b'added frozen source')

    def test_added_source_unexpectedly_present_upstream_is_rejected(self):
        self.zip([('source-pin/a.h', b'original')])
        self.row['files'][0]['base_sha256'] = None
        with self.assertRaisesRegex(ValueError, 'unexpectedly exists upstream'):
            build_editors.materialize(self.row, self.destination, self.archive)
        self.assertFalse(self.destination.exists())

    def test_unknown_source_edit_is_preserved(self):
        self.zip([('source-pin/a.h', b'original')])
        self.destination.mkdir()
        (self.destination / 'a.h').write_bytes(b'user edit')
        with self.assertRaisesRegex(ValueError, 'Unknown editor source edit preserved'):
            build_editors.materialize(self.row, self.destination, self.archive)
        self.assertEqual((self.destination / 'a.h').read_bytes(), b'user edit')

    def test_late_archive_hash_failure_does_not_partially_write(self):
        self.zip([('source-pin/a.h', b'original'), ('source-pin/b.h', b'wrong')])
        self.row['files'].append({'file': 'b.h', 'sha256': hashlib.sha256(b'expected').hexdigest()})
        with self.assertRaisesRegex(ValueError, 'archive input hash differs'):
            build_editors.materialize(self.row, self.destination, self.archive)
        self.assertFalse(self.destination.exists())

    def test_traversal_is_rejected_before_any_write(self):
        self.zip([('source-pin/a.h', b'original'), ('source-pin/../../outside', b'escape')])
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            build_editors.materialize(self.row, self.destination, self.archive)
        self.assertFalse(self.destination.exists())

    def test_editor_patches_reconstruct_fixed_parent_and_completed_result(self):
        lock = build_editors.verify_inputs()
        for row in lock['web_apps']['files']:
            if 'patch' not in row: continue
            folder = self.work / row['file'].split('/')[1]
            target = folder / row['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / row['source']).read_bytes())
            subprocess.run(['git', 'init', '--quiet', str(folder)], check=True)
            command = ['git', '-c', 'core.autocrlf=false', '-C', str(folder), 'apply', '--whitespace=nowarn']
            subprocess.run(command + ['--reverse', '--check', str(ROOT / row['patch'])], check=True)
            subprocess.run(command + ['--reverse', str(ROOT / row['patch'])], check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), row['parent_sha256'])
            subprocess.run(command + ['--check', str(ROOT / row['patch'])], check=True)
            subprocess.run(command + [str(ROOT / row['patch'])], check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), row['sha256'])

    def test_frozen_overlay_parent_cannot_be_redefined(self):
        lock = copy.deepcopy(build_editors.verify_inputs())
        row = next(r for r in lock['web_apps']['files'] if r.get('origin') == 'quality-overlay-on-frozen')
        row['parent_sha256'] = '0' * 64
        original = json.loads
        def substitute(text, *args, **kwargs):
            value = original(text, *args, **kwargs)
            return lock if isinstance(value, dict) and 'web_editors' in value else value
        with patch.object(build_editors.json, 'loads', side_effect=substitute), self.assertRaisesRegex(ValueError, 'Frozen web editor parent'):
            build_editors.verify_inputs()

    def test_sdk_reuse_rejects_changed_binary_without_overwriting_it(self):
        source, repo = self.work / 'sdkjs', self.work / 'repo'
        (source / 'configs').mkdir(parents=True)
        repo.mkdir()
        (source / 'a.js').write_bytes(b'fixed source')
        (source / 'configs/externs.json').write_text('{"externs":[]}', 'utf-8')
        (repo / 'converter.inputs.lock.json').write_text(json.dumps({'sdkjs': {'files': [{'file': 'a.js', 'sha256': hashlib.sha256(b'fixed source').hexdigest()}]}}), 'utf-8')
        report, profiles = {}, {}
        for editor in build_editors.SDKS:
            (source / ('configs/' + editor + '.json')).write_text('{"sdk":{"min":["a.js"],"common":[],"desktop":{"min":[],"common":[]}}}', 'utf-8')
            profiles[editor] = {'min': ['a.js'], 'common': []}
            folder = self.work / 'bin/editors/sdkjs' / editor
            folder.mkdir(parents=True)
            outputs = {}
            for name in ['sdk-all.js', 'sdk-all-min.js']:
                (folder / name).write_bytes(b'prior build')
                outputs[name] = hashlib.sha256(b'prior build').hexdigest()
            report[editor] = {'source_units': 1, 'profile': 'desktop native API', 'inputs': {'a.js': hashlib.sha256(b'fixed source').hexdigest()}, 'outputs': outputs}
        (self.work / 'desktop-sdk-build-report.json').write_text(json.dumps(report), 'utf-8')
        changed = self.work / 'bin/editors/sdkjs/word/sdk-all.js'
        changed.write_bytes(b'unknown changed output')
        with patch.object(build_editors, 'ROOT', repo), self.assertRaisesRegex(ValueError, 'Prior desktop SDK output differs'):
            build_editors.reuse_sdk({'sdk_profiles': profiles}, self.work, source)
        self.assertEqual(changed.read_bytes(), b'unknown changed output')


if __name__ == '__main__':
    unittest.main()
