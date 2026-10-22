"""Actual file conversion tests against the compiled ONLYOFFICE text bridge."""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import text_docx_preview as preview


def minimal_document(body):
    return {
        '[Content_Types].xml':f'<Types xmlns="{preview.CONTENT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="{preview.MAIN}"/></Types>'.encode(),
        '_rels/.rels':f'<Relationships xmlns="{preview.RELS}"><Relationship Id="rId1" Type="{preview.OFFICE}" Target="word/document.xml"/></Relationships>'.encode(),
        'word/document.xml':f'<w:document xmlns:w="{preview.WORD}"><w:body>{body}</w:body></w:document>'.encode()}


def write_package(path,parts):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in parts.items():archive.writestr(name,data)


def paragraph_text(p):
    return ''.join(node.text or '' if node.tag=='{'+preview.WORD+'}t' else '\t' if node.tag=='{'+preview.WORD+'}tab' else '\n' if node.tag=='{'+preview.WORD+'}br' else '' for node in p.iter())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--work-dir',type=Path,required=True);a=parser.parse_args()
    fixtures=a.work_dir/'docx-fixtures';fixtures.mkdir(exist_ok=True)
    if any(fixtures.iterdir()):raise ValueError('Prior DOCX evidence remains; inspect before reusing')
    scratch=a.work_dir/'docx-scratch';details=[]
    def case(name,action):
        try:action();entry={'name':name,'passed':True}
        except Exception as error:entry={'name':name,'passed':False,'error':repr(error)}
        details.append(entry);print(('PASS ' if entry['passed'] else 'FAIL ')+name,flush=True)
    def check(condition):
        if not condition:raise AssertionError('Unexpected conversion content')
    def run(mode,source,output):return preview.convert(mode,source,output,a.exe,scratch)
    samples=[('ascii','Hello document'),('xml-special','A & B <tag> "quote" > end'),('unicode','中文 日本語 Ελληνικά 😀 𠀀'),
             ('tabs','\tA\t\tB\t'),('empty-lines','first\n\nthird'),('mixed-newlines','first\r\nsecond\rthird\nlast'),
             ('empty',''),('spaces','  leading and trailing  '),('bom','\ufeff带 BOM 文本'),('trailing-newline','one\n')]
    for name,text in samples:
        def roundtrip(name=name,text=text):
            source=fixtures/(name+'.txt');document=fixtures/(name+'.docx');back=fixtures/(name+'-back.txt')
            source.write_bytes(text.encode('utf-8'));run('txt-to-docx',source,document)
            parts=preview.read_package(document);root=ET.fromstring(parts['word/document.xml'])
            paragraphs=root.findall('{'+preview.WORD+'}body/{'+preview.WORD+'}p')
            normalized=text.removeprefix('\ufeff').replace('\r\n','\n').replace('\r','\n')
            # The native TXT reader treats a final line terminator as a terminator, not an extra paragraph.
            lines=normalized.split('\n') if normalized else []
            if normalized.endswith('\n'):lines.pop()
            check([paragraph_text(p) for p in paragraphs]==lines)
            check(all(p.find('{'+preview.WORD+'}tab') is None for p in paragraphs))
            run('docx-to-txt',document,back)
            check(back.read_bytes().decode('utf-8-sig').replace('\r\n','\n')=='\n'.join(lines))
        case(name+' actual DOCX round trip',roundtrip)
    def independent(name,body,expected):
        source=fixtures/(name+'.docx');output=fixtures/(name+'.txt');write_package(source,minimal_document(body));run('docx-to-txt',source,output)
        check(output.read_bytes().decode('utf-8-sig').replace('\r\n','\n')==expected)
    case('Independent OOXML runs tabs and paragraph breaks',lambda:independent('runs','<w:p><w:r><w:t>A &amp; B</w:t><w:tab/><w:t>中文</w:t></w:r></w:p><w:p/><w:p><w:r><w:t>😀</w:t></w:r></w:p>','A & B\t中文\n\n😀'))
    case('Independent OOXML table extraction',lambda:independent('table','<w:tbl><w:tr><w:tc><w:p><w:r><w:t>甲</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>乙</w:t></w:r></w:p></w:tc></w:tr></w:tbl>','---------------------------------------------\n|甲 |乙 |'))
    case('Table properties do not create empty columns',lambda:independent('table-properties','<w:tbl><w:tr><w:tc><w:tcPr><w:tcW w:w="4000" w:type="dxa"/></w:tcPr><w:p><w:r><w:t>甲</w:t></w:r></w:p></w:tc><w:tc><w:tcPr/><w:p><w:r><w:t>乙</w:t></w:r></w:p></w:tc></w:tr></w:tbl>','---------------------------------------------\n|甲 |乙 |'))
    def rejected(name,source,mode='docx-to-txt',existing=False):
        output=fixtures/(name+'-output.txt')
        if existing:output.write_bytes(b'KEEP ORIGINAL')
        try:run(mode,source,output)
        except (ValueError,OSError,RuntimeError,zipfile.BadZipFile,ET.ParseError):pass
        else:raise AssertionError('Invalid input unexpectedly accepted')
        check(output.read_bytes()==b'KEEP ORIGINAL' if existing else not output.exists())
    bad=fixtures/'not-a-zip.docx';bad.write_bytes(b'not a package')
    case('Malformed ZIP leaves no output',lambda:rejected('bad-zip',bad))
    missing=fixtures/'missing-body.docx';write_package(missing,minimal_document('<w:p/>')|{'word/document.xml':b'<wrong/>'})
    case('Invalid main document leaves no output',lambda:rejected('bad-main',missing))
    traversal=fixtures/'traversal.docx';write_package(traversal,minimal_document('<w:p/>')|{'../escape.txt':b'escape'})
    case('ZIP traversal rejected before native conversion',lambda:rejected('traversal',traversal))
    external=fixtures/'external.docx';write_package(external,minimal_document('<w:p/>')|{'word/_rels/document.xml.rels':f'<Relationships xmlns="{preview.RELS}"><Relationship Id="rId8" Type="hyperlink" Target="https://example.invalid/" TargetMode="External"/></Relationships>'.encode()})
    case('External relationship rejected without network access',lambda:rejected('external',external))
    dtd=fixtures/'dtd.docx';write_package(dtd,minimal_document('<w:p/>')|{'word/document.xml':f'<!DOCTYPE document [<!ENTITY x "boom">]><w:document xmlns:w="{preview.WORD}"><w:body/></w:document>'.encode()})
    case('DTD rejected before native conversion',lambda:rejected('dtd',dtd))
    invalid=fixtures/'bad-utf8.txt';invalid.write_bytes(b'\xff\xfe\x80')
    case('Invalid UTF8 leaves no output',lambda:rejected('bad-encoding',invalid,'txt-to-docx'))
    controls=fixtures/'controls.txt';controls.write_bytes(b'Hello\x00world')
    case('XML control characters rejected',lambda:rejected('controls',controls,'txt-to-docx'))
    case('Existing output preserved on valid conversion',lambda:rejected('existing',fixtures/'ascii.docx',existing=True))
    case('Missing source leaves no output',lambda:rejected('missing',fixtures/'does-not-exist.docx'))
    collision=fixtures/'case-collision.docx';write_package(collision,minimal_document('<w:p/>')|{'WORD/document.xml':b'collision'})
    case('Case colliding package parts rejected',lambda:rejected('collision',collision))
    result={'passed':sum(d['passed'] for d in details),'failed':sum(not d['passed'] for d in details)}
    (a.work_dir/'docx-native-cases.json').write_text(json.dumps(details,indent=2),'utf-8');(a.work_dir/'docx-test-result.json').write_text(json.dumps(result),'utf-8')
    print(json.dumps(result),flush=True)
    if result['failed']:raise RuntimeError('DOCX conversion tests failed; fixtures retained')


if __name__=='__main__':main()
