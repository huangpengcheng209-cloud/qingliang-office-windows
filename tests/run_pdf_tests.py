"""Verify real Qt/CEF PDF forms, native save/reopen and Save As with independent readers.

Uses Chromium input, not native Windows IME. The empty-field cycle is a separate selectable suite.
"""
import argparse
import json
import os
import shutil
from pathlib import Path
from run_editor_tests import Acceptance, ROOT, owned_dialog, sha


def create_pdf(path):
    import fitz
    with fitz.open() as document:
        page = document.new_page(width=612, height=792)
        page.insert_text((54, 65), 'Qingliang PDF form acceptance', fontsize=22, color=(.08, .19, .34))
        page.insert_text((54, 95), '表单填写、保存与重开验收', fontname='china-s', fontsize=16)
        for y, label in [(145, 'Name'), (225, 'City'), (305, 'Accept terms'), (385, 'Read-only record')]:
            page.insert_text((54, y), label, fontsize=13)
        for name, kind, rect, value in [
            ('contact', fitz.PDF_WIDGET_TYPE_TEXT, (54, 157, 430, 193), 'Original name'),
            ('city', fitz.PDF_WIDGET_TYPE_COMBOBOX, (54, 237, 270, 273), 'Beijing'),
            ('accepted', fitz.PDF_WIDGET_TYPE_CHECKBOX, (54, 317, 77, 340), 'Off'),
            ('record', fitz.PDF_WIDGET_TYPE_TEXT, (54, 397, 430, 433), 'Read only')]:
            widget = fitz.Widget()
            widget.field_name, widget.field_type, widget.rect, widget.field_value = name, kind, fitz.Rect(rect), value
            widget.text_font, widget.text_fontsize = 'Helv', 14
            widget.border_width, widget.border_color, widget.fill_color = 1, (.25, .4, .65), (.95, .97, 1)
            if name == 'city': widget.choice_values = ['Beijing', 'Shanghai', 'Shenzhen']
            if name == 'record': widget.field_flags = fitz.PDF_FIELD_IS_READ_ONLY
            page.add_widget(widget)
        page = document.new_page(width=612, height=792)
        page.insert_text((54, 65), 'Second page - retained content', fontsize=20)
        page.insert_text((54, 105), 'Independent PDF fixture. No private data.', fontsize=14)
        document.save(path)


def read_pdf(path):
    import fitz
    with fitz.open(path) as document:
        fields, text = {}, []
        for index, page in enumerate(document):
            text.append(page.get_text())
            for widget in page.widgets():
                fields[widget.field_name] = {'value': widget.field_value, 'type': widget.field_type,
                    'flags': widget.field_flags, 'page': index, 'choices': widget.choice_values,
                    'rect': list(widget.rect)}
        return {'pages': len(document), 'fields': fields, 'text': text}


