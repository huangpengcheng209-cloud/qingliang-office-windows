import sys,json,hashlib,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import build_windows_components as b
b.PROJECTS['docx-renderer']=b.CORE/'DocxRenderer/DocxRenderer.pro'
started=time.time(); b.build_project('docx-renderer',b.environment())
target=b.CORE/'build/lib/win_64/DocxRenderer.dll'
report={'component':'DocxRenderer.dll','source_project':str(b.PROJECTS['docx-renderer']),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size,'seconds':round(time.time()-started,1),'source_behavior_patch':True,'reason':'Canonicalize bundled URW PDF base-font family names before substitution; prevents installed-font-order dependent Latin glyph metrics'}
(b.TASK/'evidence/docx-renderer-build.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
