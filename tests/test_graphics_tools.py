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
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_graphics as graphics


class GraphicsToolTests(unittest.TestCase):
    def setUp(self):
        parent=Path(os.environ.get('QINGLIANG_TEST_TEMP',str(ROOT/'work')))
        parent.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(prefix='graphics-tool-',dir=parent)
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.lock=copy.deepcopy(graphics.verify_graphics_inputs())

    def rejects(self,message):
        original=json.loads
        def load(text,*args,**kwargs):
            value=original(text,*args,**kwargs)
            return self.lock if isinstance(value,dict) and 'captured_profile' in value else value
        with patch.object(graphics.json,'loads',side_effect=load),self.assertRaisesRegex(ValueError,message):
            graphics.verify_graphics_inputs()

    def test_different_core_revision_rejected(self):
        self.lock['revision']='0'*40
        self.rejects('identity differs')

    def test_core_repository_substitution_rejected(self):
        self.lock['repository']='https://github.com/example/core'
        self.rejects('identity differs')

    def test_case_colliding_core_input_rejected(self):
        row=self.lock['files'][0]
        self.lock['files'].append({**row,'file':row['file'].upper()})
        self.rejects('Duplicate graphics')

    def test_frozen_source_base_must_match_original_manifest(self):
        row=next(row for row in self.lock['files'] if row['origin']=='frozen-overlay')
        row['base_sha256']='0'*64
        self.rejects('original 96-file identity')

    def test_support_archive_origin_substitution_rejected(self):
        self.lock['archives']['hyphen']['url']='https://example.com/hyphen.zip'
        self.rejects('archive origin')

    def test_parser_patch_base_must_match_archive(self):
        self.lock['archives']['katana']['patches'][0]['base_sha256']='0'*64
        self.rejects('base differs from archive')

    def test_unpinned_compile_unit_rejected(self):
        self.lock['sources'][0]='unreviewed.cpp'
        self.rejects('Unpinned graphics compile unit')

    def test_colliding_path_names_keep_separate_object_directories(self):
        sources=['Metafile/Common/CPath.cpp','Metafile/svg/SvgObjects/CPath.cpp','regular.cpp']
        groups=graphics.source_groups(sources)
        self.assertEqual(sorted(source for group in groups for source in group),sorted(sources))
        self.assertEqual(len(groups),2)
        self.assertTrue(all(len(group)==len({Path(source).stem.casefold() for source in group}) for group in groups))

    def test_new_patches_reconstruct_exact_base_and_modified_bytes(self):
        rows=[row for row in self.lock['files'] if row.get('patch','').startswith('graphics-patches/')]
        rows += [{**row,'target':archive['destination']+'/'+row['file'],'sha256':row['result_sha256']}
                 for archive in self.lock['archives'].values() for row in archive.get('patches',[])]
        subprocess.run(['git','init','--quiet',str(self.root)],check=True)
        command=['git','-c','core.autocrlf=false','-C',str(self.root),'apply','--whitespace=nowarn']
        for row in rows:
            target=self.root/row.get('target',row['file'])
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/row['modified_source'],target)
        for patch_file in sorted({row['patch'] for row in rows}):
            selected=[row for row in rows if row['patch']==patch_file]
            subprocess.run(command+['-R',str(ROOT/patch_file)],check=True)
            for row in selected:
                target=self.root/row.get('target',row['file'])
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),row['base_sha256'])
            subprocess.run(command+[str(ROOT/patch_file)],check=True)
            for row in selected:
                self.assertEqual((self.root/row.get('target',row['file'])).read_bytes(),(ROOT/row['modified_source']).read_bytes())

    def test_unlisted_external_header_rejected_and_preserved(self):
        core=self.root/'core';boost=self.root/'boost';sdk=self.root/'sdk'
        core.mkdir();boost.mkdir();sdk.mkdir()
        source=core/'test.cpp';source.write_bytes(b'// fixture')
        unknown=self.root/'unreviewed/header.h';unknown.parent.mkdir();unknown.write_bytes(b'preserve me')
        directory=self.root/'graphics-build/group-0/dependencies';directory.mkdir(parents=True)
        (directory/'test.json').write_text(json.dumps({'Data':{'Source':str(source),'Includes':[str(unknown)]}}),'utf-8')
        lock={'files':[],'archives':{},'boost':{'files':[]},'sources':['test.cpp'],'generated_headers':[]}
        with patch.object(graphics,'verify_font_inputs',return_value={'archives':{}}),patch.object(graphics,'verify_heif_inputs',return_value={'archives':{}}),self.assertRaisesRegex(ValueError,'outside MSVC and Windows SDK'):
            graphics.audit_compiler_inputs(self.root,core,boost,lock,{'WINDOWSSDKDIR':str(sdk)})
        self.assertEqual(unknown.read_bytes(),b'preserve me')


if __name__=='__main__':unittest.main()
