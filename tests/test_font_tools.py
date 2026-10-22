import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_fonts


class FontToolTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('QINGLIANG_TEST_TEMP', str(ROOT / 'work')))
        parent.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix='font-tool-', dir=parent)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.core = self.root / 'core'
        self.core.mkdir()
        self.archive = self.root / 'source.zip'
        self.row = {'root':'project-pin', 'destination':'vendor/project', 'skipped_symlinks':{},
                    'files':[{'file':'src/a.c', 'sha256':hashlib.sha256(b'source').hexdigest()}]}

    def zip(self, extra=()):
        with zipfile.ZipFile(self.archive,'w') as z:
            z.writestr('project-pin/src/a.c', b'source')
            for name, value in extra:
                z.writestr(name, value)

    def link(self):
        info = zipfile.ZipInfo('project-pin/README')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        return info

    def test_traversal_rejected_before_any_extraction(self):
        self.zip([('project-pin/../../escape', b'bad')])
        with self.assertRaisesRegex(ValueError,'Unsafe'):
            build_fonts.extract_selected(self.archive,self.row,self.core)
        self.assertEqual(list(self.core.iterdir()),[])

    def test_unexpected_link_rejected_before_any_extraction(self):
        self.zip([(self.link(),b'../../outside')])
        with self.assertRaisesRegex(ValueError,'symbolic link'):
            build_fonts.extract_selected(self.archive,self.row,self.core)
        self.assertEqual(list(self.core.iterdir()),[])

    def test_pinned_readme_link_skipped_without_creating_filesystem_link(self):
        self.row['skipped_symlinks'] = {'README':'README.md'}
        self.zip([(self.link(),b'README.md')])
        target = build_fonts.extract_selected(self.archive,self.row,self.core)
        self.assertEqual((target/'src/a.c').read_bytes(),b'source')
        self.assertFalse((target/'README').exists())

    def test_existing_user_modification_preserved(self):
        self.zip()
        target = self.core/self.row['destination']/'src/a.c'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'user change')
        with self.assertRaisesRegex(ValueError,'preserved'):
            build_fonts.extract_selected(self.archive,self.row,self.core)
        self.assertEqual(target.read_bytes(),b'user change')

    def test_case_colliding_archive_members_rejected(self):
        self.zip([('project-pin/src/A.c',b'collision')])
        with self.assertRaisesRegex(ValueError,'case-colliding'):
            build_fonts.extract_selected(self.archive,self.row,self.core)
        self.assertEqual(list(self.core.iterdir()),[])

    def test_corrupted_selected_input_rejected_before_writing(self):
        self.zip()
        self.row['files'][0]['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            build_fonts.extract_selected(self.archive,self.row,self.core)
        self.assertEqual(list(self.core.iterdir()),[])

    def test_onlyoffice_adaptation_patch_reconstructs_archive_base(self):
        lock = build_fonts.verify_font_inputs()
        row = lock['archives']['harfbuzz']
        overlay = row['patches'][0]
        core = self.core
        subprocess.run(['git','init','--quiet',str(core)],check=True)
        target = core/row['destination']/overlay['file']
        target.parent.mkdir(parents=True)
        shutil.copyfile(ROOT/overlay['modified_source'],target)
        command = ['git','-c','core.autocrlf=false','-C',str(core),'apply','--whitespace=nowarn']
        subprocess.run(command+['-R',str(ROOT/overlay['patch'])],check=True)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),overlay['base_sha256'])
        subprocess.run(command+[str(ROOT/overlay['patch'])],check=True)
        self.assertEqual(target.read_bytes(),(ROOT/overlay['modified_source']).read_bytes())

    def test_unpinned_compile_unit_rejected(self):
        lock = build_fonts.verify_font_inputs()
        lock = copy.deepcopy(lock)
        lock['profiles']['harfbuzz']['sources'][0] = 'unlisted.cc'
        original = json.loads
        def load(text, *args, **kwargs):
            data = original(text,*args,**kwargs)
            return lock if isinstance(data,dict) and 'golden_cases' in data else data
        with patch.object(build_fonts.json,'loads',side_effect=load), self.assertRaisesRegex(ValueError,'Unpinned'):
            build_fonts.verify_font_inputs()


if __name__ == '__main__':
    unittest.main()
