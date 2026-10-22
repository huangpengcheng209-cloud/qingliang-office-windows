import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_formats as formats
import run_format_tests as driver


class FormatToolTests(unittest.TestCase):
    def setUp(self):
        parent=Path(os.environ.get('QINGLIANG_TEST_TEMP',str(ROOT/'work')));parent.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(prefix='format-tool-',dir=parent);self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.lock=copy.deepcopy(formats.verify_format_inputs())

    def rejects(self,message):
        original=json.loads
        def load(text,*args,**kwargs):
            value=original(text,*args,**kwargs)
            return self.lock if isinstance(value,dict) and 'PoleSupport' in value.get('profiles',{}) else value
        with patch.object(formats.json,'loads',side_effect=load),self.assertRaisesRegex(ValueError,message):formats.verify_format_inputs()

    def test_core_revision_substitution_rejected(self):
        self.lock['revision']='0'*40;self.rejects('identity differs')

    def test_frozen_source_identity_cannot_be_redefined(self):
        next(r for r in self.lock['files'] if r['origin']=='frozen-overlay')['base_sha256']='0'*64
        self.rejects('original 96-file identity')

    def test_unpinned_compile_unit_rejected(self):
        self.lock['profiles']['VbaFormatLib']['sources'][0]='unreviewed.cpp';self.rejects('Unpinned format')

    def test_case_colliding_input_rejected(self):
        row=self.lock['files'][0];self.lock['files'].append({**row,'file':row['file'].upper()});self.rejects('Duplicate format')

    def test_traversal_rejected_before_preparation(self):
        self.lock['files'][0]['file']='../../escape';self.rejects('Unsafe')

    def test_colliding_object_names_rejected(self):
        units=self.lock['profiles']['VbaFormatLib']['sources'];units[0]=units[1];self.rejects('object name collision')

    def test_bom_and_all_patch_bytes_reconstruct_exact_upstream(self):
        rows=[r for r in self.lock['files'] if r.get('patch','').startswith('format-patches/')]
        subprocess.run(['git','init','--quiet',str(self.root)],check=True)
        command=['git','-c','core.autocrlf=false','-C',str(self.root),'apply','--whitespace=nowarn']
        for row in rows:
            target=self.root/row['file'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/row['modified_source'],target)
        for patch_file in sorted({row['patch'] for row in rows}):
            selected=[r for r in rows if r['patch']==patch_file];subprocess.run(command+['-R',str(ROOT/patch_file)],check=True)
            for row in selected:self.assertEqual(hashlib.sha256((self.root/row['file']).read_bytes()).hexdigest(),row['base_sha256'])
            subprocess.run(command+[str(ROOT/patch_file)],check=True)
            for row in selected:self.assertEqual((self.root/row['file']).read_bytes(),(ROOT/row['modified_source']).read_bytes())

    def test_unreviewed_external_header_preserved_and_rejected(self):
        core=self.root/'core';boost=self.root/'boost';sdk=self.root/'sdk'
        for directory in (core,boost,sdk):directory.mkdir()
        source=core/'test.cpp';source.write_bytes(b'fixture');unknown=self.root/'unknown.h';unknown.write_bytes(b'preserve')
        folder=self.root/'format-build/Test/dependencies';folder.mkdir(parents=True)
        (folder/'test.json').write_text(json.dumps({'Data':{'Source':str(source),'Includes':[str(unknown)]}}),'utf-8')
        lock={'files':[],'boost':{'files':[]},'profiles':{'Test':{'sources':['test.cpp']}}}
        with self.assertRaisesRegex(ValueError,'Unreviewed external'):formats.audit_compiler_inputs(self.root,core,boost,lock,{'WINDOWSSDKDIR':str(sdk)})
        self.assertEqual(unknown.read_bytes(),b'preserve')

    def test_success_exit_with_failed_marker_does_not_pass_driver(self):
        exe=self.root/'test.exe';exe.write_bytes(b'fixture')
        fake=SimpleNamespace(returncode=0,stdout='FAIL\n',stderr='')
        with patch.object(sys,'argv',['run_format_tests.py','--exe',str(exe),'--work-dir',str(self.root)]),patch.object(driver.subprocess,'run',return_value=fake),patch('builtins.print'),self.assertRaisesRegex(RuntimeError,'cases failed'):
            driver.main()
        self.assertEqual(json.loads((self.root/'format-test-result.json').read_text('utf-8')),{'passed':0,'failed':36})

    def test_native_failure_diagnostics_include_case_and_exit_code(self):
        outcomes=[SimpleNamespace(returncode=0,stdout='PASS\n',stderr='') for _ in driver.CASES]
        outcomes[13]=SimpleNamespace(returncode=2,stdout='',stderr='native fixture error')
        with patch.object(sys,'argv',['run_format_tests.py','--exe',str(self.root/'test.exe'),'--work-dir',str(self.root)]),patch.object(driver.subprocess,'run',side_effect=outcomes),patch('builtins.print') as output,self.assertRaisesRegex(RuntimeError,'cases failed'):
            driver.main()
        failed=[args[0][0] for args in output.call_args_list if str(args[0][0]).startswith('FORMAT_FAILURE ')]
        self.assertEqual(len(failed),1)
        entry=json.loads(failed[0].removeprefix('FORMAT_FAILURE '))
        self.assertEqual((entry['case'],entry['exit_code'],entry['stderr']),(13,2,'native fixture error'))


if __name__=='__main__':unittest.main()
