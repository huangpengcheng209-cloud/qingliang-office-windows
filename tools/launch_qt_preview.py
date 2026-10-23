"""Prepare the built workbench and start the source-built Qt shell in an isolated acceptance profile.

This is a development preview; desktop editor web-apps and installation acceptance are separate.
"""
import argparse
import ctypes
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from build_dependencies import sha
from build_qt import verify_inputs, verify_sdk
from verify_sources import ROOT


def preview_is_running(pid, expected_image):
    """A retained process object or a reused PID is not a running owned preview."""
    from ctypes import wintypes as wt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = wt.HANDLE
    kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    kernel.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    kernel.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    handle = kernel.OpenProcess(0x101000, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == 87: return False  # No such process.
        raise ctypes.WinError(error)
    try:
        state = kernel.WaitForSingleObject(handle, 0)
        if state == 0: return False  # Exited; another handle can keep its object alive.
        if state != 258: raise ctypes.WinError(ctypes.get_last_error())
        image, size = ctypes.create_unicode_buffer(32768), wt.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return Path(image.value).resolve() == expected_image.resolve()
    finally:
        kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--qt-dir', required=True, type=Path)
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--debug-port', type=int, default=9223)
    args = parser.parse_args()
    if os.name != 'nt': parser.error('Windows is required')
    if not 1024 <= args.debug_port <= 65535: parser.error('Invalid local debugger port')
    work, qt = args.work_dir.resolve(), args.qt_dir.resolve()
    if work == ROOT or ROOT in work.parents or work in ROOT.parents or not (work / '.qingliang-dependency-build').is_file():
        raise ValueError('Select the marked external acceptance build staging directory')
    lock = verify_inputs()
    verify_sdk(lock, qt)
    build = json.loads((work / 'qt-build-report.json').read_text('utf-8'))
    if build['input_manifest_sha256'] != sha(ROOT / 'qt.inputs.lock.json'):
        raise ValueError('Build the current Qt input profile before preview')
    for row in build['artifacts'].values():
        if sha(work / row['output']) != row['sha256']:
            raise ValueError('Qt artifact changed since build')
    host = json.loads((work / 'host-build-report.json').read_text('utf-8'))
    if host['input_manifest_sha256'] != lock['host_input_lock_sha256'] or host['host_dll_sha256'] != sha(work / 'bin/ascdocumentscore.dll'):
        raise ValueError('The native host changed since build')
    home = json.loads((work / 'workbench-build-report.json').read_text('utf-8'))
    index = work / 'sources/desktop-apps/common/loginpage/deploy/index.html'
    if home['input_manifest_sha256'] != lock['ui_input_lock_sha256'] or sha(index) != home['index_html_sha256']:
        raise ValueError('Build the current workbench before preview')
    record = work / 'qt-runtime-launch.json'
    if record.exists():
        prior = json.loads(record.read_text('utf-8'))
        if prior.get('pid') and preview_is_running(prior['pid'], work / 'bin/DesktopEditors.exe'):
            raise ValueError('The previously recorded test process is still running; close that preview normally first')
    folder, profile = work / 'bin', work / 'qt-acceptance-profile'
    profile.mkdir(exist_ok=True)
    fd = os.open(work / '.build.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        inputs = [(index, folder / 'index.html'),
                  (index.parent / 'noconnect.html', folder / 'editors/webext/noconnect.html')]
        cef = json.loads((ROOT / 'host.inputs.lock.json').read_text('utf-8'))['cef_sdk']
        for row in cef['files']:
            name = row['file']
            if name.startswith('Resources/'):
                inputs.append((work / 'sources/cef' / name, folder / name.removeprefix('Resources/')))
            elif name.startswith('Release/') and Path(name).suffix in ('.dll', '.bin', '.json'):
                inputs.append((work / 'sources/cef' / name, folder / Path(name).name))
            else: continue
            if sha(inputs[-1][0]) != row['sha256']:
                raise ValueError('Official CEF runtime resource changed')
        copied = []
        for source, target in inputs:
            digest = sha(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or sha(target) != digest: shutil.copy2(source, target)
            copied.append({'source': str(source), 'destination': str(target), 'sha256': digest})
        env = os.environ.copy()
        env.update({'TEMP': str(work / 'temp'), 'TMP': str(work / 'temp'),
                    'OFFICE_USER_DATA_ROOT': str(profile / 'data'),
                    'QINGLIANG_SETTINGS_FILE': str(profile / 'settings.ini'),
                    'QT_QPA_PLATFORM_PLUGIN_PATH': str(qt / 'plugins/platforms'),
                    'VLC_PLUGIN_PATH': str(work / 'sources/vlc-runtime/plugins')})
        env['PATH'] = os.pathsep.join([str(folder), str(folder / 'mediaplayer'), str(qt / 'bin'),
                                      str(work / 'sources/vlc-runtime'), env['PATH']])
        version = subprocess.run([str(folder / 'DesktopEditors.exe'), '--version'], cwd=folder, env=env,
                                 capture_output=True, timeout=30)
        report = {'version_exit_code': version.returncode, 'resource_copies': copied, 'profile': str(profile),
                  'gui_launched': False, 'edit_save_tested': False, 'debug_port': args.debug_port,
                  'qt_build_report_sha256': sha(work / 'qt-build-report.json'),
                  'host_dll_sha256': sha(folder / 'ascdocumentscore.dll')}
        if version.returncode: raise RuntimeError('Qt version startup failed: ' + str(version.returncode))
        if args.gui:
            command = [str(folder / 'DesktopEditors.exe'), '--log', '--lang=zh-CN',
                       '--remote-debugging-port=' + str(args.debug_port), '--remote-debugging-address=127.0.0.1']
            with (profile / 'native-stdout.log').open('ab') as out, (profile / 'native-stderr.log').open('ab') as err:
                process = subprocess.Popen(command, cwd=folder, env=env, stdout=out, stderr=err)
            report.update({'gui_launched': True, 'pid': process.pid, 'command': command})
            time.sleep(4)
            report['exit_code_after_4s'] = process.poll()
        record.write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
        print(json.dumps({k: v for k, v in report.items() if k != 'resource_copies'}))
        if args.gui and report['exit_code_after_4s'] is not None:
            raise RuntimeError('Qt GUI exited during startup')
    finally:
        os.close(fd)
        (work / '.build.lock').unlink()


if __name__ == '__main__':
    main()
