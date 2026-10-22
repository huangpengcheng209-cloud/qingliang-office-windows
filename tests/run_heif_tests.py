"""Run bounded native HEIC tests with pinned upstream fixtures and preserve failure evidence."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_heif import verify_heif_inputs
from build_dependencies import sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',required=True,type=Path)
    parser.add_argument('--work-dir',required=True,type=Path)
    args=parser.parse_args()
    lock=verify_heif_inputs()
    row=lock['archives']['libheif']
    source=args.work_dir/'sources/core'/row['destination']
    for name in ('examples/example.heic','examples/example.avif'):
        expected=next(r['sha256'] for r in row['files'] if r['file']==name)
        if sha(source/name)!=expected:raise ValueError('Changed upstream HEIF fixture; preserved')
    folder=args.work_dir/'heif-fixtures'
    folder.mkdir(exist_ok=True)
    if any(folder.iterdir()):raise ValueError('Prior HEIF test evidence remains; inspect before reusing')
    result_path=args.work_dir/'heif-test-result.json'
    if result_path.exists():result_path.unlink()
    result=subprocess.run([str(args.exe),str(folder),str(source)],capture_output=True,text=True,encoding='utf-8',timeout=180)
    print(result.stderr,end='')
    print(result.stdout,end='')
    if result.returncode:raise RuntimeError('Native HEIF tests failed; fixture evidence retained')
    totals=json.loads(result.stdout)
    result_path.write_text(json.dumps(totals),'utf-8')
    if totals!={'passed':16,'failed':0}:raise RuntimeError('Expected all 16 native HEIF scenarios')


if __name__=='__main__':main()