class PdfAcceptance(Acceptance):
    def __init__(self, args):
        super().__init__(args)
        self.source = self.evidence / 'fixtures/source.pdf'
        self.edited = self.evidence / 'fixtures/表单 工作副本.pdf'
        self.created = self.evidence / 'fixtures/另存表单.PDF'
        self.marker = '表单填写 Native PDF 2026'
        self.new_marker = 'New field content'
        self.new_name = None
        self.fixture_marker = '.qingliang-pdf-acceptance'
        self.fixture_report = 'pdf-test-result.json'

    def fixtures(self):
        marker = self.evidence / self.fixture_marker
        if self.evidence.exists() and any(self.evidence.iterdir()) and not marker.exists():
            raise ValueError('Select an empty evidence directory or a marked PDF acceptance directory')
        self.evidence.mkdir(parents=True, exist_ok=True)
        marker.write_text('Only controlled PDF acceptance fixtures and evidence.\n', 'utf-8')
        self.source.parent.mkdir(exist_ok=True)
        result = self.evidence / self.fixture_report
        known = json.loads(result.read_text('utf-8')).get('owned_fixtures', {}) if result.exists() else {}
        for path in (self.source, self.edited, self.created):
            if path.exists() and sha(path) != known.get(path.relative_to(self.evidence).as_posix()):
                raise ValueError('Unknown fixture edit preserved: ' + path.name)
        for path in (self.edited, self.created):
            if path.exists(): path.unlink()
        if not self.source.exists(): create_pdf(self.source)
        shutil.copy2(self.source, self.edited)
        self.original_hash = sha(self.source)
        self.fixtures_ready = True

    def connect(self, playwright):
        browser = playwright.chromium.connect_over_cdp('http://127.0.0.1:' + str(self.port))
        page = next(p for c in browser.contexts for p in c.pages if '/apps/api/documents/' in p.url)
        page.set_default_timeout(7000)
        page.on('pageerror', lambda error: self.errors.append(str(error)))
        for attempt in range(140):
            frame = next((f for f in page.frames if '/pdfeditor/main/' in f.url), None)
            if frame and frame.evaluate('(()=>{try{return PDFE.getController("Main")._isDocReady && editor.getCountPages()===2 && editor.GetAllFieldsNames().length>=4 && !!document.querySelector(".ql-quickbar")}catch{return false}})()'):
                frame.locator('.ql-quickbar').wait_for(state='visible')
                return browser, page, frame
            page.wait_for_timeout(200)
        raise AssertionError('The real PDF editor did not finish opening its forms')

    def fields(self, frame):
        return frame.evaluate('Object.fromEntries(AscBuilder.Pdf.Api.GetDocument().GetAllFields().map(f=>[f.GetFullName(),f.GetValue()]))')

    def field_point(self, frame, name, page_number=0, arrow=False):
        return frame.evaluate('''({name,page,arrow})=>{const r=AscBuilder.Pdf.Api.GetDocument().GetFieldByName(name).GetAllWidgets()[0].GetRect();
            const p=AscPDF.GetGlobalCoordsByPageCoords(arrow?r[2]-6:(r[0]+r[2])/2,(r[1]+r[3])/2,page);
            return {x:p.X,y:p.Y};}''', {'name': name, 'page': page_number, 'arrow': arrow})

    def value_is(self, frame, name, value):
        frame.wait_for_function('([name,value])=>AscBuilder.Pdf.Api.GetDocument().GetFieldByName(name).GetValue()===value', arg=[name, value])

    def select_text(self, page, frame, expected):
        # Clicking an unvisited field can asynchronously load its font and defer native focus.
        # Wait for an actual keyboard selection in that field instead of assuming click means ready.
        for attempt in range(70):
            page.keyboard.press('Control+A')
            if frame.evaluate('editor.asc_GetSelectedText(false,{})').strip() == expected: return
            page.wait_for_timeout(100)
        raise AssertionError('The native PDF field did not expose the expected selected text')

    def settle_view(self, page, frame):
        previous, stable = None, 0
        for attempt in range(30):
            page.wait_for_timeout(50)
            current = frame.evaluate('({scroll:editor.getCurScroll(),zoom:PDFE.getController("Statusbar").getZoom()})')
            stable = stable + 1 if current == previous else 0
            previous = current
            if stable >= 3: return
        raise AssertionError('The native PDF viewport did not settle after focus navigation')

    def select_city(self, page, frame, city, keyboard=False):
        self.settle_view(page, frame)
        frame.locator('#id_forms').click(position=self.field_point(frame, 'city', arrow=True), delay=80)
        frame.get_by_text(city, exact=True).wait_for(state='visible')
        if keyboard:
            frame.wait_for_function('()=>{const menu=document.querySelector(".dropdown-menu[aria-expanded=true]");return menu && menu.contains(document.activeElement)}')
            for attempt in range(4):
                if frame.evaluate('document.activeElement.textContent.trim()') == city: break
                page.keyboard.press('ArrowDown')
            self.check('keyboard_focuses_requested_pdf_dropdown_item', frame.evaluate('document.activeElement.textContent.trim()') == city)
            page.keyboard.press('Enter')
        else: frame.get_by_text(city, exact=True).click()
        # Reproduces the race: Tab changes activeForm immediately after the menu selection.
        page.keyboard.press('Tab')
        self.value_is(frame, 'city', city)
        self.check('pdf_dropdown_commits_before_rapid_tab_' + city, not frame.locator('.asc-window.alert:visible').count())

    def expected(self, data):
        fields = data['fields']
        return data['pages'] == 2 and all(fields.get(name, {}).get('value') == value for name, value in
            [('contact', self.marker), ('city', 'Shanghai'), ('accepted', 'Yes'), ('record', 'Read only'), (self.new_name, self.new_marker)])

    def wait_saved(self, page, frame, path, predicate=None):
        import fitz
        previous, stable = None, 0
        for attempt in range(130):
            page.wait_for_timeout(150)
            if frame.locator('.asc-window.alert:visible').count():
                raise AssertionError('Native PDF save displayed an error: ' + frame.locator('.asc-window.alert:visible').inner_text())
            try:
                ready, current = (predicate or self.expected)(read_pdf(path)), sha(path)
                stable = stable + 1 if ready and current == previous else 0
                previous = current
                if ready and stable >= 3 and not frame.evaluate('editor.asc_isDocumentCanSave()'): return
            except (OSError, ValueError, RuntimeError, fitz.FileDataError): pass
        raise AssertionError('The native PDF save did not reach independently verified stable output')

    def edit_existing(self, playwright):
        import fitz
        self.start()
        self.open_argument(self.edited)
        browser, page, frame = self.connect(playwright)
        self.dismiss_tips(frame)
        self.check('existing_pdf_native_source_path', Path(frame.evaluate('AscDesktopEditor.LocalFileGetSourcePath()')).resolve() == self.edited)
        self.check('existing_pdf_has_two_pages_and_four_widgets', frame.evaluate('editor.getCountPages()===2 && editor.GetAllFieldsNames().length===4'))
        self.check('independent_initial_pdf_fields_match_model', self.fields(frame) == {name: row['value'] for name, row in read_pdf(self.source)['fields'].items()})
        frame.locator('#btn-zoom-topage').click()
        frame.wait_for_function('PDFE.getController("Statusbar").getZoom()<100')
        zoom = frame.evaluate('PDFE.getController("Statusbar").getZoom()')
        frame.locator('#btn-zoom-up').click()
        frame.wait_for_function('z=>PDFE.getController("Statusbar").getZoom()>z', arg=zoom)
        self.check('native_pdf_zoom_controls_change_real_view', True)
        frame.locator('#btn-zoom-topage').click()
        page.wait_for_timeout(300)
        frame.locator('#id_forms').click(position=self.field_point(frame, 'contact'), delay=80)
        self.select_text(page, frame, 'Original name')
        page.keyboard.type(self.marker, delay=20)
        page.keyboard.press('Enter')
        self.value_is(frame, 'contact', self.marker)
        self.check('chinese_and_latin_pdf_text_input_commits', True)
        frame.locator('.ql-quickbar [data-ql-action="undo"]').click()
        self.check('pdf_form_undo_changes_inserted_text', self.fields(frame)['contact'] != self.marker)
        frame.locator('.ql-quickbar [data-ql-action="redo"]').click()
        self.value_is(frame, 'contact', self.marker)
        self.check('pdf_form_redo_restores_inserted_text', True)
        self.select_city(page, frame, 'Shenzhen')
        self.select_city(page, frame, 'Shanghai', keyboard=True)
        self.settle_view(page, frame)
        frame.locator('#id_forms').click(position=self.field_point(frame, 'accepted'), delay=80)
        self.value_is(frame, 'accepted', 'Yes')
        self.check('pdf_checkbox_commits_checked_value', True)
        frame.locator('#id_forms').click(position=self.field_point(frame, 'record'))
        page.keyboard.insert_text('Blocked edit')
        self.check('readonly_pdf_widget_rejects_input', self.fields(frame)['record'] == 'Read only' and self.fields(frame)['contact'] == self.marker)
        page.keyboard.press('Escape')
        frame.locator('#slot-status-btn-next button').click()
        frame.wait_for_function('editor.getCurrentPage()===1')
        self.check('native_pdf_next_page_changes_visible_page', True)
        frame.locator('.ql-quickbar [data-ql-action="pdfmode"]').click()
        frame.wait_for_function('PDFE.getController("Main").appOptions.isPDFEdit')
        self.check('quick_pdf_mode_enters_real_content_editor', True)
        self.dismiss_tips(frame)
        frame.locator('.ql-quickbar [data-ql-action="commands"]').click()
        frame.locator('.ql-command-item[data-ql-action="tools-forms"]').click()
        self.check('command_search_reaches_native_form_tools', frame.get_by_role('button', name='文本字段', exact=True).is_visible())
        before = set(self.fields(frame))
        frame.get_by_role('button', name='文本字段', exact=True).click()
        frame.wait_for_function('editor.GetAllFieldsNames().length===5')
        self.new_name = next(iter(set(self.fields(frame)) - before))
        self.check('native_form_button_creates_one_text_field', bool(self.new_name))
        page.screenshot(path=str(self.evidence / 'creating-form-field.png'))
        frame.locator('.ql-back').click()
        frame.locator('.ql-quickbar [data-ql-action="pdfmode"]').click()
        frame.wait_for_function('!PDFE.getController("Main").appOptions.isPDFEdit')
        page.wait_for_timeout(350)
        frame.locator('#id_forms').click(position=self.field_point(frame, self.new_name, 1))
        # New field fonts can load asynchronously; use normal typed key events after focus settles.
        page.wait_for_timeout(400)
        page.keyboard.type(self.new_marker, delay=20)
        self.select_text(page, frame, self.new_marker)
        page.keyboard.press('Enter')
        page.keyboard.press('Tab')
        self.value_is(frame, self.new_name, self.new_marker)
        self.check('new_pdf_field_accepts_keyboard_input', True)
        frame.locator('.ql-quickbar [data-ql-action="save"]').click()
        self.wait_saved(page, frame, self.edited)
        saved = read_pdf(self.edited)
        self.check('independent_pdf_reader_finds_all_five_saved_values', self.expected(saved))
        self.check('saved_new_text_field_is_on_second_page', saved['fields'][self.new_name]['page'] == 1 and saved['fields'][self.new_name]['type'] == fitz.PDF_WIDGET_TYPE_TEXT)
        self.check('saved_pdf_retains_dropdown_choices', saved['fields']['city']['choices'] == ['Beijing', 'Shanghai', 'Shenzhen'])
        self.check('saved_pdf_retains_readonly_flag', saved['fields']['record']['flags'] & fitz.PDF_FIELD_IS_READ_ONLY)
        self.check('saved_pdf_retains_original_page_text', 'Qingliang PDF form acceptance' in saved['text'][0] and 'Second page - retained content' in saved['text'][1])
        self.check('saved_pdf_appearance_contains_filled_text', ''.join(self.marker.split()) in ''.join(saved['text'][0].split()) and self.new_marker in saved['text'][1])
        with fitz.open(self.edited) as document:
            for index in range(2): document[index].get_pixmap().save(self.evidence / ('saved-page-' + str(index + 1) + '.png'))
        if frame.evaluate('editor.getCurrentPage()') != 0:
            frame.locator('#slot-status-btn-prev button').click()
        frame.wait_for_function('editor.getCurrentPage()===0')
        page.wait_for_timeout(200)
        page.screenshot(path=str(self.evidence / 'filled-pdf.png'))
        self.check('saving_returns_pdf_to_clean_state', not frame.evaluate('editor.asc_isDocumentCanSave()'))
        self.close()

    def reopen_and_save_as(self, playwright):
        self.start()
        self.open_argument(self.edited)
        browser, page, frame = self.connect(playwright)
        self.dismiss_tips(frame)
        self.check('fresh_process_reopens_all_saved_pdf_fields', self.fields(frame) == {name: row['value'] for name, row in read_pdf(self.edited)['fields'].items()})
        self.check('fresh_process_pdf_is_clean', not frame.evaluate('editor.asc_isDocumentCanSave()'))
        page.screenshot(path=str(self.evidence / 'reopened-pdf.png'))
        before = sha(self.edited)
        frame.locator('.ql-quickbar [data-ql-action="file"]').click()
        frame.locator('.ql-command-item[data-ql-action="saveas"]').click()
        dialog = owned_dialog(self.pid)
        self.check('pdf_save_as_opens_owned_native_dialog', dialog.exists())
        dialog.child_window(auto_id='1001', control_type='Edit', visible_only=False).set_edit_text(str(self.created))
        dialog.child_window(auto_id='1', control_type='Button', visible_only=False).invoke()
        self.wait_saved(page, frame, self.created)
        self.check('uppercase_pdf_copy_has_no_duplicate_extension', self.created.exists() and not Path(str(self.created) + '.pdf').exists())
        self.check('pdf_save_as_preserves_original_bytes', sha(self.edited) == before)
        self.check('pdf_save_as_changes_native_source_path', Path(frame.evaluate('AscDesktopEditor.LocalFileGetSourcePath()')).resolve() == self.created)
        self.check('pdf_copy_keeps_editable_widgets_and_values', self.expected(read_pdf(self.created)))
        frame.locator('.ql-quickbar [data-ql-action="commands"]').click()
        frame.locator('.ql-command-item[data-ql-action="pdfmode"]').click()
        frame.wait_for_function('PDFE.getController("Main").appOptions.isPDFEdit')
        self.check('command_search_switches_pdf_to_edit_mode', True)
        self.dismiss_tips(frame)
        frame.locator('.ql-quickbar [data-ql-action="commands"]').click()
        self.check('edit_mode_command_describes_return_to_reading', frame.locator('.ql-command-item[data-ql-action="pdfmode"]').inner_text().startswith('返回阅读与批注'))
        frame.locator('.ql-command-item[data-ql-action="pdfmode"]').click()
        frame.wait_for_function('!PDFE.getController("Main").appOptions.isPDFEdit')
        self.check('command_search_returns_to_pdf_reading_mode', True)
        self.close()


