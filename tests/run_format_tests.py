"""Run isolated native format cases so malformed input cannot hide crashes or hang the suite."""
import argparse
import json
import subprocess
from pathlib import Path

CASES=['UTF8 BOM and mixed newlines','UTF8 no BOM','UTF16 LE and supplementary character','UTF16 BE and supplementary character',
       'GBK explicit encoding','Empty lines preserved','Repeated read line count','Empty read resets count','Missing text input',
       'Big endian writer preserves const input','Big endian exact bytes and readback','Little endian exact bytes and readback',
       'UTF8 exact bytes and no trailing newline','Unicode emoji path','Invalid output path','BOM only text',
       'Raw VBA project stream','Compressed literal VBA chunk','Overlapping VBA copy token','Uncompressed 4096 byte chunk',
       'Multiple VBA chunks','Module text offset before compression signature','Exact boundary scalar read','Rollback clamps at zero',
       'Seek clamps at end','Overflowing skip clamps at end','Eight byte alignment','Zero alignment',
       'Truncated VBA chunk header','Truncated raw VBA chunk','Invalid backward VBA copy','Missing VBA file',
       'Copy token bit width above sixteen literals','Oversized decompressed VBA chunk rejected','Module offset beyond stream rejected','Bounded block read at end']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exe',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True);a=p.parse_args()
    out=a.work_dir/'format-fixtures';out.mkdir(exist_ok=True)
    if any(out.iterdir()):raise ValueError('Prior format evidence remains; inspect before reusing')
    result_path=a.work_dir/'format-test-result.json'
    if result_path.exists():result_path.unlink()
    details=[]
    for index,name in enumerate(CASES):
        fixture=out/str(index);fixture.mkdir()
        try:
            r=subprocess.run([str(a.exe),str(index),str(fixture)],cwd=a.work_dir/'bin',capture_output=True,text=True,encoding='utf-8',timeout=10)
            entry={'case':index,'name':name,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'passed':r.returncode==0 and r.stdout.strip()=='PASS'}
        except subprocess.TimeoutExpired:
            entry={'case':index,'name':name,'passed':False,'timeout':True}
        details.append(entry);print(('PASS ' if entry['passed'] else 'FAIL ')+name,flush=True)
    result={'passed':sum(r['passed'] for r in details),'failed':sum(not r['passed'] for r in details)}
    (a.work_dir/'format-native-cases.json').write_text(json.dumps(details,indent=2),'utf-8')
    result_path.write_text(json.dumps(result),'utf-8');print(json.dumps(result),flush=True)
    if result['failed']:raise RuntimeError('Native format cases failed; outputs retained')


if __name__=='__main__':main()
