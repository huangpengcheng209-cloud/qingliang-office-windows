"""Build the full native desktop host with source-built support and a fixed official CEF SDK.

Qt, Chromium source rebuilding, Office editing and installation acceptance are separate.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import zipfile
from pathlib import Path
from build_converter import compiler_index, verify_converter_inputs
from build_dependencies import acquire_archive, sha
from build_desktop import prepare_desktop, build_hunspell, verify_desktop_inputs
from build_graphics import source_groups
from build_kernel import response_file
from build_windows import discover_vs, execute, msvc_environment
from verify_sources import ROOT, safe_relative, verify

MODULES = {'desktop-sdk': 'sources/desktop-sdk', 'cef': 'sources/cef', 'core': 'sources/core',
           'boost': 'sources/boost/boost_1_72_0', 'icu': 'sources/icu/icu'}
SYSTEM_LIBS = {'d3d11','d3dcompiler','glu32','gdi32','wininet','dnsapi','version','msimg32','ws2_32',
               'usp10','psapi','shlwapi','winmm','ole32','oleaut32','uuid','advapi32','shell32',
               'comdlg32','odbc32','odbccp32','delayimp','credui','netapi32','comctl32','rpcrt4',
               'gdiplus','urlmon','opengl32','crypt32','imm32'}
BOOST_NAMES = {'libboost_system-vc142-mt-x64-1_72':'boost_system',
               'libboost_filesystem-vc142-mt-x64-1_72':'boost_filesystem',
               'libboost_regex-vc142-mt-x64-1_72':'boost_regex'}


def source_path(work, value):
    module, relative = value.removeprefix('@').split('/', 1)
    if not value.startswith('@') or module not in MODULES:
        raise ValueError('Unknown host input module')
    safe_relative(relative)
    root = (work / MODULES[module]).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError('Host input escapes selected source root')
    return target


def verify_host_inputs():
    verify()
    lock = json.loads((ROOT / 'host.inputs.lock.json').read_text('utf-8'))
    converter = verify_converter_inputs()
    desktop = verify_desktop_inputs()
    upstream = {r['repository']:r for r in json.loads((ROOT / 'upstream.lock.json').read_text('utf-8'))}
    if sha(ROOT / 'converter.inputs.lock.json') != lock['converter_input_lock_sha256'] or sha(ROOT / 'desktop.inputs.lock.json') != lock['desktop_input_lock_sha256']:
        raise ValueError('Host prerequisite source locks differ')
    sdk = lock['desktop_sdk']
    if sdk['revision'] != upstream['desktop-sdk']['revision'] or sdk['url'] != 'https://codeload.github.com/ONLYOFFICE/desktop-sdk/zip/' + sdk['revision'] or sdk['root'] != 'desktop-sdk-' + sdk['revision']:
        raise ValueError('Host SDK origin differs from fixed upstream')
    if lock['core_archive']['revision'] != upstream['core']['revision']:
        raise ValueError('Host core origin differs')
    materials = json.loads((ROOT / 'desktop.prerequisites.json').read_text('utf-8'))['cef']
    if lock['cef_revision'] != materials['cef_revision'] or lock['cef_source']['root'] != 'cef-' + lock['cef_revision']:
        raise ValueError('Host CEF revision differs')
    for key, url in [('cef_sdk',materials['sdk_url']),('cef_source',materials['wrapper_source_url'])]:
        row = lock[key]
        original = next(r for r in materials['archives'] if r['archive'] == row['archive'])
        if row['sha256'] != original['sha256'] or row['url'] != url:
            raise ValueError('Host CEF archive differs')
    frozen = {r['file']:r for r in json.loads((ROOT / 'source-manifest.json').read_text('utf-8'))['modified_files'] if r['repository'] == 'desktop-sdk'}
    for key in ('desktop_sdk','cef_sdk','cef_source'):
        row = lock[key]
        for field in ('archive','root'):
            safe_relative(row[field])
        if not re.fullmatch('[a-f0-9]{64}',row['sha256']):
            raise ValueError('Invalid host archive hash')
        seen = set()
        for item in row['files']:
            safe_relative(item['file'])
            for field in ('modified_source','patch'):
                if field in item:safe_relative(item[field])
            if item['file'].casefold() in seen or not re.fullmatch('[a-f0-9]{64}', item['sha256']):
                raise ValueError('Duplicate or invalid host source input')
            seen.add(item['file'].casefold())
            if item.get('origin') == 'frozen-overlay':
                if item['sha256'] != frozen[item['file']]['sha256'] or sha(ROOT / item['modified_source']) != item['sha256']:
                    raise ValueError('Host frozen source differs')
            if 'patch' in item:
                for field in ('patch','modified_source'):
                    safe_relative(item[field])
                if sha(ROOT / item['patch']) != item['patch_sha256'] or sha(ROOT / item['modified_source']) != item['sha256']:
                    raise ValueError('Host patch or modified source differs')
                if key == 'desktop_sdk' and item['frozen_parent_sha256'] != frozen[item['file']]['sha256']:
                    raise ValueError('Host community fix parent differs')
    p = lock['profile']
    if len(p['sources']) != 280 or len(set(p['sources'])) != 280:
        raise ValueError('Host must retain all 280 native units')
    for value in p['sources'] + p['include_directories'] + [p['force_include']]:
        source_path(Path('/host-input-check'), value)
    required = {'FEATURE_ENABLE_PROTECT','FEATURE_ENABLE_SIGNATURE','ONLYOFFICE_CEF_150','CEF_API_VERSION=15000','_HAS_DEPRECATED_ALLOCATOR_MEMBERS=1'}
    if not required.issubset(p['defines']) or any(not re.fullmatch('[A-Za-z_][A-Za-z0-9_.,=]*',v) for v in p['defines']):
        raise ValueError('Host features or fixed CEF build profile differ')
    for value in p['libraries']:
        if value != '@cef/Release/libcef.lib' and not re.fullmatch('-l[A-Za-z0-9_.-]+',value):
            raise ValueError('Unreviewed host library argument')
    seen = set()
    for item in lock['compiler_inputs']:
        source_path(Path('/host-input-check'),item['file'])
        if item['file'].casefold() in seen or not re.fullmatch('[a-f0-9]{64}',item['sha256']):
            raise ValueError('Duplicate or invalid host compiler input')
        seen.add(item['file'].casefold())
    if not set(p['sources']).issubset({r['file'] for r in lock['compiler_inputs']}):
        raise ValueError('Host compilation source omitted from audit lock')
    providers = {'@desktop-sdk/'+r['file']:r['sha256'] for r in sdk['files']}
    providers.update({'@cef/'+r['file']:r['sha256'] for a in (lock['cef_sdk'],lock['cef_source']) for r in a['files']})
    providers.update({'@core/'+name:digest for name,digest in compiler_index(converter).items()})
    hunspell = desktop['hunspell']
    providers.update({'@core/'+hunspell['destination']+'/'+r['file']:r['sha256'] for r in hunspell['files']})
    providers.update({'@core/'+hunspell['destination']+'/'+r['file']:r['result_sha256'] for r in hunspell['patches']})
    providers.update({'@core/'+r['file']:r['sha256'] for r in lock['additional_core_files']})
    providers.update({'@boost/'+r['file']:r['sha256'] for r in converter['boost']['files']+lock['boost_files']})
    providers.update({'@icu/'+r['file']:r['sha256'] for r in lock['icu_files']})
    providers = {k.casefold():v for k,v in providers.items()}
    for item in lock['compiler_inputs']:
        if providers.get(item['file'].casefold()) != item['sha256']:
            raise ValueError('Host compiler lock differs from source provider: '+item['file'])
    return lock


def materialize(row, destination, archive, frozen=None):
    """Check every selected archive member and destination before replacing owned source bytes."""
    indexed = {r['file']:r for r in row['files']}
    pending = []
    source = zipfile.ZipFile(archive) if archive.suffix == '.zip' else tarfile.open(archive,'r:bz2')
    try:
        members = {}
        for member in source.infolist() if isinstance(source,zipfile.ZipFile) else source.getmembers():
            name = member.filename if isinstance(source,zipfile.ZipFile) else member.name
            safe_relative(name)
            prefix = row['root'] + '/'
            if not name.startswith(prefix):
                if name.rstrip('/') == row['root']:continue
                raise ValueError('Unexpected host archive root')
            relative = name[len(prefix):]
            if relative not in indexed:continue
            linked = stat.S_ISLNK(member.external_attr >> 16) if isinstance(source,zipfile.ZipFile) else not member.isfile()
            if relative.casefold() in members or linked:
                raise ValueError('Duplicate or linked host archive input')
            members[relative.casefold()] = member
        for name, item in indexed.items():
            target = (destination / name).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError('Host destination escapes source directory')
            base = item.get('base_sha256',item['sha256'])
            member = members.get(name.casefold())
            if base is not None:
                if member is None:raise ValueError('Missing locked host archive member')
                data = source.read(member) if isinstance(source,zipfile.ZipFile) else source.extractfile(member).read()
                if hashlib.sha256(data).hexdigest() != base:
                    raise ValueError('Host archive member hash differs')
            else:
                data = b''
            parent = None
            if frozen and name in frozen:
                parent = (ROOT / 'sources/desktop-sdk' / name).read_bytes()
                if hashlib.sha256(parent).hexdigest() != frozen[name]['sha256']:
                    raise ValueError('Host frozen overlay changed')
                data = parent
            allowed = {base,item['sha256'],item.get('frozen_parent_sha256')}
            if target.exists() and sha(target) not in allowed:
                raise ValueError('Unknown existing host source edit preserved: '+name)
            pending.append((target,data,item))
        for target,data,item in pending:
            if target.exists() and sha(target) == item['sha256']:continue
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
            if 'patch' in item:
                if not (destination / '.git').exists():
                    subprocess.run(['git','init','--quiet',str(destination)],check=True)
                command = ['git','-c','core.autocrlf=false','-C',str(destination),'apply','--whitespace=nowarn']
                subprocess.run(command + ['--check',str(ROOT / item['patch'])],check=True)
                subprocess.run(command + [str(ROOT / item['patch'])],check=True)
            if sha(target) != item['sha256']:
                raise ValueError('Prepared host overlay result differs')
    finally:
        source.close()


def prepare_host(lock, work, archive_cache=None):
    frozen = {r['file']:r for r in json.loads((ROOT / 'source-manifest.json').read_text('utf-8'))['modified_files'] if r['repository'] == 'desktop-sdk'}
    for key,module in [('desktop_sdk','desktop-sdk'),('cef_sdk','cef'),('cef_source','cef')]:
        row = lock[key]
        archive = acquire_archive(row,work,archive_cache)
        materialize(row,work / MODULES[module],archive,frozen if key == 'desktop_sdk' else None)
    extra = dict(lock['core_archive'])
    extra['files'] = lock['additional_core_files']
    materialize(extra,work / MODULES['core'],acquire_archive(extra,work,archive_cache))
    for item in lock['boost_files']:
        if sha(work / MODULES['boost'] / item['file']) != item['sha256']:
            raise ValueError('Host Boost source differs')
    for item in lock['icu_files']:
        if sha(work / MODULES['icu'] / item['file']) != item['sha256']:
            raise ValueError('Host ICU header differs')


def build_boost(lock, work, env):
    folder = work / 'host-boost-build'
    folder.mkdir(exist_ok=True)
    compiler = shutil.which('cl.exe',path=env['PATH'])
    for name, files in lock['boost_profiles'].items():
        obj = folder / name
        deps = obj / 'dependencies'
        deps.mkdir(parents=True,exist_ok=True)
        flags = ['/nologo','/c','/O2','/MD','/EHsc','/std:c++17','/MP4','/bigobj','/utf-8','/w',
                 '/DNOMINMAX','/DBOOST_ALL_NO_LIB','/D_CRT_SECURE_NO_WARNINGS','/DBOOST_FILESYSTEM_STATIC_LINK',
                 '/DBOOST_SYSTEM_STATIC_LINK','/I'+str(work / MODULES['boost']),'/Fo'+str(obj)+os.sep]
        rsp = folder / (name+'-compile.rsp')
        response_file(rsp,flags+[work / MODULES['boost'] / p for p in files])
        execute([compiler,'/sourceDependencies',str(deps)+os.sep,'@'+str(rsp)],folder,env,work/'host-boost-build.log')
        response_file(rsp,['/NOLOGO','/MACHINE:X64','/OUT:'+str(work/'lib'/(name+'.lib'))]+[obj/(Path(p).stem+'.obj') for p in files])
        execute([shutil.which('lib.exe',path=env['PATH']),'@'+str(rsp)],folder,env,work/'host-boost-build.log')


def compile_host(lock, work, env):
    p = lock['profile']
    folder = work / 'host-build'
    folder.mkdir(exist_ok=True)
    flags = ['/nologo','/c','/TP','/O2','/MD','/EHsc','/std:c++20','/bigobj','/MP4','/utf-8',
             '/Zc:__cplusplus','/Zc:strictStrings-','/FS','/w','/D_CRT_SECURE_NO_WARNINGS']
    flags += ['/D'+v for v in p['defines']]+['/I'+str(source_path(work,v)) for v in p['include_directories']]
    flags += ['/FI'+str(source_path(work,p['force_include']))]
    objects = []
    for number,group in enumerate(source_groups(p['sources'])):
        obj = folder / ('group-'+str(number))
        deps = obj / 'dependencies'
        deps.mkdir(parents=True,exist_ok=True)
        # Remove only dependency reports for this exact compile group; a failed rebuild cannot pass using stale reports.
        for name in group:
            (deps / (Path(name).name+'.json')).unlink(missing_ok=True)
        rsp = folder / ('compile-group-'+str(number)+'.rsp')
        response_file(rsp,flags+['/Fo'+str(obj)+os.sep]+[source_path(work,v) for v in group])
        execute([shutil.which('cl.exe',path=env['PATH']),'/sourceDependencies',str(deps)+os.sep,'@'+str(rsp)],folder,env,work/'host-build.log')
        objects += [str(obj/(Path(v).stem+'.obj')) for v in group]
        print(json.dumps({'host_compiled_group':number,'units':len(group)}),flush=True)
    return objects


def audit_host(lock, work, env):
    expected = {source_path(work,r['file']):r['sha256'] for r in lock['compiler_inputs']}
    actual, used, external = set(), set(), set()
    for path in (work/'host-build').glob('group-*/dependencies/*.json'):
        data = json.loads(path.read_text('utf-8-sig'))['Data']
        actual.add(Path(data['Source']).resolve())
        used.update(Path(p).resolve() for p in [data['Source'],*data['Includes']])
    if actual != {source_path(work,v) for v in lock['profile']['sources']}:
        raise ValueError('Host compiler records omit or add a translation unit')
    toolchain = [Path(env[k]).resolve() for k in ('VCTOOLSINSTALLDIR','WINDOWSSDKDIR')]
    for path in used:
        if path in expected:
            if sha(path) != expected[path]:raise ValueError('Host compiler read modified source: '+str(path))
        elif any(path.is_relative_to(root) for root in toolchain):external.add(path)
        else:raise ValueError('Unpinned host compiler input: '+str(path))
    result = {'compile_units':len(actual),'locked_inputs_read':len(used-external),'toolchain_headers':len(external)}
    (work/'host-compiler-inputs.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
    return result


def link_host(lock, work, env, objects):
    libraries = []
    for value in lock['profile']['libraries']:
        if value.startswith('@'):
            libraries.append(str(source_path(work,value)))
            continue
        name = BOOST_NAMES.get(value[2:],value[2:])
        candidates = [work/'lib'/(name+'.lib'),work/'bin'/(name+'.lib')]
        if name == 'icuuc':candidates.append(work/'sources/icu/icu/lib64/icuuc.lib')
        found = next((p for p in candidates if p.is_file()),None)
        if found:libraries.append(str(found))
        elif name.lower() in SYSTEM_LIBS:libraries.append(name+'.lib')
        else:raise ValueError('Missing source-built host support library: '+name)
    libraries += ['user32.lib','kernel32.lib']
    rsp = work/'host-build/link.rsp'
    response_file(rsp,['/NOLOGO','/DLL','/MACHINE:X64','/OPT:REF','/OPT:ICF','/INCREMENTAL:NO',
                      '/OUT:'+str(work/'bin/ascdocumentscore.dll'),'/IMPLIB:'+str(work/'lib/ascdocumentscore.lib'),*objects,*libraries])
    execute([shutil.which('link.exe',path=env['PATH']),'@'+str(rsp)],work/'host-build',env,work/'host-link.log')
    return {str(p):sha(Path(p)) for p in libraries if Path(p).is_file()}


def test_host(work, env):
    folder = work/'host-build'
    binary = work/'bin/desktop-host-test.exe'
    result = work/'host-test-result.json'
    result.unlink(missing_ok=True)
    flags = ['/nologo','/std:c++20','/MD','/EHsc','/O2','/utf-8','/DWIN32','/DUNICODE','/D_UNICODE','/DNOMINMAX',
             '/DONLYOFFICE_CEF_150','/DBOOST_ALL_NO_LIB','/DBOOST_FILESYSTEM_STATIC_LINK','/DBOOST_SYSTEM_STATIC_LINK','/D_CRT_SECURE_NO_WARNINGS',
             '/I'+str(work/'sources/desktop-sdk/ChromiumBasedEditors/lib/include'),'/I'+str(work/MODULES['boost']),
             str(ROOT/'tests/native/desktop_host_test.cpp'),'/Fo'+str(folder/'native-test.obj'),'/Fe'+str(binary),'/link',
             str(work/'lib/ascdocumentscore.lib'),str(work/'lib/boost_filesystem.lib'),str(work/'lib/boost_system.lib'),'advapi32.lib']
    execute([shutil.which('cl.exe',path=env['PATH']),*flags],folder,env,work/'host-native-test.log')
    runtime = dict(env)
    runtime['PATH'] = str(work/'bin')+os.pathsep+str(work/'sources/cef/Release')+os.pathsep+env['PATH']
    fixtures = work/'host-native-fixtures'
    fixtures.mkdir(exist_ok=True)
    execute([str(binary),str(fixtures),str(result)],work/'bin',runtime,work/'host-native-test.log')
    data = json.loads(result.read_text('utf-8'))
    if data['passed'] != 22 or data['failed'] or len(data['cases']) != 22:
        raise ValueError('Native host suite failed')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('verify','build'))
    parser.add_argument('--work-dir',type=Path)
    parser.add_argument('--archive-cache',type=Path)
    parser.add_argument('--vs-root',type=Path)
    args = parser.parse_args()
    lock = verify_host_inputs()
    if args.command == 'verify':
        print(json.dumps({'ok':True,'host_units':280,'boost_units':11,'compiler_inputs':len(lock['compiler_inputs'])}))
        return
    if os.name != 'nt' or not args.work_dir:parser.error('Windows and --work-dir are required')
    work = args.work_dir.resolve()
    if work == ROOT or work in ROOT.parents or ROOT in work.parents or not (work/'.qingliang-dependency-build').is_file():
        raise ValueError('Use the existing marked converter/dependency build directory')
    fd = os.open(work/'.build.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,str(os.getpid()).encode('ascii'))
        (work/'host-build-report.json').unlink(missing_ok=True)
        prior = json.loads((work/'converter-build-report.json').read_text('utf-8'))
        if prior['source_manifest_sha256'] != lock['converter_input_lock_sha256']:
            raise ValueError('Build the current pinned converter and support chain first')
        for name,digest in prior['artifacts'].items():
            if sha(work/'bin'/name) != digest:raise ValueError('Converter support binary changed: '+name)
        spelling = verify_desktop_inputs()
        spelling_source = prepare_desktop(spelling,work,args.archive_cache)
        spelling_report = work/'desktop-build-report.json'
        ready = json.loads(spelling_report.read_text('utf-8')) if spelling_report.exists() else {}
        if ready.get('input_manifest_sha256') != sha(ROOT/'desktop.inputs.lock.json') or not (work/'bin/hunspell.dll').is_file() or ready.get('hunspell_dll_sha256') != sha(work/'bin/hunspell.dll'):
            build_hunspell(spelling,work,spelling_source,args.vs_root)
        prepare_host(lock,work,args.archive_cache)
        env = msvc_environment(discover_vs(args.vs_root,version_range='[17.0,18.0)'),work)
        build_boost(lock,work,env)
        objects = compile_host(lock,work,env)
        audit = audit_host(lock,work,env)
        linked = link_host(lock,work,env,objects)
        tests = test_host(work,env)
        report = {'host_units':280,'boost_units':11,'compiler_input_audit':audit,'native_tests':tests,
                  'input_manifest_sha256':sha(ROOT/'host.inputs.lock.json'),'test_source_sha256':sha(ROOT/'tests/native/desktop_host_test.cpp'),
                  'builder_source_sha256':sha(Path(__file__)),'host_dll_sha256':sha(work/'bin/ascdocumentscore.dll'),
                  'host_import_library_sha256':sha(work/'lib/ascdocumentscore.lib'),'link_inputs':linked,
                  'cef_sdk_prebuilt':True,'old_office_support_libraries_used':False,'cef_browser_initialized':False,
                  'qt_gui_tested':False,'office_edit_save_tested':False,'installer_built':False}
        (work/'host-build-report.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
        print(json.dumps({'host_units':280,'native_tests':{'passed':22,'failed':0},'office_edit_save_tested':False}),flush=True)
    finally:
        os.close(fd)
        (work/'.build.lock').unlink()


if __name__ == '__main__':
    main()
