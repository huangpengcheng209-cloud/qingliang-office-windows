"""Protect local acceptance fixtures before any controlled output is replaced."""
import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from run_editor_tests import Acceptance, ROOT, sha
from run_spreadsheet_tests import SpreadsheetAcceptance
from run_presentation_tests import PresentationAcceptance
from run_pdf_tests import PdfAcceptance, EmptyPdfAcceptance


class AcceptanceFixtureTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='editor-fixtures-', dir=parent)
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)

    def assert_late_unknown_edit_preserves_earlier_output(self, kind, marker, report):
        args = Namespace(work_dir=self.work, qt_dir=self.work, evidence_dir=self.work / 'evidence')
        session = kind(args)
        session.source.parent.mkdir(parents=True)
        (session.evidence / marker).write_text('owned acceptance directory', 'utf-8')
        session.source.write_bytes(b'unchanged source fixture')
        session.edited.write_bytes(b'previous known output')
        known = {p.relative_to(session.evidence).as_posix(): sha(p) for p in (session.source, session.edited)}
        session.created.write_bytes(b'unknown user change')
        record = session.evidence / report
        record.write_text(json.dumps({'owned_fixtures': known}), 'utf-8')
        before = record.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Unknown.*fixture edit preserved'):
            session.fixtures()
        self.assertEqual(session.edited.read_bytes(), b'previous known output')
        self.assertEqual(session.created.read_bytes(), b'unknown user change')
        self.assertEqual(record.read_bytes(), before)
        self.assertFalse(session.fixtures_ready)

    def test_docx_fixture_preflight_preserves_all_files_on_late_unknown_edit(self):
        self.assert_late_unknown_edit_preserves_earlier_output(Acceptance, '.qingliang-editor-acceptance', 'editor-test-result.json')

    def test_xlsx_fixture_preflight_preserves_all_files_on_late_unknown_edit(self):
        self.assert_late_unknown_edit_preserves_earlier_output(SpreadsheetAcceptance, '.qingliang-spreadsheet-acceptance', 'spreadsheet-test-result.json')

    def test_pptx_fixture_preflight_preserves_all_files_on_late_unknown_edit(self):
        self.assert_late_unknown_edit_preserves_earlier_output(PresentationAcceptance, '.qingliang-presentation-acceptance', 'presentation-test-result.json')

    def test_pdf_fixture_preflight_preserves_all_files_on_late_unknown_edit(self):
        self.assert_late_unknown_edit_preserves_earlier_output(PdfAcceptance, '.qingliang-pdf-acceptance', 'pdf-test-result.json')

    def test_empty_pdf_fixture_preflight_preserves_all_files_on_late_unknown_edit(self):
        self.assert_late_unknown_edit_preserves_earlier_output(EmptyPdfAcceptance, '.qingliang-pdf-empty-acceptance', 'pdf-empty-field-result.json')
