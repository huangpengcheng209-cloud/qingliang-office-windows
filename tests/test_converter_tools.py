import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_converter as converter


class ConverterToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=converter.verify_converter_inputs()

    def setUp(self):
        parent=Path(os.environ.get('QINGLIANG_TEST_TEMP',str(ROOT/'work')));parent.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(prefix='converter-tools-',dir=parent);self.addCleanup(temp.cleanup);self.root=Path(temp.name)

    def reject_lock(self,mutate,message):
        lock=copy.deepcopy(self.original);mutate(lock);load=json.loads
        def substitute(text,*args,**kwargs):
            value=load(text,*args,**kwargs)
            return lock if isinstance(value,dict) and 'ConverterOoxml' in value.get('profiles',{}) else value
        with patch.object(converter.json,'loads',side_effect=substitute),self.assertRaisesRegex(ValueError,message):converter.verify_converter_inputs()

    def test_core_archive_revision_cannot_be_substituted(self):
        self.reject_lock(lambda lock:lock['core_archive'].update(revision='0'*40),'Unpinned core')

    def test_v8_dependency_cannot_redirect_to_another_commit(self):
        self.reject_lock(lambda lock:lock['v8_dependencies']['build'].update(revision='0'*40),'Unpinned V8')

    def test_converter_compile_units_must_be_locked(self):
        self.reject_lock(lambda lock:lock['profiles']['x2t']['sources'].__setitem__(0,'unpublished.cpp'),'Unpinned or incomplete')

    def test_frozen_96_file_base_cannot_be_redefined(self):
        self.reject_lock(lambda lock:next(r for r in lock['files'] if r['origin']=='frozen-overlay').update(base_sha256='0'*64),'Frozen source')

    def test_unknown_existing_source_is_preserved(self):
        p=self.root/'file';p.write_bytes(b'user edit')
        with self.assertRaisesRegex(ValueError,'preserved'):converter.write_known(p,b'upstream',{'0'*64})
        self.assertEqual(p.read_bytes(),b'user edit')

    def test_hwp_links_after_math_and_converter_links_last(self):
        order=converter.link_order(self.original['profiles'])
        self.assertLess(order.index('StarMathConverter'),order.index('HWPFile'))
        self.assertLess(order.index('PdfFile'),order.index('XpsFile'))
        self.assertLess(order.index('doctrenderer'),order.index('x2t'))

    def test_cyclic_library_dependencies_stop_before_linking(self):
        profiles={'one':{'kind':'shared','libraries':['-ltwo']},'two':{'kind':'shared','libraries':['-lone']}}
        with self.assertRaisesRegex(ValueError,'Cyclic'):converter.link_order(profiles)

    def test_tar_traversal_and_unidentified_links_are_rejected(self):
        for name,link in [('../escape',False),('source-link',True)]:
            archive=self.root/'archive.tar.gz'
            with tarfile.open(archive,'w:gz') as tar:
                item=tarfile.TarInfo(name)
                if link:item.type=tarfile.SYMTYPE;item.linkname='elsewhere'
                else:item.size=1
                tar.addfile(item,None if link else io.BytesIO(b'x'))
            with self.subTest(name=name),self.assertRaises(ValueError):converter.extract_tar(archive,{'files':[]},self.root/'output')
            self.assertFalse((self.root/'output').exists())

    def test_changed_tar_timestamp_preserves_pinned_source_identity(self):
        data=b'pinned source\n';row={'files':[{'file':'input.cc','sha256':hashlib.sha256(data).hexdigest()}]};hashes=[]
        for timestamp in [1,2]:
            archive=self.root/('transport-'+str(timestamp)+'.tar.gz')
            with tarfile.open(archive,'w:gz') as tar:
                item=tarfile.TarInfo('input.cc');item.size=len(data);item.mtime=timestamp;tar.addfile(item,io.BytesIO(data))
            hashes.append(hashlib.sha256(archive.read_bytes()).hexdigest());converter.extract_tar(archive,row,self.root/'output')
        self.assertNotEqual(hashes[0],hashes[1]);self.assertEqual((self.root/'output/input.cc').read_bytes(),data)

    def test_changed_tar_source_bytes_are_rejected_before_writing(self):
        archive=self.root/'bad-source.tar.gz';row={'files':[{'file':'input.cc','sha256':hashlib.sha256(b'original').hexdigest()}]}
        with tarfile.open(archive,'w:gz') as tar:
            item=tarfile.TarInfo('input.cc');item.size=4;tar.addfile(item,io.BytesIO(b'edit'))
        with self.assertRaisesRegex(ValueError,'TAR input differs'):converter.extract_tar(archive,row,self.root/'output')
        self.assertFalse((self.root/'output').exists())

    def test_unindexed_tar_file_is_rejected_before_writing(self):
        archive=self.root/'extra-file.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            item=tarfile.TarInfo('extra.cc');item.size=1;tar.addfile(item,io.BytesIO(b'x'))
        with self.assertRaisesRegex(ValueError,'file set differs'):converter.extract_tar(archive,{'files':[]},self.root/'output')
        self.assertFalse((self.root/'output').exists())

    def test_transient_gitiles_download_error_retries_then_verifies_source(self):
        payload=io.BytesIO();data=b'public pinned code'
        with tarfile.open(fileobj=payload,mode='w:gz') as tar:
            item=tarfile.TarInfo('source.cc');item.size=len(data);tar.addfile(item,io.BytesIO(data))
        row={'archive':'source.tar.gz','url':'https://chromium.googlesource.com/example/+archive/'+'1'*40+'.tar.gz','revision':'1'*40,'sha256':'0'*64,'files':[{'file':'source.cc','sha256':hashlib.sha256(data).hexdigest()}]}
        transient=urllib.error.HTTPError(row['url'],503,'unavailable',None,None)
        with patch.object(converter.urllib.request,'urlopen',side_effect=[transient,io.BytesIO(payload.getvalue())]) as download,patch.object(converter.time,'sleep'):
            converter.prepare_v8_dependency(self.root,'build',row,self.root/'core')
        self.assertEqual(download.call_count,2);self.assertEqual((self.root/'core'/converter.V8_PATH/'build/source.cc').read_bytes(),data)

    def test_new_converter_patches_reconstruct_exact_bases(self):
        rows=[r for r in self.original['files'] if r.get('patch','').startswith('converter-patches/')]
        archives=list(self.original['support_archives'].values())+[{**a,'destination':converter.V8_PATH+'/'+n} for n,a in self.original['v8_dependencies'].items()]
        rows += [{**r,'file':a['destination']+'/'+r['file'],'sha256':r['result_sha256']} for a in archives for r in a.get('patches',[]) if r['patch'].startswith('converter-patches/')]
        subprocess.run(['git','init','--quiet',str(self.root)],check=True)
        command=['git','-c','core.autocrlf=false','-C',str(self.root),'apply','--whitespace=nowarn']
        for row in rows:
            target=self.root/row['file'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/row['modified_source'],target)
        for filename in sorted({r['patch'] for r in rows}):
            selected=[r for r in rows if r['patch']==filename];subprocess.run(command+['--reverse',str(ROOT/filename)],check=True)
            for r in selected:self.assertEqual(hashlib.sha256((self.root/r['file']).read_bytes()).hexdigest(),r['base_sha256'])
            subprocess.run(command+[str(ROOT/filename)],check=True)
            for r in selected:self.assertEqual((self.root/r['file']).read_bytes(),(ROOT/r['modified_source']).read_bytes())


if __name__=='__main__':unittest.main()
