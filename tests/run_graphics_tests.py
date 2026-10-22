"""Run graphics DLL integration tests with bounded runtime and retained failure fixtures."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_dependencies import sha
from build_graphics import verify_graphics_inputs


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exe',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True);a=p.parse_args()
    verify_graphics_inputs()
    out=a.work_dir/'graphics-fixtures';out.mkdir(exist_ok=True)
    if any(out.iterdir()):raise ValueError('Prior graphics test evidence remains; inspect before reusing')
    result_path=a.work_dir/'graphics-test-result.json'
    if result_path.exists():result_path.unlink()
    result=subprocess.run([str(a.exe),str(out),str(a.work_dir/'sources/core'),str(a.work_dir/'heif-fixtures')],cwd=a.work_dir/'bin',capture_output=True,text=True,encoding='utf-8',timeout=180)
    print(result.stderr,end='');print(result.stdout,end='')
    (a.work_dir/'graphics-native-output.txt').write_text(result.stderr+result.stdout,'utf-8')
    if result.returncode:raise RuntimeError('Native graphics tests failed; evidence retained')
    totals=json.loads(result.stdout);result_path.write_text(json.dumps(totals),'utf-8')
    if totals!={'passed':21,'failed':0}:raise RuntimeError('Expected 21 passing graphics scenarios')


if __name__=='__main__':main()
