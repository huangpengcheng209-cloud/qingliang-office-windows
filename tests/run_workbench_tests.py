"""Exercise the real compiled start page; mock only the unavailable CEF native boundary."""
import argparse
import functools
import hashlib
import http.server
import json
import os
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--evidence-dir', required=True, type=Path)
    parser.add_argument('--channel', default='msedge')
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if not (work / '.qingliang-dependency-build').is_file():
        raise ValueError('Select the existing marked community build directory')
    os.environ['TEMP'] = os.environ['TMP'] = str(work / 'temp')
    evidence = args.evidence_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    home = work / 'sources/desktop-apps/common/loginpage'
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(home)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/deploy/index.html'
    errors, cases = [], []
    records = [
        {'id': 1, 'type': 65, 'path': 'D:\\工作文件\\季度项目计划.docx', 'modifyed': '2026-10-23 09:20'},
        {'id': 2, 'type': 257, 'path': 'D:\\工作文件\\项目预算.xlsx', 'modifyed': '2026-10-22 16:30'},
        {'id': 3, 'type': 129, 'path': 'D:\\工作文件\\方案汇报.pptx', 'modifyed': '2026-10-22 15:10'},
        {'id': 4, 'type': 513, 'path': 'D:\\工作文件\\产品介绍.pdf', 'modifyed': '2026-10-21 11:00'},
        {'id': 5, 'type': 65, 'path': 'D:\\工作文件\\Q&A [v2].docx', 'modifyed': '2026-10-21 09:20'},
        {'id': 6, 'type': 257, 'path': 'D:\\归档\\年度统计.xlsx', 'modifyed': '2026-10-20 15:00'},
        {'id': 7, 'type': 65, 'path': 'D:\\归档\\Café.docx', 'modifyed': '2026-10-19 14:00'},
        {'id': 8, 'type': 65, 'path': 'D:\\归档\\固定模板.docx', 'modifyed': '2026-10-18 11:00', 'pin': True}
    ]
    def check(name, condition):
        if not condition:
            page.screenshot(path=str(evidence / 'workbench-failure.png'), full_page=True)
            raise AssertionError(name)
        cases.append(name)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=args.channel, headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.add_init_script(path=str(ROOT / 'tests/ui/native_bridge_fixture.js'))
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base + '?lang=zh-CN')
            page.wait_for_selector('.ql-workbench-header')
            check('actual_page_boots_without_js_error', not errors)
            check('empty_recent_state', page.locator('.ql-recent-empty').is_visible())
            page.screenshot(path=str(evidence / 'workbench-empty.png'), full_page=True)
            def history(items):
                page.evaluate('rows => window.onupdaterecents(rows)', items)
                page.wait_for_function('(count) => app.controller.recent.getRecents().size() === count', arg=len(items))
                page.wait_for_timeout(60)
            def visible():
                return page.locator('#box-recent .row:visible').count()
            def filter_type(key):
                page.locator(f'[data-filter="{key}"]').click()
            search = page.locator('#idx-recent-filter')
            history(records)
            check('four_recent_rows_and_more', visible() == 4 and page.locator('.ql-more-recent').is_visible())
            check('pinned_row_sorted_first', page.locator('#box-recent .row').first.locator('.col-name').get_attribute('title') == '固定模板.docx')
            check('render_keeps_full_model_filename', page.evaluate('app.controller.recent.getRecents().items.find(m => m.fileid === 5).name') == 'Q&A [v2].docx')
            check('file_action_icons_keep_readable_dimensions', page.locator('#box-recent .row:visible .btn-quick svg').evaluate_all('es => es.every(e => e.clientWidth >= 16 && e.clientHeight >= 16)'))
            page.screenshot(path=str(evidence / 'workbench-light.png'), full_page=True)
            page.locator('.ql-more-recent').click()
            check('expand_all_recent_files', visible() == 8)
            page.locator('.ql-more-recent').click()
            check('collapse_recent_files', visible() == 4)
            search.fill('[')
            check('literal_regex_metacharacter_search', visible() == 1 and 'Q&A' in page.locator('#box-recent .row:visible .col-name').inner_text())
            search.fill('q&a [V2]')
            check('case_insensitive_search_with_ampersand', visible() == 1)
            search.fill('[')
            check('repeated_query_has_no_regex_state_bug', visible() == 1)
            search.fill('café')
            check('unicode_normalization_search', visible() == 1)
            search.fill('归档')
            check('location_search', visible() == 3)
            search.press('Escape')
            check('escape_clears_and_restores_collapsed_rows', search.input_value() == '' and visible() == 4)
            filter_type('cell')
            check('spreadsheet_filter', visible() == 2)
            search.fill('年度')
            check('query_and_type_filter_combined', visible() == 1)
            filter_type('pdf')
            check('no_results_feedback', visible() == 0 and page.locator('.ql-no-results').is_visible())
            page.locator('.ql-reset-filter').click()
            check('clear_all_filters_restores_history_and_focus', visible() == 4 and search.input_value() == '' and search.evaluate('e => e === document.activeElement'))
            filter_type('word')
            check('document_filter', visible() == 4)
            filter_type('slide')
            check('presentation_filter', visible() == 1)
            filter_type('pdf')
            check('pdf_filter', visible() == 1)
            filter_type('pinned')
            check('pinned_filter', visible() == 1)
            page.locator('#box-recent .row:visible .col-pin button').click()
            page.wait_for_timeout(60)
            check('unpin_updates_native_command_and_active_filter', visible() == 0 and page.evaluate("__bridgeCommands.some(c => c.command === 'recent:pinned' && JSON.parse(c.payload).id === 8 && !JSON.parse(c.payload).pinned)"))
            filter_type('all')
            page.keyboard.press('Control+f')
            check('ctrl_f_focuses_recent_search', search.evaluate('e => e === document.activeElement'))
            search.fill('Q&A')
            search.press('ArrowDown')
            check('arrow_down_focuses_matching_file', page.locator('#box-recent .row:visible .col-name').evaluate('e => e === document.activeElement'))
            page.evaluate('window.last_click_time = -10000')
            page.wait_for_timeout(850)
            page.keyboard.press('Enter')
            command = page.evaluate("__bridgeCommands.filter(c => c.command === 'open:recent').at(-1)")
            check('keyboard_open_uses_existing_native_command_and_full_name', command and json.loads(command['payload'])['name'] == 'Q&A [v2].docx')
            search.fill('')
            for doc_type in ('word', 'cell', 'slide', 'form'):
                page.locator(f'.document-creation-item[data-id="{doc_type}"]').click()
            check('all_four_create_actions_reach_native_boundary', page.evaluate("['word','cell','slide','form'].every(t => __bridgeCommands.some(c => c.command === 'create:new' && c.payload === t))"))
            page.evaluate('window.last_click_time = -10000')
            page.locator('.ql-open-existing').click()
            check('open_existing_reaches_native_boundary', page.evaluate("__bridgeCommands.some(c => c.command === 'open:folder')"))
            # 40 duplicate paths made the old unique-hash batch count stop loading early.
            duplicate_batch = [{'id': 100+i, 'type': 65, 'path': 'D:\\fixture\\duplicate.docx', 'modifyed': ''} for i in range(52)]
            history(duplicate_batch)
            check('batch_continues_after_duplicate_paths', page.evaluate('app.controller.recent.getRecents().size()') == 52)
            old = [{'id': 200+i, 'type': 65, 'path': f'D:\\fixture\\old-{i}.docx', 'modifyed': ''} for i in range(120)]
            page.evaluate('([old, current]) => {onupdaterecents(old); setTimeout(() => onupdaterecents(current), 15)}', [old, records])
            page.wait_for_timeout(300)
            check('new_history_cancels_stale_async_batches', page.evaluate('app.controller.recent.getRecents().size()') == 8 and 'old-' not in page.locator('#box-recent').inner_text())
            search.fill('Needle')
            streamed = duplicate_batch + [{'id': 999, 'type': 65, 'path': 'D:\\fixture\\Needle.docx', 'modifyed': ''}]
            history(streamed)
            check('active_search_applies_to_later_batches', visible() == 1)
            history(records)
            search.fill('')
            page.emulate_media(reduced_motion='reduce')
            check('reduced_motion_disables_animation_and_transition', page.locator('.document-creation-grid').evaluate("e => getComputedStyle(e).animationName === 'none'") and page.locator('.document-creation-item').first.evaluate("e => getComputedStyle(e).transitionDuration === '0s'"))
            page.set_viewport_size({'width': 920, 'height': 820})
            check('compact_layout_has_no_horizontal_page_overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth') and page.locator('.recent-panel-container').evaluate('e => e.scrollWidth <= e.clientWidth'))
            page.screenshot(path=str(evidence / 'workbench-compact.png'), full_page=True)
            page.goto(base + '?lang=zh-CN&uitheme=theme-dark')
            page.wait_for_selector('.ql-workbench-header')
            history(records)
            page.set_viewport_size({'width': 1440, 'height': 1000})
            check('dark_theme_uses_dark_workbench_surfaces', page.locator('#placeholder').evaluate("e => getComputedStyle(e).getPropertyValue('--ql-surface').trim() === '#232934'"))
            check('dark_recent_rows_use_the_actual_workbench_surface', page.locator('#box-recent .row').first.evaluate("e => getComputedStyle(e).backgroundColor === 'rgb(35, 41, 52)'"))
            page.screenshot(path=str(evidence / 'workbench-dark.png'), full_page=True)
            page.evaluate("utils.Lang.change('en')")
            check('language_switch_updates_search_filters_and_result_status', search.get_attribute('placeholder') == 'Search files or locations' and page.locator('[data-filter="all"]').inner_text() == 'All files' and 'files' in page.locator('.ql-recent-count').inner_text())
            check('all_browser_scenarios_have_no_js_errors', not errors)
            browser_version = browser.version
            context.close()
            browser.close()
        report = {'passed': len(cases), 'failed': 0, 'cases': cases, 'browser': browser_version,
                  'compiled_index_sha256': hashlib.sha256((home / 'deploy/index.html').read_bytes()).hexdigest(),
                  'native_bridge': 'test adapter, production JavaScript and DOM are real',
                  'desktop_editor_edit_save_verified': False, 'installer_verified': False}
        (evidence / 'workbench-test-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
        print(json.dumps({'passed': len(cases), 'failed': 0, 'desktop_editor_edit_save_verified': False}), flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
