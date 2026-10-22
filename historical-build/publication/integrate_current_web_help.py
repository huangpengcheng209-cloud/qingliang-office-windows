import hashlib,json,psutil,shutil
from pathlib import Path
TASK=Path(r'D:\CodexWorkspaces\2026-10-13\office-windows');STAGE=Path(r'D:\CodexCache\office-windows');APP=STAGE/'candidate/app';OUT=STAGE/'build/web-apps'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not any((p.info['exe'] or '').lower().startswith(str(APP).lower()+'\\') for p in psutil.process_iter(['exe'])),'Close candidate before integration'
reports=json.loads((TASK/'evidence/web-controllers-build.json').read_text(encoding='utf-8'));rows=[]
for report in reports:
 for record in [report,report['postload']]:
  assert all(sha(Path(p))==h for p,h in record['inputs'].items()),'Frontend source changed after build'
  source=Path(record['output']);assert sha(source)==record['output_sha256'];target=APP/'editors/web-apps/apps'/source.relative_to(OUT);shutil.copyfile(source,target)
  rows.append({'file':target.relative_to(APP).as_posix(),'sha256':sha(target)})
 report['integrated']=True;report['windows_functional_acceptance']='pending current frontend; local language fallback focused checks passed'
(TASK/'evidence/web-controllers-build.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
help_report=json.loads((TASK/'evidence/cef150-offline-help-preparation.json').read_text(encoding='utf-8'))
for item in help_report['files']:
 source=OUT/item['file'];assert sha(source)==item['sha256'];target=APP/'editors/web-apps/apps'/item['file'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);assert sha(target)==item['sha256']
help_report['integrated']=True;help_report['native_gui_acceptance']='pending';(TASK/'evidence/cef150-offline-help-preparation.json').write_text(json.dumps(help_report,indent=2),encoding='utf-8')
(TASK/'evidence/cef150-web-help-integration.json').write_text(json.dumps({'bundles':rows,'help_files':len(help_report['files']),'help_index_targets_valid':True,'candidate_only':True,'final_win3_replaced':False,'native_gui_acceptance':'pending'},indent=2),encoding='utf-8')
print(json.dumps({'bundles':len(rows),'help_files':len(help_report['files']),'candidate_only':True,'gui_acceptance':'pending'}))
