import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_desktop


class DesktopCompilerAuditTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='desktop-audit-', dir=parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'unit.cxx').write_bytes(b'code')
        (self.source / 'header.hxx').write_bytes(b'header')
        self.lock = {'hunspell': {'files': [
            {'file': name, 'sha256': hashlib.sha256((self.source / name).read_bytes()).hexdigest()}
            for name in ('unit.cxx', 'header.hxx')], 'patches': []}, 'sources': ['unit.cxx']}
        self.env = {'VCTOOLSINSTALLDIR': str(self.root / 'msvc'), 'WINDOWSSDKDIR': str(self.root / 'sdk')}
        self.record = self.root / 'unit.deps.json'

    def audit(self, includes, source=None):
        self.record.write_text(json.dumps({'Data': {
            'Source': str(source or self.source / 'unit.cxx'), 'Includes': [str(p) for p in includes]}}), 'utf-8-sig')
        return build_desktop.audit_inputs([self.record], self.source, self.lock, self.env)

    def test_bom_json_and_separate_toolchain_inputs(self):
        result = self.audit([self.source / 'header.hxx', self.root / 'msvc/include/vector'])
        self.assertEqual(result['locked_inputs_read'], ['header.hxx', 'unit.cxx'])
        self.assertEqual(result['toolchain_headers'], 1)

    def test_modified_locked_header_rejected_without_overwrite(self):
        header = self.source / 'header.hxx'
        header.write_bytes(b'user edit')
        with self.assertRaisesRegex(ValueError, 'modified Hunspell'):
            self.audit([header])
        self.assertEqual(header.read_bytes(), b'user edit')

    def test_unpinned_header_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unpinned input'):
            self.audit([self.root / 'old-office/include/unknown.hxx'])

    def test_neighbor_of_toolchain_directory_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unpinned input'):
            self.audit([self.root / 'msvc-other/include/vector'])

    def test_omitted_source_dependency_record_rejected(self):
        with self.assertRaisesRegex(ValueError, 'omit a native source'):
            build_desktop.audit_inputs([], self.source, self.lock, self.env)


if __name__ == '__main__':
    unittest.main()
