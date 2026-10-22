"""Complete the single cached CEF SDK with matching sample utility sources."""
import hashlib,json,re,tarfile
from pathlib import Path
from zipfile import ZipFile
import requests
TASK=Path(r'D:\CodexWorkspaces\2026-10-13\office-windows');STAGE=Path(r'D:\CodexCache\office-windows')
sdk=STAGE/'build/cef-upgrade-preflight'
header=(sdk/'include/cef_version.h').read_text()
revision=re.search(r'#define CEF_COMMIT_HASH "([a-f0-9]+)"',header)[1]
target=STAGE/'downloads'/f'cef-{revision}.zip';url=f'https://codeload.github.com/chromiumembedded/cef/zip/{revision}'
if not target.exists():
    response=requests.get(url,timeout=(30,180));response.raise_for_status();target.write_bytes(response.content)
count=0
with ZipFile(target) as source:
    assert source.testzip() is None
    for name in source.namelist():
        p=Path(name)
        if len(p.parts)<3 or p.parts[1] not in ('tests',):continue
        relative=Path(*p.parts[1:]);out=(sdk/relative).resolve();assert out.is_relative_to(sdk.resolve())
        if name.endswith('/'):out.mkdir(parents=True,exist_ok=True)
        else:out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(source.read(name));count+=1
archive=next((STAGE/'downloads').glob('cef_binary_150.0.22*windows64_minimal.tar.bz2'))
with tarfile.open(archive,'r|bz2') as source:
    for member in source:
        p=Path(member.name)
        if member.isfile() and len(p.parts)==2 and p.name in ('cef_paths.cmake','cef_paths2.cmake'):
            (sdk/p.name).write_bytes(source.extractfile(member).read())
report={'revision':revision,'source_url':url,'cache_archive':str(target),'archive_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'matching_test_utility_files':count,'sdk':str(sdk),'release_replaced':False}
(TASK/'evidence/cef150-build-source-preparation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'revision':revision,'test_utility_files':count,'release_replaced':False}))
