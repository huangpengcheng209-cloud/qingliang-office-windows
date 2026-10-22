"""Portable MSVC entry for native save tests and a read-only full-engine dependency audit."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from verify_sources import ROOT, verify

HEADER = Path('sources/desktop-sdk/ChromiumBasedEditors/lib/src/windows_save_transaction.h')
FIXTURE = Path('tests/native/save_transaction_test.cpp')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def discover_vs(explicit=None):
    if explicit is not None:
        root = explicit.resolve()
    else:
        candidates = [Path(os.environ.get('ProgramFiles(x86)', '')) / 'Microsoft Visual Studio/Installer/vswhere.exe']
        found = shutil.which('vswhere')
        if found:
            candidates.insert(0, Path(found))
        program = next((p for p in candidates if p.is_file()), None)
        if program is None:
            raise ValueError('MSVC not found: install Visual Studio C++ Build Tools or pass --vs-root')
        value = subprocess.check_output([str(program), '-latest', '-products', '*', '-requires',
                                         'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                                         '-property', 'installationPath'], text=True).strip()
        if not value:
            raise ValueError('No Visual Studio installation with x64 C++ tools')
        root = Path(value).resolve()
    script = root / 'VC/Auxiliary/Build/vcvarsall.bat'
    if not script.is_file():
        raise ValueError('Selected Visual Studio root has no vcvarsall.bat')
    return script

def msvc_environment(vcvars, work):
    if any(char in str(vcvars) for char in '\r\n"%'):
        raise ValueError('Unsupported characters in compiler setup path')
    script = work / 'msvc-environment.cmd'
    script.write_text('@echo off\ncall "' + str(vcvars) + '" x64 >nul\nif errorlevel 1 exit /b 1\nset\n', 'utf-8')
    result = subprocess.run(['cmd.exe', '/d', '/c', str(script)], check=True, capture_output=True)
    env = dict(os.environ)
    selected = {'PATH', 'LIB', 'INCLUDE', 'LIBPATH', 'VCTOOLSINSTALLDIR', 'WINDOWSSDKDIR', 'WINDOWSSDKVERSION'}
    for line in result.stdout.decode('utf-8', 'replace').splitlines():
        if '=' in line and not line.startswith('='):
            key, value = line.split('=', 1)
            if key.upper() in selected:
                # Windows environment variables are case-insensitive.
                for old in list(env):
                    if old.upper() == key.upper():
                        del env[old]
                env[key.upper()] = value
    for key in ('TEMP', 'TMP'):
        env[key] = str(work / 'temp')
    (work / 'temp').mkdir(exist_ok=True)
    return env

def owned_work_directory(work):
    work = work.resolve()
    if work == ROOT or work in ROOT.parents or ROOT in work.parents:
        raise ValueError('Build work directory must be outside the published repository')
    marker = work / '.qingliang-native-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():
        raise ValueError('Refusing to reuse an unrecognized nonempty build directory')
    work.mkdir(parents=True, exist_ok=True)
    marker.write_text('Rebuildable save-transaction native test outputs only.\n', 'utf-8')
    return work

def execute(command, work, env, log):
    with log.open('ab') as stream:
        stream.write(('\nCOMMAND ' + repr(command) + '\n').encode('utf-8'))
        offset = stream.tell()
        result = subprocess.run(command, cwd=work, env=env, stdout=stream, stderr=stream)
    if result.returncode:
        with log.open('rb') as stream:
            stream.seek(offset)
            lines = stream.read().decode('utf-8', 'replace').splitlines()
        print('\n'.join(lines[-12:]), file=sys.stderr)
        raise RuntimeError(f'Native build/test failed; see {log}')

def build_save_transaction(work, vs_root=None):
    if os.name != 'nt':
        raise ValueError('Native save-transaction compilation requires Windows')
    verify()
    vcvars = discover_vs(vs_root)
    work = owned_work_directory(work)
    # One build at a time in the stable workspace. Never remove another process's lock.
    lock = work / '.build.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        env = msvc_environment(vcvars, work)
        compiler = shutil.which('cl.exe', path=env['PATH'])
        if compiler is None:
            raise ValueError('cl.exe unavailable after MSVC setup')
        exe = work / 'save-transaction-test.exe'
        obj = work / 'save-transaction-test.obj'
        log = work / 'native-build.log'
        command = [compiler, '/nologo', '/std:c++17', '/EHsc', '/W4', '/O2', '/utf-8', '/MD',
                   '/DUNICODE', '/D_UNICODE', '/DNOMINMAX', '/I' + str((ROOT / HEADER).parent),
                   str(ROOT / FIXTURE), '/Fo' + str(obj), '/Fe' + str(exe),
                   '/link', 'ole32.lib', 'advapi32.lib']
        execute(command, work, env, log)
        fixtures = work / 'fixtures'
        fixtures.mkdir(exist_ok=True)
        if any(fixtures.iterdir()):
            raise ValueError('Native fixtures contain prior evidence; inspect before reusing this directory')
        result_path = work / 'native-test-result.json'
        if result_path.exists():
            result_path.unlink()
        execute([str(exe), str(fixtures), str(result_path)], work, env, log)
        result = json.loads(result_path.read_text('utf-8'))
        if result.get('failed') != 0 or result.get('passed') != 14:
            raise RuntimeError('Native test summary does not match the expected suite')
        report = {'component': 'windows_save_transaction.h', 'header_sha256': sha(ROOT / HEADER),
                  'test_sha256': sha(ROOT / FIXTURE), 'executable_sha256': sha(exe),
                  'native_tests': result, 'compiler_setup': str(vcvars), 'compiled': True,
                  'full_office_built': False, 'application_gui_tested': False,
                  'office_support_runtime_required': False, 'msvc_runtime': '/MD'}
        (work / 'native-build-report.json').write_text(json.dumps(report, indent=2), 'utf-8')
        print(json.dumps({'compiled': True, 'native_tests': result, 'full_office_built': False,
                          'report': str(work / 'native-build-report.json')}))
        return report
    finally:
        os.close(fd)
        lock.unlink()

def engine_audit(source_root=None, qt_root=None, source_archive=None):
    if (source_root is None) == (source_archive is None):
        raise ValueError('Select exactly one prepared source root or frozen source archive')
    if source_root is not None:
        source_root = source_root.resolve()
    archive_names = None
    if source_archive is not None:
        with zipfile.ZipFile(source_archive) as archive:
            archive_names = set(archive.namelist())
    checks = []
    for name, relative, purpose in [
        ('core kernel project', 'core/Common/kernel.pro', 'kernel qmake project'),
        ('desktop shell project', 'desktop-apps/win-linux/ASCDocumentEditor.pro', 'desktop application qmake project'),
        ('zlib source', 'core/OfficeUtils/src/zlib-1.2.11/zlib.h', 'kernel compression sources'),
        ('libxml2 source', 'core/DesktopEditor/xml/libxml2/include/libxml/parser.h', 'kernel XML sources'),
        ('Boost headers', 'core/Common/3dParty/boost/boost_1_72_0/boost/version.hpp', 'converter/native include dependency'),
        ('ICU headers', 'core/Common/3dParty/icu/win_64/icu/source/common/unicode/utypes.h', 'UnicodeConverter include dependency'),
        ('UnicodeConverter import library', 'core/build/lib/win_64/UnicodeConverter.lib', 'kernel link dependency'),
        ('CEF 150 build selection', 'desktop-sdk/ChromiumBasedEditors/lib/cef_pri_150/cef_sources.pri', 'generated CEF source group'),
    ]:
        available = ('upstream/' + relative in archive_names) if archive_names is not None else (source_root / relative).is_file()
        checks.append({'name': name, 'available': available, 'relative_path': relative, 'purpose': purpose})
    if qt_root:
        checks.append({'name': 'Qt qmake', 'available': (qt_root / 'bin/qmake.exe').is_file(),
                       'relative_path': str(qt_root / 'bin/qmake.exe'), 'purpose': 'Qt 5.15.2 MSVC x64 qmake'})
    blockers = [
        'Complete desktop build orchestration is not yet portable; historical scripts require original baseline inputs.',
        'Unmodified runtime support DLLs have not all been replaced by a source-rebuilt dependency pipeline.',
        'VLC x64 downstream patch and static dependency/configuration correspondence remains incomplete.',
    ]
    return {'scope': 'read-only selected full-engine input audit', 'input_kind': 'archive' if source_archive is not None else 'directory', 'checks': checks,
            'missing_file_inputs': sum(not x['available'] for x in checks), 'remaining_blockers': blockers,
            'full_app_build_ready': False, 'build_performed': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    native = commands.add_parser('save-transaction', help='Compile the published Win32 save component and run 14 real file-operation cases.')
    native.add_argument('--work-dir', required=True, type=Path)
    native.add_argument('--vs-root', type=Path)
    audit = commands.add_parser('engine-audit', help='Inspect known full-engine inputs without compiling or writing to the source tree.')
    inputs = audit.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--source-root', type=Path, help='Prepared DesktopEditors source root')
    inputs.add_argument('--source-archive', type=Path, help='Frozen snapshot with upstream/<module>/ archive paths; read without extracting')
    audit.add_argument('--qt-root', type=Path)
    audit.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.command == 'save-transaction':
        build_save_transaction(args.work_dir, args.vs_root)
    else:
        result = engine_audit(args.source_root, args.qt_root, args.source_archive)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, indent=2), 'utf-8')
        print(json.dumps(result))

if __name__ == '__main__':
    main()
