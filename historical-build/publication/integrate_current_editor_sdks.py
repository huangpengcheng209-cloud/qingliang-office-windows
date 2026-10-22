import argparse,hashlib,json,os,psutil,shutil,subprocess,time
from pathlib import Path
TASK=Path(r'D:\CodexWorkspaces\2026-10-13\office-windows');STAGE=Path(r'D:\CodexCache\office-windows');SDK=STAGE/'upstream/DesktopEditors/sdkjs';APP=STAGE/'candidate/app'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not any((p.info['exe'] or '').lower()==str(APP/'editors.exe').lower() for p in psutil.process_iter(['exe'])),'Close candidate before replacing bundles'
records=[]
parser=argparse.ArgumentParser();parser.add_argument('--editors',nargs='+',choices=['word','cell','slide','visio'],default=['word','slide','visio']);args=parser.parse_args()
for editor in args.editors:
 report_path=TASK/('evidence/'+editor+'-sdk-build.json');report=json.loads(report_path.read_text(encoding='utf-8'))
 assert all(sha(SDK/p)==digest for p,digest in report['inputs'].items()),editor+' source changed'
 for source,digest in report['outputs'].items():
  source=Path(source);assert sha(source)==digest
  target=APP/'editors/sdkjs'/editor/source.name;before=sha(target);shutil.copyfile(source,target)
  records.append({'editor':editor,'file':str(target),'previous_sha256':before,'sha256':sha(target)})
 report['integrated']=True;report['windows_functional_acceptance']='requires current bundle runtime checks';report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
started=time.time()
result=subprocess.run([str(APP/'converter/x2t.exe'),'-create-js-snapshots'],cwd=APP/'converter',env=dict(os.environ,TEMP=str(STAGE/'tmp'),TMP=str(STAGE/'tmp')),capture_output=True,timeout=120)
(STAGE/'logs/cef150-js-snapshot-regeneration.log').write_bytes(result.stdout+result.stderr)
assert result.returncode==0,result.returncode
snapshots=[{'file':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in (APP/'editors/sdkjs').rglob('sdk-all*.bin')]
assert len(snapshots)==5,len(snapshots)
(TASK/'evidence/cef150-editor-sdk-integration.json').write_text(json.dumps({'files':records,'snapshots':snapshots,'snapshot_exit':0,'snapshot_seconds':round(time.time()-started,1),'release_ready':False},indent=2),encoding='utf-8')
print(json.dumps({'bundles_integrated':len(records),'snapshots_regenerated':len(snapshots),'seconds':round(time.time()-started,1)}))
