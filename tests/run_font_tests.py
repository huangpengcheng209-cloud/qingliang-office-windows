"""Compare new native libraries with pinned upstream shaping goldens and font/decoder fixtures."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_dependencies import sha
from build_fonts import verify_font_inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', required=True, type=Path)
    parser.add_argument('--work-dir', required=True, type=Path)
    args = parser.parse_args()
    lock = verify_font_inputs()
    core = args.work_dir / 'sources/core'
    hb = core / lock['archives']['harfbuzz']['destination']
    brotli = core / lock['archives']['brotli']['destination']
    result_path = args.work_dir / 'fonts-test-result.json'
    if result_path.exists():
        result_path.unlink()
    # Recheck every test font and golden file against the archive identities before execution.
    for name, row in lock['archives'].items():
        root = core / row['destination']
        for entry in row['files']:
            if entry['file'].startswith(('test/', 'tests/', 'perf/')) and sha(root / entry['file']) != entry['sha256']:
                raise ValueError('Changed font test fixture; preserved')
    command = [str(args.exe), 'self', str(hb / 'perf/fonts/Roboto-Regular.ttf'),
               str(hb / 'perf/fonts/Amiri-Regular.ttf'), str(brotli / 'tests/testdata'),
               str(args.work_dir / 'fonts-raster.pgm')]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding='utf-8', timeout=120)
    print(result.stderr, end='')
    totals = json.loads(result.stdout)
    if totals != {'passed':12, 'failed':0} or result.returncode:
        raise RuntimeError('Native font/decoder integration tests failed: ' + result.stdout)
    details = []
    for case in lock['golden_cases']:
        # Assert the recorded expectation really is a line from the fixed upstream test file.
        line = (hb / case['test']).read_text('utf-8').splitlines()[case['line']-1]
        _, options, codepoints, expected = line.split(';',3)
        if (options, codepoints, expected) != (case['options'], case['codepoints'], case['expected']):
            raise ValueError('Recorded golden differs from pinned upstream test line')
        actual = subprocess.check_output([str(args.exe), 'golden', str(hb / case['font']), codepoints],
                                         text=True, encoding='utf-8', timeout=30).strip()
        ok = actual == expected
        totals['passed' if ok else 'failed'] += 1
        details.append({'suite':case['suite'], 'line':case['line'], 'expected':expected,'actual':actual,'passed':ok})
        print(('PASS ' if ok else 'FAIL ') + case['suite'] + ':' + str(case['line']))
    (args.work_dir / 'fonts-golden-results.json').write_text(json.dumps(details, indent=2), 'utf-8')
    result_path.write_text(json.dumps(totals), 'utf-8')
    print(json.dumps(totals))
    if totals != {'passed':32, 'failed':0}:
        raise RuntimeError('Pinned upstream shaping golden comparison failed')


if __name__ == '__main__':
    main()
