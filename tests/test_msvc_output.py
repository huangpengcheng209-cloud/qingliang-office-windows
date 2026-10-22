import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import msvc_output


class MsvcOutputTests(unittest.TestCase):
    def test_chinese_include_keeps_header_path_in_utf8(self):
        path='  D:\\源码\\header.h\r\n'
        data=('注意: 包含文件:'+path).encode('cp936')
        self.assertEqual(msvc_output.normalize(data,'cp936'),('Note: including file:'+path).encode('utf-8'))

    def test_english_include_unchanged(self):
        data=b'Note: including file: D:\\source\\header.h\r\n'
        self.assertEqual(msvc_output.normalize(data,'cp936'),data)

    def test_utf8_chinese_output_is_not_decoded_twice(self):
        data='注意: 包含文件:  D:\\source\\header.h\r\n'.encode('utf-8')
        self.assertEqual(msvc_output.normalize(data,'cp936'),b'Note: including file:  D:\\source\\header.h\r\n')

    def test_diagnostic_is_preserved(self):
        data='file.cpp(2): error C1083: 无法打开文件\r\n'
        self.assertEqual(msvc_output.normalize(data.encode('cp936'),'cp936'),data.encode('utf-8'))

    def test_child_failure_exit_is_forwarded(self):
        child=type('Child',(),{'stdout':io.BytesIO(b'compiler error\n'),'wait':lambda self:7})()
        capture=type('Output',(),{'buffer':io.BytesIO()})()
        with patch.object(sys,'argv',['msvc_output.py','compiler.exe']),patch.object(msvc_output.subprocess,'Popen',return_value=child),patch.object(sys,'stdout',capture):
            self.assertEqual(msvc_output.main(),7)
        self.assertEqual(capture.buffer.getvalue(),b'compiler error\n')

    def test_changed_wrapper_does_not_launch_compiler(self):
        with patch.object(sys,'argv',['msvc_output.py','--source-sha256='+'0'*64,'compiler.exe']),patch.object(msvc_output.subprocess,'Popen') as child:
            self.assertEqual(msvc_output.main(),2)
        child.assert_not_called()


if __name__=='__main__':unittest.main()
