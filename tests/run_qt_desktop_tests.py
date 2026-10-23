"""Inspect an already running isolated Qt/CEF community desktop, without a native mock."""
import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--evidence-dir', required=True, type=Path)
    parser.add_argument('--qt-dir', required=True, type=Path)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if not (work / '.qingliang-dependency-build').is_file():
        raise ValueError('Select the marked community build staging directory')
    launch = json.loads((work / 'qt-runtime-launch.json').read_text('utf-8'))
    profile = work / 'qt-acceptance-profile'
    if launch['profile'] != str(profile) or not launch['gui_launched']:
        raise ValueError('The desktop must use the dedicated acceptance profile')
    image = ctypes.create_unicode_buffer(32768)
    count = ctypes.c_ulong(len(image))
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, launch['pid'])
    if not handle:
        raise ValueError('The recorded test desktop is no longer running')
    try:
        if not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(count)):
            raise ctypes.WinError(ctypes.get_last_error())
        if Path(image.value).resolve() != work / 'bin/DesktopEditors.exe':
            raise ValueError('The process is not the staged community executable')
    finally:
        kernel.CloseHandle(handle)
    evidence = args.evidence_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({'TEMP': str(work / 'temp'), 'TMP': str(work / 'temp'),
                'OFFICE_USER_DATA_ROOT': str(profile / 'data'),
                'QINGLIANG_SETTINGS_FILE': str(profile / 'settings.ini'),
                'QT_QPA_PLATFORM_PLUGIN_PATH': str(args.qt_dir / 'plugins/platforms')})
    env['PATH'] = os.pathsep.join([str(work / 'bin'), str(work / 'bin/mediaplayer'),
                                 str(work / 'sources/vlc-runtime'), str(args.qt_dir / 'bin'), env['PATH']])
    os.environ['TEMP'] = os.environ['TMP'] = str(work / 'temp')
    cases, errors = [], []
    report = {'native_bridge': 'real CEF bindings; no fixture injected', 'pid': launch['pid'],
              'exe_sha256': hashlib.sha256((work / 'bin/DesktopEditors.exe').read_bytes()).hexdigest(),
              'host_dll_sha256': hashlib.sha256((work / 'bin/ascdocumentscore.dll').read_bytes()).hexdigest(),
              'qt_build_report_sha256': hashlib.sha256((work / 'qt-build-report.json').read_bytes()).hexdigest(),
              'test_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'compiled_index_sha256': hashlib.sha256((work / 'bin/index.html').read_bytes()).hexdigest(),
              'cases': cases, 'edit_save_tested': False, 'installer_tested': False}
    def check(name, success):
        cases.append({'name': name, 'passed': bool(success)})
        if not success:
            raise AssertionError(name)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp('http://127.0.0.1:' + str(launch.get('debug_port', 9223)))
            page = next(p for c in browser.contexts for p in c.pages if p.url.startswith((work / 'bin/index.html').as_uri()))
            page.set_default_timeout(5000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            check('actual_compiled_page_has_real_native_bindings', page.evaluate("typeof AscDesktopEditor === 'object' && typeof AscDesktopEditor.GetEditorId === 'function' && typeof __bridgeCommands === 'undefined'"))
            check('native_editor_id_call_returns_number', isinstance(page.evaluate('AscDesktopEditor.GetEditorId()'), (int, float)))
            page.locator('a').filter(has_text='首页').click()
            check('empty_native_recent_list_has_feedback', page.locator('.ql-recent-empty').is_visible())
            page.keyboard.press('Control+f')
            search = page.locator('#idx-recent-filter')
            check('native_window_ctrl_f_focuses_search', search.evaluate('e => e === document.activeElement'))
            search.fill('验收不存在的文件')
            search.press('Escape')
            check('escape_clears_search', search.input_value() == '')
            page.locator('[data-filter="cell"]').click()
            check('native_window_filter_updates_selection', page.locator('[data-filter="cell"]').get_attribute('aria-pressed') == 'true')
            page.locator('[data-filter="all"]').click()
            check('actual_viewport_has_no_horizontal_overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            page.wait_for_function("!document.getAnimations().some(a => a.playState === 'running' && a.effect.getTiming().iterations !== Infinity)")
            page.screenshot(path=str(evidence / 'native-workbench-light.png'), full_page=True)
            page.emulate_media(reduced_motion='reduce')
            check('cef_reduced_motion_disables_transitions', page.locator('.document-creation-item').first.evaluate("e => getComputedStyle(e).transitionDuration === '0s'"))
            page.emulate_media(reduced_motion='no-preference')
            page.locator('a').filter(has_text='设置').click()
            theme = page.locator('#box-settings select').filter(has=page.locator('option[value="theme-dark"]'))
            theme.select_option('theme-dark')
            page.locator('#sett-btn-apply:visible').click()
            page.wait_for_function("getComputedStyle(document.querySelector('#placeholder')).getPropertyValue('--ql-surface').trim() === '#232934'", timeout=5000)
            page.locator('a').filter(has_text='首页').click()
            check('real_native_dark_theme_updates_workbench', page.locator('#placeholder').evaluate("e => getComputedStyle(e).getPropertyValue('--ql-surface').trim() === '#232934'"))
            page.wait_for_function("!document.getAnimations().some(a => a.playState === 'running' && a.effect.getTiming().iterations !== Infinity)")
            page.screenshot(path=str(evidence / 'native-workbench-dark.png'), full_page=True)
            settings = profile / 'settings.ini'
            check('native_settings_written_to_isolated_ini', settings.is_file() and b'theme-dark' in settings.read_bytes())
            started = time.monotonic()
            secondary = subprocess.run([str(work / 'bin/DesktopEditors.exe'), '--log'], cwd=work / 'bin', env=env,
                                       capture_output=True, timeout=15)
            report['secondary_duration_seconds'] = round(time.monotonic() - started, 3)
            report['secondary_exit_code'] = secondary.returncode
            check('secondary_instance_exits_successfully', secondary.returncode == 0)
            logs = list((profile / 'data').rglob('app.log'))
            check('secondary_instance_delivered_message_to_real_primary', any('Parameter sending status: 1' in p.read_text('utf-8') for p in logs))
            check('secondary_delivery_does_not_wait_for_unfindable_window', report['secondary_duration_seconds'] < 4)
            check('interaction_has_no_javascript_exceptions', not errors)
            page.locator('a').filter(has_text='设置').click()
            theme.select_option('theme-system')
            page.locator('#sett-btn-apply:visible').click()
            page.locator('a').filter(has_text='首页').click()
            page.evaluate('AscDesktopEditor.InitJSContext(); AscDesktopEditor.InitJSContext()')
            page.wait_for_timeout(250)
            check('native_bridge_reinitialization_keeps_crypto_accessor', page.evaluate("(() => { const p = Object.getOwnPropertyDescriptor(AscDesktopEditor, 'CryptoMode'); return !!p && typeof p.get === 'function' && typeof p.set === 'function' && p.configurable === false; })()"))
            check('restore_theme_and_repeated_native_init_have_no_exceptions', not errors)
            report['browser_version'] = browser.version
    except BaseException as error:
        report['execution_error'] = str(error)
        raise
    finally:
        report.update({'passed': sum(c['passed'] for c in cases),
                       'failed': max(sum(not c['passed'] for c in cases), int('execution_error' in report)),
                       'javascript_errors': errors})
        (evidence / 'native-desktop-test-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
        print(json.dumps({k: report[k] for k in ('passed', 'failed', 'edit_save_tested', 'installer_tested')}))


if __name__ == '__main__':
    main()
