"""Use owned child processes to distinguish live previews from retained/reused PIDs."""
import ctypes
import os
import subprocess
import sys
import unittest
from ctypes import wintypes as wt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from launch_qt_preview import preview_is_running


@unittest.skipUnless(os.name == 'nt', 'Windows process handles are required')
class PreviewProcessTests(unittest.TestCase):
    def child(self):
        process = subprocess.Popen([sys.executable, '-c', 'import sys; print("ready", flush=True); sys.stdin.readline()'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=subprocess.CREATE_NO_WINDOW, text=True)
        self.addCleanup(self.finish, process)
        self.assertEqual(process.stdout.readline().strip(), 'ready')
        return process

    def finish(self, process):
        if process.poll() is None:
            process.stdin.write('\n')
            process.stdin.flush()
        process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0)

    def test_live_owned_image_is_running(self):
        process = self.child()
        self.assertTrue(preview_is_running(process.pid, Path(sys.executable)))

    def test_unrelated_live_image_does_not_block_preview(self):
        process = self.child()
        self.assertFalse(preview_is_running(process.pid, Path(sys.executable).with_name('DesktopEditors.exe')))

    def test_retained_handle_to_exited_process_does_not_block_preview(self):
        process = self.child()
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = wt.HANDLE
        kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        kernel.CloseHandle.argtypes = [wt.HANDLE]
        handle = kernel.OpenProcess(0x101000, False, process.pid)
        self.assertTrue(handle)
        try:
            self.finish(process)
            self.assertFalse(preview_is_running(process.pid, Path(sys.executable)))
        finally:
            kernel.CloseHandle(handle)
