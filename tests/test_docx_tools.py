import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_docx as docx
import text_docx_preview as preview


class DocxToolTests(unittest.TestCase):
    def setUp(self):
        parent=Path(os.environ.get('QINGLIANG_TEST_TEMP',str(ROOT/'work')));parent.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(prefix='docx-tool-',dir=parent);self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.lock=copy.deepcopy(docx.verify_docx_inputs())

    def rejects(self,message):
        original=json.loads
        def load(text,*args,**kwargs):
            value=original(text,*args,**kwargs)
            return self.lock if isinstance(value,dict) and 'TxtDocxBridge' in value.get('profiles',{}) else value
        with patch.object(docx.json,'loads',side_effect=load),self.assertRaisesRegex(ValueError,message):docx.verify_docx_inputs()

    def test_archive_revision_substitution_rejected(self):
        self.lock['core_archive']['revision']='0'*40;self.rejects('archive origin')

    def test_frozen_source_identity_cannot_be_redefined(self):
        next(r for r in self.lock['files'] if r['origin']=='frozen-overlay')['base_sha256']='0'*64;self.rejects('original 96-file')

    def test_html_source_path_traversal_rejected(self):
        self.lock['support_archives']['gumbo']['files'][0]['file']='../escape';self.rejects('Unsafe')

    def test_html_case_collisions_rejected(self):
        row=self.lock['support_archives']['md4c']['files'][0];self.lock['support_archives']['md4c']['files'].append({**row,'file':row['file'].upper()});self.rejects('Duplicate')

    def test_compile_unit_substitution_rejected(self):
        self.lock['profiles']['DocxFormatLib']['sources'][0]='not-pinned.cpp';self.rejects('Unpinned')

    def test_all_new_patches_reverse_to_exact_base_bytes(self):
        rows=[r for r in self.lock['files'] if r.get('patch','').startswith('docx-patches/')]
        rows += [{**r,'file':a['destination']+'/'+r['file'],'sha256':r['result_sha256']} for a in self.lock['support_archives'].values() for r in a.get('patches',[]) if r['patch'].startswith('docx-patches/')]
        subprocess.run(['git','init','--quiet',str(self.root)],check=True)
        command=['git','-c','core.autocrlf=false','-C',str(self.root),'apply','--whitespace=nowarn']
        for row in rows:
            target=self.root/row['file'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/row['modified_source'],target)
        for filename in sorted({r['patch'] for r in rows}):
            selected=[r for r in rows if r['patch']==filename];subprocess.run(command+['-R',str(ROOT/filename)],check=True)
            for r in selected:self.assertEqual(hashlib.sha256((self.root/r['file']).read_bytes()).hexdigest(),r['base_sha256'])
            subprocess.run(command+[str(ROOT/filename)],check=True)
            for r in selected:self.assertEqual((self.root/r['file']).read_bytes(),(ROOT/r['modified_source']).read_bytes())

    def test_zip_names_reject_windows_aliases_and_absolute_paths(self):
        for name in ('../escape','C:/file','a\\b','NUL.txt','word/name.','/root','a//b','word/COM1.xml','a:b'):
            with self.subTest(name=name),self.assertRaises(ValueError):preview.part_name(name)

    def test_unknown_scratch_preserved_before_conversion(self):
        source=self.root/'in.txt';source.write_bytes(b'text');exe=self.root/'native.exe';exe.write_bytes(b'fixture')
        scratch=self.root/'scratch';scratch.mkdir();keep=scratch/'keep';keep.write_bytes(b'preserve')
        with patch.object(preview.subprocess,'run') as native,self.assertRaisesRegex(ValueError,'Unknown nonempty'):
            preview.convert('txt-to-docx',source,self.root/'out.docx',exe,scratch)
        native.assert_not_called();self.assertEqual(keep.read_bytes(),b'preserve')

    def test_native_failure_never_publishes_output(self):
        source=self.root/'in.txt';source.write_bytes(b'text');exe=self.root/'native.exe';exe.write_bytes(b'fixture')
        with patch.object(preview.subprocess,'run',return_value=subprocess.CompletedProcess([],7)),self.assertRaisesRegex(RuntimeError,'status 7'):
            preview.convert('txt-to-docx',source,self.root/'out.docx',exe,self.root/'scratch')
        self.assertFalse((self.root/'out.docx').exists());self.assertFalse((self.root/'scratch/.convert.lock').exists())


if __name__=='__main__':unittest.main()
