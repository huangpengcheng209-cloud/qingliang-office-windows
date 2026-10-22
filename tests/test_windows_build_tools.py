import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_windows import discover_vs, engine_audit, owned_work_directory

class WindowsBuildToolTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='windows-build-tool-', dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_unknown_work_contents_are_preserved(self):
        path = self.root / 'existing-work'
        path.mkdir()
        file = path / 'keep.txt'
        file.write_bytes(b'keep local work')
        with self.assertRaisesRegex(ValueError, 'unrecognized'):
            owned_work_directory(path)
        self.assertEqual(file.read_bytes(), b'keep local work')

    def test_owned_work_directory_can_be_reused(self):
        path = self.root / 'owned'
        self.assertEqual(owned_work_directory(path), path.resolve())
        self.assertEqual(owned_work_directory(path), path.resolve())

    def test_repository_cannot_be_build_directory(self):
        for path in [ROOT, ROOT / 'artifacts', ROOT.parent]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                owned_work_directory(path)

    def test_missing_compiler_setup_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'vcvarsall'):
            discover_vs(self.root)

    def test_empty_engine_reports_missing_inputs_without_writing(self):
        source = self.root / 'empty-engine'
        source.mkdir()
        report = engine_audit(source)
        self.assertEqual(report['missing_file_inputs'], 8)
        self.assertFalse(report['full_app_build_ready'])
        self.assertFalse(report['build_performed'])
        self.assertEqual(list(source.iterdir()), [])

    def test_archive_audit_does_not_extract(self):
        archive = self.root / 'frozen.zip'
        with zipfile.ZipFile(archive, 'w') as stream:
            stream.writestr('upstream/core/Common/kernel.pro', 'fixture')
        report = engine_audit(source_archive=archive)
        self.assertEqual(report['input_kind'], 'archive')
        self.assertEqual(report['missing_file_inputs'], 7)
        self.assertEqual(set(p.name for p in self.root.iterdir()), {'frozen.zip'})

    def test_ambiguous_engine_input_is_rejected(self):
        with self.assertRaises(ValueError):
            engine_audit()
        with self.assertRaises(ValueError):
            engine_audit(self.root, source_archive=self.root / 'frozen.zip')

    def test_prepared_dependencies_remain_distinct_from_source_inputs(self):
        source = self.root / 'empty-source'
        source.mkdir()
        dependencies = self.root / 'dependency-build'
        for name in ['sources/boost/boost_1_72_0/boost/version.hpp',
                     'sources/icu/icu/source/common/unicode/utypes.h', 'bin/UnicodeConverter.lib']:
            path = dependencies / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
        report = engine_audit(source, dependency_work_dir=dependencies)
        self.assertEqual(report['missing_file_inputs'], 5)
        prepared = [row for row in report['checks'] if row.get('prepared_dependency_available')]
        self.assertEqual(len(prepared), 3)
        self.assertTrue(all(not row['source_input_available'] for row in prepared))
        self.assertFalse(report['full_app_build_ready'])
        self.assertFalse(report['prepared_dependency_wired_into_full_engine'])

if __name__ == '__main__':
    unittest.main()
