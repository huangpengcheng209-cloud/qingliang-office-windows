"""Convert UTF-8 TXT and ordinary DOCX with the built Windows native preview."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile

WORD='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
RELS='http://schemas.openxmlformats.org/package/2006/relationships'
OFFICE='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument'
CONTENT='http://schemas.openxmlformats.org/package/2006/content-types'
MAIN='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'
MAX_PARTS=2048
MAX_EXPANDED=128*1024*1024
MAX_PART=32*1024*1024
MAX_TEXT=16*1024*1024


def part_name(name):
    if not name or '\\' in name or ':' in name or name.startswith('/') or '\x00' in name:
        raise ValueError('Unsafe package part name')
    components=name.rstrip('/').split('/')
    reserved={'con','prn','aux','nul',*(f'com{i}' for i in range(1,10)),*(f'lpt{i}' for i in range(1,10))}
    if any(p in ('','.','..') or p[-1:] in (' ','.') or p.split('.')[0].casefold() in reserved or any(ord(c)<32 or c in '<>"|?*' for c in p) for p in components):
        raise ValueError('Unsafe package part name')
    return '/'.join(components)


def xml_part(data):
    text=data.decode('utf-8-sig')
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b',text,re.I):raise ValueError('DTD and entity declarations are outside this preview')
    return ET.fromstring(text)


def validate_package(parts):
    required={'[Content_Types].xml','_rels/.rels','word/document.xml'}
    if not required.issubset(parts):raise ValueError('Missing required DOCX package parts')
    trees={name:xml_part(data) for name,data in parts.items() if name.endswith(('.xml','.rels'))}
    types=trees['[Content_Types].xml']
    if types.tag!='{'+CONTENT+'}Types' or not any(p.get('PartName')=='/word/document.xml' and p.get('ContentType')==MAIN for p in types):
        raise ValueError('Only ordinary DOCX main documents are supported')
    root_rels=trees['_rels/.rels']
    main=[p for p in root_rels if p.get('Type')==OFFICE]
    if root_rels.tag!='{'+RELS+'}Relationships' or len(main)!=1 or main[0].get('Target')!='word/document.xml':
        raise ValueError('Unsupported DOCX main document relationship')
    for name,tree in trees.items():
        if not name.endswith('.rels'):continue
        if tree.tag!='{'+RELS+'}Relationships':raise ValueError('Invalid relationship part')
        for rel in tree:
            target=unquote(rel.get('Target',''))
            if rel.get('TargetMode','Internal')!='Internal' or urlsplit(target).scheme or target.startswith(('/','\\')) or '\\' in target:
                raise ValueError('External relationships are outside this offline preview')
            # Resolve relative OPC targets without allowing filesystem escapes.
            parent=PurePosixPath(name).parent.parent if name!='_rels/.rels' else PurePosixPath('.')
            resolved=list(parent.parts)
            for component in target.split('#',1)[0].split('/'):
                if component=='..':
                    if not resolved:raise ValueError('Relationship escapes the package')
                    resolved.pop()
                elif component not in ('','.') :resolved.append(component)
            if '/'.join(resolved) not in parts:raise ValueError('Missing relationship target')
    document=trees['word/document.xml']
    if document.tag!='{'+WORD+'}document' or document.find('{'+WORD+'}body') is None:raise ValueError('Invalid Word document body')


def read_package(source):
    if source.stat().st_size>64*1024*1024:raise ValueError('DOCX exceeds the preview size limit')
    parts={};seen=set();expanded=0
    with zipfile.ZipFile(source) as archive:
        if len(archive.infolist())>MAX_PARTS:raise ValueError('Too many DOCX parts')
        for info in archive.infolist():
            name=part_name(info.filename)
            if name.casefold() in seen:raise ValueError('Duplicate or case-colliding DOCX parts')
            seen.add(name.casefold())
            if stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1:raise ValueError('Links and encrypted parts are unsupported')
            expanded+=info.file_size
            if info.file_size>MAX_PART or expanded>MAX_EXPANDED:raise ValueError('Expanded DOCX exceeds preview limits')
            if not info.is_dir():parts[name]=archive.read(info)
    validate_package(parts)
    return parts


def convert(mode,source,output,exe,work_dir):
    source=Path(source).resolve();output=Path(output).absolute();exe=Path(exe).resolve();work=Path(work_dir).resolve()
    if mode not in ('txt-to-docx','docx-to-txt'):raise ValueError('Unknown conversion mode')
    if not source.is_file() or not exe.is_file():raise ValueError('Input file or built native preview is missing')
    if output.exists() or output.is_symlink():raise FileExistsError('Output already exists; choose a new filename')
    if not output.parent.is_dir():raise ValueError('Output directory does not exist')
    if source==output:raise ValueError('Input and output must differ')
    marker=work/'.qingliang-text-preview'
    if work.exists() and any(work.iterdir()) and not marker.is_file():raise ValueError('Unknown nonempty scratch directory; preserved')
    work.mkdir(parents=True,exist_ok=True);marker.write_text('Rebuildable text conversion scratch.\n','utf-8')
    lock=os.open(work/'.convert.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        with tempfile.TemporaryDirectory(prefix='convert-',dir=work) as temporary:
            temp=Path(temporary);package=temp/'package';package.mkdir();result=temp/'result'
            if mode=='txt-to-docx':
                if source.stat().st_size>MAX_TEXT:raise ValueError('TXT exceeds the preview size limit')
                text=source.read_bytes().decode('utf-8-sig')
                if any(ord(c)<32 and c not in '\t\r\n' or ord(c) in (0xfffe,0xffff) for c in text):raise ValueError('TXT contains unsupported XML control characters')
                normalized=temp/'input.txt';normalized.write_bytes(text.encode('utf-8'))
                native_input,native_output=normalized,package
            else:
                for name,data in read_package(source).items():
                    target=package/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
                native_input,native_output=package,result
            env=os.environ.copy();env['PATH']=str(exe.parent)+os.pathsep+env.get('PATH','')
            native=subprocess.run([str(exe),mode,str(native_input),str(native_output)],cwd=temp,env=env,capture_output=True,timeout=60)
            if native.returncode:raise RuntimeError('Native converter failed with status '+str(native.returncode))
            if mode=='txt-to-docx':
                parts={p.relative_to(package).as_posix():p.read_bytes() for p in package.rglob('*') if p.is_file()}
                validate_package(parts)
                with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as archive:
                    for name,data in sorted(parts.items()):archive.writestr(name,data)
                read_package(result)
            else:result.read_bytes().decode('utf-8-sig')
            # Exclusive create protects existing outputs even if another process wins the race.
            fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o666)
            try:
                with os.fdopen(fd,'wb') as target,result.open('rb') as original:
                    shutil.copyfileobj(original,target);target.flush();os.fsync(target.fileno())
            except BaseException:
                output.unlink(missing_ok=True);raise
        return {'mode':mode,'output':str(output),'bytes':output.stat().st_size}
    finally:
        os.close(lock);(work/'.convert.lock').unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('txt-to-docx','docx-to-txt'));parser.add_argument('input',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--work-dir',type=Path,required=True)
    args=parser.parse_args()
    try:print(json.dumps(convert(args.mode,args.input,args.output,args.exe,args.work_dir),ensure_ascii=True))
    except (ValueError,OSError,RuntimeError,zipfile.BadZipFile,ET.ParseError,subprocess.TimeoutExpired) as error:parser.exit(1,str(error)+'\n')


if __name__=='__main__':main()
