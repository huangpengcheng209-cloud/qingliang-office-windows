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
import build_heif


class HeifToolTests(unittest.TestCase):
    def setUp(self):
        parent=Path(os.environ.get('QINGLIANG_TEST_TEMP',str(ROOT/'work')))
        parent.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(prefix='heif-tool-',dir=parent)
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.lock=copy.deepcopy(build_heif.verify_heif_inputs())

    def rejects(self,message):
        original=json.loads
        def load(text,*args,**kwargs):
            data=original(text,*args,**kwargs)
            return self.lock if isinstance(data,dict) and 'cmake_version_range' in data else data
        with patch.object(build_heif.json,'loads',side_effect=load),self.assertRaisesRegex(ValueError,message):
            build_heif.verify_heif_inputs()

    def test_different_core_revision_rejected(self):
        self.lock['revision']='0'*40
        self.rejects('identity differs')

    def test_archive_origin_substitution_rejected(self):
        self.lock['archives']['x265']['url']='https://example.com/unreviewed.zip'
        self.rejects('archive origin')

    def test_case_colliding_input_rejected(self):
        rows=self.lock['archives']['libde265']['files']
        rows.append({**rows[0],'file':rows[0]['file'].upper()})
        self.rejects('Duplicate HEIF')

    def test_cmake_source_path_traversal_rejected(self):
        self.lock['profiles']['x265']['source_subdirectory']='../../outside'
        self.rejects('Unsafe')

    def test_different_runtime_profile_rejected(self):
        self.lock['runtime']='MultiThreaded'
        self.rejects('Unexpected HEIF build profile')

    def test_cmake_four_rejected_before_configuring_sources(self):
        exe=self.root/'cmake.exe';exe.write_bytes(b'fixture')
        with patch.object(build_heif.subprocess,'check_output',return_value='cmake version 4.2.0\n'),self.assertRaisesRegex(ValueError,'requires CMake'):
            build_heif.cmake_tool(self.root,exe)

    def test_patches_reconstruct_exact_archive_bases_and_results(self):
        subprocess.run(['git','init','--quiet',str(self.root)],check=True)
        command=['git','-c','core.autocrlf=false','-C',str(self.root),'apply','--whitespace=nowarn']
        for row in self.lock['archives'].values():
            for overlay in row.get('patches',[]):
                target=self.root/row['destination']/overlay['file']
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/overlay['modified_source'],target)
                subprocess.run(command+['-R',str(ROOT/overlay['patch'])],check=True)
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),overlay['base_sha256'])
                subprocess.run(command+[str(ROOT/overlay['patch'])],check=True)
                self.assertEqual(target.read_bytes(),(ROOT/overlay['modified_source']).read_bytes())


if __name__=='__main__':unittest.main()