class EmptyPdfAcceptance(PdfAcceptance):
    def __init__(self, args):
        super().__init__(args)
        self.fixture_marker = '.qingliang-pdf-empty-acceptance'
        self.fixture_report = 'pdf-empty-field-result.json'

    def empty_field_cycle(self, playwright):
        initial = {name: row['value'] for name, row in read_pdf(self.source)['fields'].items()}
        def expected(value):
            return lambda data: data['pages'] == 2 and len(data['fields']) == 5 and all(
                data['fields'].get(name, {}).get('value') == wanted for name, wanted in {**initial, self.new_name: value}.items())
        self.start()
        self.open_argument(self.edited)
        browser, page, frame = self.connect(playwright)
        self.dismiss_tips(frame)
        frame.locator('#slot-status-btn-next button').click()
        frame.wait_for_function('editor.getCurrentPage()===1')
        frame.locator('.ql-quickbar [data-ql-action="pdfmode"]').click()
        frame.wait_for_function('PDFE.getController("Main").appOptions.isPDFEdit')
        self.dismiss_tips(frame)
        frame.locator('.ql-quickbar [data-ql-action="commands"]').click()
        frame.locator('.ql-command-item[data-ql-action="tools-forms"]').click()
        frame.get_by_role('button', name='文本字段', exact=True).click()
        frame.wait_for_function('editor.GetAllFieldsNames().length===5')
        self.new_name = next(name for name in self.fields(frame) if name not in initial)
        self.check('empty_cycle_creates_one_new_native_text_field', True)
        frame.locator('.ql-back').click()
        frame.locator('.ql-quickbar [data-ql-action="pdfmode"]').click()
        frame.wait_for_function('!PDFE.getController("Main").appOptions.isPDFEdit')
        frame.locator('.ql-quickbar [data-ql-action="save"]').click()
        self.wait_saved(page, frame, self.edited, expected(''))
        self.check('empty_cycle_independently_saves_blank_field', True)
        self.check('empty_cycle_blank_field_is_on_second_page', read_pdf(self.edited)['fields'][self.new_name]['page'] == 1)
        self.close()

        self.start()
        self.open_argument(self.edited)
        browser, page, frame = self.connect(playwright)
        self.dismiss_tips(frame)
        self.check('empty_cycle_reopens_blank_value', self.fields(frame)[self.new_name] in (None, ''))
        frame.locator('#slot-status-btn-next button').click()
        frame.wait_for_function('editor.getCurrentPage()===1')
        frame.locator('#btn-zoom-topage').click()
        page.wait_for_timeout(350)
        frame.locator('#id_forms').click(position=self.field_point(frame, self.new_name, 1), delay=80)
        page.wait_for_timeout(500)
        page.keyboard.type(self.new_marker, delay=25)
        page.keyboard.press('Enter')
        self.value_is(frame, self.new_name, self.new_marker)
        self.check('empty_cycle_fills_previously_saved_empty_field', True)
        frame.locator('.ql-quickbar [data-ql-action="save"]').click()
        self.wait_saved(page, frame, self.edited, expected(self.new_marker))
        self.check('empty_cycle_independently_resaves_new_value', True)
        page.screenshot(path=str(self.evidence / 'resaved-empty-field.png'))
        self.close()

        self.start()
        self.open_argument(self.edited)
        browser, page, frame = self.connect(playwright)
        self.check('empty_cycle_fresh_process_reads_resaved_value', self.fields(frame)[self.new_name] == self.new_marker)
        self.check('empty_cycle_reopened_file_is_clean', not frame.evaluate('editor.asc_isDocumentCanSave()'))
        self.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--qt-dir', required=True, type=Path)
    parser.add_argument('--evidence-dir', required=True, type=Path)
    parser.add_argument('--empty-field-cycle-only', action='store_true', help='Run the separate create-empty/save/reopen/fill/resave/reopen regression')
    args = parser.parse_args()
    if os.name != 'nt': parser.error('Windows is required')
    work = args.work_dir.resolve()
    if not (work / '.qingliang-dependency-build').is_file(): raise ValueError('Select the marked stable build directory')
    build = json.loads((work / 'editor-build-report.json').read_text('utf-8'))
    if build['input_manifest_sha256'] != sha(ROOT / 'editor.inputs.lock.json'): raise ValueError('Build the current editor resources first')
    os.environ['TEMP'] = os.environ['TMP'] = str(work / 'temp')
    from playwright.sync_api import sync_playwright
    acceptance = (EmptyPdfAcceptance if args.empty_field_cycle_only else PdfAcceptance)(args)
    report = {'cases': acceptance.cases, 'observed_javascript_errors': acceptance.errors, 'normal_shutdowns': acceptance.closes,
        'input_method': 'Chromium events; native Windows IME and clipboard not tested',
        'exe_sha256': sha(work / 'bin/DesktopEditors.exe'), 'host_dll_sha256': sha(work / 'bin/ascdocumentscore.dll'),
        'editor_build_report_sha256': sha(work / 'editor-build-report.json'), 'runtime_layout_sha256': sha(work / 'editor-runtime-layout.json'),
        'test_source_sha256': sha(Path(__file__)), 'native_session_helper_sha256': sha(ROOT / 'tests/run_editor_tests.py'),
        'preview_launcher_sha256': sha(ROOT / 'tools/launch_qt_preview.py'),
        'empty_field_cycle_suite': args.empty_field_cycle_only,
        'empty_new_field_reopen_then_fill_resave_acceptance': False, 'complex_pdf_forms_acceptance': False,
        'signature_acceptance': False, 'physical_printing_acceptance': False, 'installer_acceptance': False}
    try:
        acceptance.fixtures()
        with sync_playwright() as playwright:
            if args.empty_field_cycle_only:
                acceptance.empty_field_cycle(playwright)
            else:
                acceptance.edit_existing(playwright)
                acceptance.reopen_and_save_as(playwright)
        acceptance.check('untouched_source_pdf_preserved', sha(acceptance.source) == acceptance.original_hash)
        acceptance.check('interactions_have_no_observed_javascript_errors', not acceptance.errors)
    except BaseException as error:
        report['execution_error'] = str(error)
        raise
    finally:
        if acceptance.fixtures_ready:
            report['new_field_name'] = acceptance.new_name
            report['owned_fixtures'] = {p.relative_to(acceptance.evidence).as_posix(): sha(p) for p in (acceptance.source, acceptance.edited, acceptance.created) if p.exists()}
            report['passed'] = sum(c['passed'] for c in acceptance.cases)
            report['failed'] = max(sum(not c['passed'] for c in acceptance.cases), int('execution_error' in report))
            report['empty_new_field_reopen_then_fill_resave_acceptance'] = args.empty_field_cycle_only and report['failed'] == 0
            (acceptance.evidence / acceptance.fixture_report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
            print(json.dumps({'passed': report['passed'], 'failed': report['failed'], 'installer_acceptance': False}), flush=True)
        elif acceptance.evidence.exists() and (acceptance.evidence / acceptance.fixture_marker).exists():
            (acceptance.evidence / 'fixture-preflight-error.json').write_text(json.dumps({'execution_error': report.get('execution_error'), 'prior_ownership_report_preserved': True}, indent=2) + '\n', 'utf-8')


if __name__ == '__main__': main()
