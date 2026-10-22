"""Build the complete pinned Windows graphics project with freshly built dependencies and test rendering."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from build_dependencies import acquire_archive, prepare, sha
from build_fonts import extract_selected, prepare_fonts, verify_font_inputs
from build_heif import prepare_heif, verify_heif_inputs
from build_kernel import prepare_kernel_sources, response_file, dependencies_current
from build_x2t_dependencies import kernel_current
from build_windows import discover_vs, msvc_environment, execute
from verify_sources import ROOT, safe_relative, verify


def verify_graphics_inputs():
    lock=json.loads((ROOT/'graphics.inputs.lock.json').read_text('utf-8'))
    upstream=json.loads((ROOT/'upstream.lock.json').read_text('utf-8'))
    if lock['repository']!='https://github.com/ONLYOFFICE/core' or lock['revision']!=next(r['revision'] for r in upstream if r['repository']=='core'):
        raise ValueError('Graphics identity differs from pinned core')
    for field,name in [('font_manifest_sha256','fonts.inputs.lock.json'),('heif_manifest_sha256','heif.inputs.lock.json'),('kernel_manifest_sha256','kernel.inputs.lock.json')]:
        if lock[field]!=sha(ROOT/name):raise ValueError('Graphics prerequisite manifest changed')
    frozen={r['file']:r for r in json.loads((ROOT/'source-manifest.json').read_text('utf-8'))['modified_files'] if r['repository']=='core'}
    indexed={};seen_core=set()
    for row in lock['files']:
        safe_relative(row['file'])
        if row['file'].casefold() in seen_core or not re.fullmatch('[a-f0-9]{64}',row['sha256']):raise ValueError('Duplicate graphics input or invalid hash')
        seen_core.add(row['file'].casefold())
        if row['origin'] not in ('pinned-upstream','community-overlay','frozen-overlay'):raise ValueError('Unknown graphics input origin')
        if row['origin'] in ('community-overlay','frozen-overlay'):
            safe_relative(row['modified_source'])
            if sha(ROOT/row['modified_source'])!=row['sha256']:raise ValueError('Graphics modified source hash mismatch')
        if row['origin']=='community-overlay':
            safe_relative(row['patch'])
            if sha(ROOT/row['patch'])!=row['patch_sha256']:raise ValueError('Graphics prerequisite patch hash mismatch')
        if row['origin']=='frozen-overlay':
            original=frozen.get(row['file'])
            if original is None or row['modified_source']!='sources/core/'+row['file'] or any(row[k]!=original[k] for k in ('sha256','base_sha256')):
                raise ValueError('Graphics frozen overlay differs from original 96-file identity')
        indexed[row['file']]=row['sha256']
    if set(lock['archives'])!={'katana','hyphen'}:raise ValueError('Expected both parser and hyphen source archives')
    for name,row in lock['archives'].items():
        repository='https://github.com/'+('jasenhuang/katana-parser' if name=='katana' else 'hunspell/hyphen')
        if row['repository']!=repository or row['url']!=repository.replace('github.com/','codeload.github.com/')+'/zip/'+row['revision']:
            raise ValueError('Unexpected graphics support archive origin')
        if not re.fullmatch('[a-f0-9]{40}',row['revision']) or not re.fullmatch('[a-f0-9]{64}',row['sha256']):raise ValueError('Invalid graphics archive identity')
        safe_relative(row['archive']);seen=set()
        for entry in row['files']:
            safe_relative(entry['file'])
            if entry['file'].casefold() in seen or not re.fullmatch('[a-f0-9]{64}',entry['sha256']):raise ValueError('Duplicate graphics archive input or invalid hash')
            seen.add(entry['file'].casefold())
    for group in [lock['archives'],verify_font_inputs()['archives']]:
        for row in group.values():
            safe_relative(row['destination'])
            for entry in row['files']:
                safe_relative(entry['file'])
                indexed[row['destination']+'/'+entry['file']]=entry['sha256']
    for row in lock['archives'].values():
        for overlay in row.get('patches',[]):
            for field in ('file','patch','modified_source'):safe_relative(overlay[field])
            base=next((entry['sha256'] for entry in row['files'] if entry['file']==overlay['file']),None)
            if base!=overlay['base_sha256']:raise ValueError('Graphics parser adaptation base differs from archive input')
            if sha(ROOT/overlay['patch'])!=overlay['patch_sha256'] or sha(ROOT/overlay['modified_source'])!=overlay['result_sha256']:
                raise ValueError('Graphics parser adaptation hash mismatch')
    if len(lock['sources'])!=515 or len(set(lock['sources']))!=515:raise ValueError('Expected all 515 graphics compile units')
    if not set(lock['sources']).issubset(indexed):raise ValueError('Unpinned graphics compile unit')
    for directory in lock['include_directories']:safe_relative(directory)
    for row in lock['boost']['files']:
        safe_relative(row['file'])
        if not re.fullmatch('[a-f0-9]{64}',row['sha256']):raise ValueError('Invalid graphics Boost hash')
    for row in lock['generated_headers']:
        safe_relative(row['file'])
        if not re.fullmatch('[a-f0-9]{64}',row['sha256']):raise ValueError('Invalid generated graphics header hash')
    return lock


def prepare_graphics(work,lock,archive_cache=None,source_cache=None):
    roots=prepare(work,archive_cache)
    if not dependencies_current(work) or not kernel_current(work):
        raise ValueError('Build and test ICU/UnicodeConverter and kernel in this workspace first')
    prepare_fonts(work,verify_font_inputs(),archive_cache,source_cache)
    prepare_heif(work,verify_heif_inputs(),archive_cache,source_cache)
    selected={**lock,'files':[row for row in lock['files'] if row['origin']!='frozen-overlay']}
    core=prepare_kernel_sources(selected,work,source_cache)
    for row in lock['files']:
        if row['origin']=='frozen-overlay':
            target=core/row['file']
            if not target.resolve().is_relative_to(core.resolve()):raise ValueError('Frozen graphics source escapes workspace')
            if target.exists() and sha(target) not in (row['sha256'],row['base_sha256']):raise ValueError('Unknown frozen graphics source modification; preserved')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ROOT/row['modified_source']).read_bytes())
    for name,row in lock['archives'].items():
        archive=acquire_archive(row,work,archive_cache)
        destination=extract_selected(archive,row,core)
        for overlay in row.get('patches',[]):
            target=destination/overlay['file']
            if sha(target)==overlay['base_sha256']:
                cmd=['git','-c','core.autocrlf=false','-C',str(core),'apply','--whitespace=nowarn']
                subprocess.run(cmd+['--check',str(ROOT/overlay['patch'])],check=True)
                subprocess.run(cmd+[str(ROOT/overlay['patch'])],check=True)
            if sha(target)!=overlay['result_sha256']:raise ValueError('Prepared graphics parser adaptation differs')
        print(name+': fixed graphics support source prepared',flush=True)
    for row in lock['boost']['files']:
        if sha(roots['boost']/row['file'])!=row['sha256']:raise ValueError('Unknown graphics Boost modification; preserved')
    for row in lock['generated_headers']:
        if sha(core/row['file'])!=row['sha256']:raise ValueError('Unknown generated graphics header modification; preserved')
    report_path=work/'heif-build-report.json'
    if not report_path.is_file():raise ValueError('Build and test HEIF prerequisites first')
    report=json.loads(report_path.read_text('utf-8'))
    heif=verify_heif_inputs()
    if report['source_manifest_sha256']!=sha(ROOT/'heif.inputs.lock.json') or report['native_tests']!={'passed':16,'failed':0}:
        raise ValueError('HEIF prerequisite evidence is stale')
    for name,row in heif['archives'].items():
        path=core/row['destination']/'build/win_64/release'/heif['profiles'][name]['library']
        if sha(path)!=report['artifacts'][name]['sha256']:raise ValueError('HEIF library differs from tested artifact')
    return core,roots['boost']


def audit_compiler_inputs(work,core,boost,lock,env):
    indexed={r['file'].casefold():r['sha256'] for r in lock['files']}
    for manifest in (lock,verify_font_inputs(),verify_heif_inputs()):
        for archive in manifest['archives'].values():
            for row in archive['files']:indexed[(archive['destination']+'/'+row['file']).casefold()]=row['sha256']
            for row in archive.get('patches',[]):indexed[(archive['destination']+'/'+row['file']).casefold()]=row['result_sha256']
    for row in lock['generated_headers']:indexed[row['file'].casefold()]=row['sha256']
    boost_index={r['file'].casefold():r['sha256'] for r in lock['boost']['files']}
    source_paths=set();included=set();reports=list((work/'graphics-build').glob('group-*/dependencies/*.json'))
    for path in reports:
        data=json.loads(path.read_text('utf-8-sig'))['Data']
        source_paths.add(Path(data['Source']).resolve().relative_to(core.resolve()).as_posix().casefold())
        included.update(data.get('Includes',[]))
    if source_paths!={s.casefold() for s in lock['sources']}:raise ValueError('Compiler dependency reports do not cover the complete graphics project')
    core_root=core.resolve();boost_root=boost.resolve();audited=[];external=[]
    toolchain_roots=[Path(env[key]).resolve() for key in ('VCTOOLSINSTALLDIR','WINDOWSSDKDIR') if env.get(key)]
    if not toolchain_roots:raise ValueError('No verified MSVC or Windows SDK header roots')
    for name in sorted(included):
        path=Path(name).resolve()
        if path.is_relative_to(core_root):
            relative=path.relative_to(core_root).as_posix();expected=indexed.get(relative.casefold())
            if expected is None or sha(path)!=expected:raise ValueError('Unpinned or changed graphics compiler input: '+relative)
            audited.append({'origin':'core-or-locked-support','file':relative,'sha256':expected})
        elif path.is_relative_to(boost_root):
            relative=path.relative_to(boost_root).as_posix();expected=boost_index.get(relative.casefold())
            if expected is None or sha(path)!=expected:raise ValueError('Unpinned or changed Boost compiler input: '+relative)
            audited.append({'origin':'boost','file':relative,'sha256':expected})
        else:
            if not any(path.is_relative_to(root) for root in toolchain_roots):
                raise ValueError('Graphics read an external header outside MSVC and Windows SDK: '+str(path))
            external.append(str(path))
    report={'compile_units':len(source_paths),'locked_header_reads':len(audited),'external_toolchain_headers':len(external),
            'source_manifest_sha256':sha(ROOT/'graphics.inputs.lock.json'),'inputs':audited,'toolchain_headers':external}
    (work/'graphics-compiler-inputs.json').write_text(json.dumps(report,indent=2),'utf-8')
    return report


def source_groups(sources):
    groups=[]
    for source in sources:
        stem=Path(source).stem.casefold()
        for group in groups:
            if stem not in {Path(s).stem.casefold() for s in group}:group.append(source);break
        else:groups.append([source])
    return groups


def compile_graphics(work,core,boost,lock,vs_root=None):
    env=msvc_environment(discover_vs(vs_root,version_range='[17.0,18.0)'),work)
    env['VSLANG']='1033'
    compiler=shutil.which('cl.exe',path=env['PATH']);linker=shutil.which('link.exe',path=env['PATH'])
    folder=work/'graphics-build';folder.mkdir(exist_ok=True)
    log=work/'graphics-build.log'
    report=work/'graphics-build-report.json'
    if report.exists():report.unlink()
    objects=[]
    for index,group in enumerate(source_groups(lock['sources'])):
        group_dir=folder/f'group-{index}';group_dir.mkdir(exist_ok=True)
        dependencies=group_dir/'dependencies';dependencies.mkdir(exist_ok=True)
        flags=['/nologo','/c','/O2','/MD','/EHsc','/std:c++17','/MP4','/bigobj','/utf-8','/w',
               '/Zc:wchar_t','/Zc:strictStrings-','/DBOOST_ALL_NO_LIB','/D_CRT_SECURE_NO_WARNINGS',
               '/I'+str(core),'/I'+str(boost),'/Fo'+str(group_dir)+os.sep]
        flags+=['/D'+value for value in lock['defines']]
        flags+=['/I'+str(core/value) for value in lock['include_directories']]
        rsp=folder/f'compile-{index}.rsp'
        response_file(rsp,flags+[core/source for source in group])
        execute([compiler,'/sourceDependencies',str(dependencies)+os.sep,'@'+str(rsp)],folder,env,log)
        objects += [group_dir/(Path(source).stem+'.obj') for source in group]
    if not all(path.is_file() for path in objects):raise RuntimeError('Missing graphics object output')
    heif=verify_heif_inputs()
    libraries=[work/'bin/kernel.lib',work/'bin/UnicodeConverter.lib',work/'lib/boost_regex.lib',work/'lib/boost_date_time.lib']
    libraries += [core/heif['archives'][name]['destination']/'build/win_64/release'/heif['profiles'][name]['library'] for name in ('libheif','x265','libde265')]
    link_rsp=folder/'link.rsp'
    response_file(link_rsp,['/NOLOGO','/DLL','/MACHINE:X64','/OPT:REF','/OPT:ICF','/INCREMENTAL:NO',
                            '/OUT:'+str(work/'bin/graphics.dll'),'/IMPLIB:'+str(work/'bin/graphics.lib'),
                            *objects,*libraries,*lock['system_libraries']])
    execute([linker,'@'+str(link_rsp)],folder,env,log)
    audit_compiler_inputs(work,core,boost,lock,env)
    return env,compiler


def audit_runtime_imports(work,env):
    dumpbin=shutil.which('dumpbin.exe',path=env['PATH'])
    output=subprocess.check_output([dumpbin,'/NOLOGO','/DEPENDENTS',str(work/'bin/graphics.dll')],env=env,text=True,encoding='utf-8')
    imports={line.strip().casefold() for line in output.splitlines() if re.fullmatch(r'\s*[\w.-]+\.dll\s*',line,re.I)}
    allowed={'kernel.dll','unicodeconverter.dll','kernel32.dll','user32.dll','gdi32.dll','advapi32.dll','ole32.dll',
             'oleaut32.dll','shell32.dll','shlwapi.dll','usp10.dll','ws2_32.dll','bcrypt.dll','crypt32.dll','comdlg32.dll',
             'msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll','ucrtbase.dll'}
    if not {'kernel.dll','unicodeconverter.dll'}.issubset(imports) or any(name not in allowed and not name.startswith('api-ms-win-') for name in imports):
        raise ValueError('Unexpected graphics runtime import: '+','.join(sorted(imports)))
    report={'graphics_dll_sha256':sha(work/'bin/graphics.dll'),'imports':sorted(imports),
            'kernel_dll_sha256':sha(work/'bin/kernel.dll'),'unicodeconverter_dll_sha256':sha(work/'bin/UnicodeConverter.dll')}
    (work/'graphics-runtime-imports.json').write_text(json.dumps(report,indent=2),'utf-8')
    return report


def test_graphics(work,core,boost,lock,env,compiler):
    folder=work/'graphics-build';log=work/'graphics-build.log'
    source=ROOT/'tests/native/graphics_test.cpp';executable=work/'bin/graphics-test.exe'
    execute([compiler,'/nologo','/std:c++17','/O2','/MD','/EHsc','/utf-8','/DNOMINMAX','/DUNICODE','/D_UNICODE','/DBOOST_ALL_NO_LIB',
             '/I'+str(core),'/I'+str(boost),str(source),'/Fo'+str(folder/'native-test.obj'),'/Fe'+str(executable),
             '/link',str(work/'bin/graphics.lib'),str(work/'bin/kernel.lib'),'ole32.lib','gdi32.lib','user32.lib'],folder,env,log)
    execute([sys.executable,str(ROOT/'tests/run_graphics_tests.py'),'--exe',str(executable),'--work-dir',str(work)],folder,env,log)
    result=json.loads((work/'graphics-test-result.json').read_text('utf-8'))
    if result!={'passed':21,'failed':0}:raise RuntimeError('Graphics rendering tests did not fully pass')
    report={'core_revision':lock['revision'],'compile_units':len(lock['sources']),'source_inputs':len(lock['files']),
            'source_manifest_sha256':sha(ROOT/'graphics.inputs.lock.json'),'native_tests':result,
            'native_test_source_sha256':sha(source),'test_driver_sha256':sha(ROOT/'tests/run_graphics_tests.py'),
            'graphics_dll_sha256':sha(work/'bin/graphics.dll'),'graphics_import_library_sha256':sha(work/'bin/graphics.lib'),
            'kernel_dll_sha256':sha(work/'bin/kernel.dll'),'font_manifest_sha256':lock['font_manifest_sha256'],'heif_manifest_sha256':lock['heif_manifest_sha256'],
            'runtime':'MSVC x64 /MD','compiler':compiler,'full_graphics_built':True,'qt_runtime_used':False,
            'old_office_baseline_used':False,'x2t_converter_built':False,'full_office_built':False,'application_gui_tested':False}
    audit=json.loads((work/'graphics-compiler-inputs.json').read_text('utf-8'))
    report['compiler_header_reads_verified']=audit['locked_header_reads']
    report['runtime_imports']=audit_runtime_imports(work,env)['imports']
    (work/'graphics-build-report.json').write_text(json.dumps(report,indent=2),'utf-8')
    print(json.dumps(report),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('verify','build'))
    parser.add_argument('--work-dir',type=Path);parser.add_argument('--archive-cache',type=Path)
    parser.add_argument('--source-cache',type=Path);parser.add_argument('--vs-root',type=Path)
    args=parser.parse_args();lock=verify_graphics_inputs()
    if args.command=='verify':
        print(json.dumps({'ok':True,'compile_units':len(lock['sources']),'source_inputs':len(lock['files'])}));return
    if os.name!='nt' or not args.work_dir:parser.error('Windows and an explicit --work-dir are required')
    work=args.work_dir.resolve()
    if work==ROOT or work in ROOT.parents or ROOT in work.parents:raise ValueError('Select a workspace outside this repository')
    marker=work/'.qingliang-dependency-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():raise ValueError('Unknown nonempty graphics workspace; preserved')
    work.mkdir(parents=True,exist_ok=True);marker.write_text('One stable graphics and dependency build workspace.\n','utf-8')
    lockfile=work/'.build.lock';fd=os.open(lockfile,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,str(os.getpid()).encode('ascii'));verify()
        core,boost=prepare_graphics(work,lock,args.archive_cache,args.source_cache)
        env,compiler=compile_graphics(work,core,boost,lock,args.vs_root)
        test_graphics(work,core,boost,lock,env,compiler)
    finally:os.close(fd);lockfile.unlink()


if __name__=='__main__':main()
