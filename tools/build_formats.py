"""Build pinned VBA and text-format archives with a separate POLE support object and native parser tests."""
import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from build_dependencies import prepare,sha
from build_kernel import prepare_kernel_sources,response_file
from build_x2t_dependencies import kernel_current
from build_windows import discover_vs,msvc_environment,execute
from verify_sources import ROOT,safe_relative,verify


def verify_format_inputs():
    lock=json.loads((ROOT/'formats.inputs.lock.json').read_text('utf-8'))
    upstream=json.loads((ROOT/'upstream.lock.json').read_text('utf-8'))
    if lock['repository']!='https://github.com/ONLYOFFICE/core' or lock['revision']!=next(r['revision'] for r in upstream if r['repository']=='core'):
        raise ValueError('Format identity differs from pinned core')
    frozen={r['file']:r for r in json.loads((ROOT/'source-manifest.json').read_text('utf-8'))['modified_files'] if r['repository']=='core'}
    for rows in (lock['files'],lock['boost']['files']):
        seen=set()
        for row in rows:
            safe_relative(row['file'])
            if row['file'].casefold() in seen or not re.fullmatch('[a-f0-9]{64}',row['sha256']):raise ValueError('Duplicate format input or invalid hash')
            seen.add(row['file'].casefold())
    if lock['boost']['version']!='1.72.0':raise ValueError('Unexpected format Boost identity')
    for row in lock['files']:
        if row['origin'] not in ('pinned-upstream','community-overlay','frozen-overlay'):raise ValueError('Unknown format input origin')
        if row['origin']!='pinned-upstream':
            safe_relative(row['modified_source'])
            if sha(ROOT/row['modified_source'])!=row['sha256']:raise ValueError('Format modified source hash mismatch')
        if row['origin']=='community-overlay':
            safe_relative(row['patch'])
            if sha(ROOT/row['patch'])!=row['patch_sha256']:raise ValueError('Format patch hash mismatch')
        if row['origin']=='frozen-overlay':
            original=frozen.get(row['file'])
            if original is None or row['modified_source']!='sources/core/'+row['file'] or any(row[k]!=original[k] for k in ('sha256','base_sha256')):
                raise ValueError('Format frozen overlay differs from original 96-file identity')
    indexed={r['file'] for r in lock['files']}
    if set(lock['profiles'])!={'VbaFormatLib','TxtXmlFormatLib','PoleSupport'}:raise ValueError('Unexpected format build profiles')
    for name,count in [('VbaFormatLib',4),('TxtXmlFormatLib',7),('PoleSupport',2)]:
        profile=lock['profiles'][name];units=profile['sources'];safe_relative(profile['project'])
        if len(units)!=count or len({Path(p).stem.casefold() for p in units})!=count:raise ValueError('Unexpected format units or object name collision')
        if not set(units+[profile['project']]).issubset(indexed):raise ValueError('Unpinned format compile unit or project')
        for directory in profile['include_directories']:safe_relative(directory)
    return lock


def prepare_formats(work,lock,archive_cache=None,source_cache=None):
    roots=prepare(work,archive_cache)
    if not kernel_current(work):raise ValueError('Build and test kernel with ICU/UnicodeConverter in this workspace first')
    selected={**lock,'files':[r for r in lock['files'] if r['origin']!='frozen-overlay']}
    core=prepare_kernel_sources(selected,work,source_cache)
    for row in lock['files']:
        if row['origin']=='frozen-overlay':
            target=core/row['file']
            if not target.resolve().is_relative_to(core.resolve()):raise ValueError('Frozen format source escapes workspace')
            if target.exists() and sha(target) not in (row['sha256'],row['base_sha256']):raise ValueError('Unknown frozen format source modification; preserved')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/row['modified_source']).read_bytes())
    for row in lock['boost']['files']:
        if sha(roots['boost']/row['file'])!=row['sha256']:raise ValueError('Unknown format Boost modification; preserved')
    return core,roots['boost']


def audit_compiler_inputs(work,core,boost,lock,env):
    core=core.resolve();boost=boost.resolve()
    index={r['file'].casefold():r['sha256'] for r in lock['files']};bi={r['file'].casefold():r['sha256'] for r in lock['boost']['files']}
    sources=set();included=set()
    for path in (work/'format-build').glob('*/dependencies/*.json'):
        data=json.loads(path.read_text('utf-8-sig'))['Data'];sources.add(Path(data['Source']).resolve().relative_to(core).as_posix().casefold());included.update(data.get('Includes',[]))
    if sources!={s.casefold() for p in lock['profiles'].values() for s in p['sources']}:raise ValueError('Format compiler reports do not cover all units')
    toolchain=[Path(env[key]).resolve() for key in ('VCTOOLSINSTALLDIR','WINDOWSSDKDIR') if env.get(key)]
    if not toolchain:raise ValueError('Missing compiler and SDK header roots')
    inputs=[];external=[]
    for name in sorted(included):
        path=Path(name).resolve()
        if path.is_relative_to(core):relative=path.relative_to(core).as_posix();expected=index.get(relative.casefold());origin='core'
        elif path.is_relative_to(boost):relative=path.relative_to(boost).as_posix();expected=bi.get(relative.casefold());origin='boost'
        else:
            if not any(path.is_relative_to(p) for p in toolchain):raise ValueError('Unreviewed external format header: '+str(path))
            external.append(str(path));continue
        if expected is None or sha(path)!=expected:raise ValueError('Unpinned or changed format compiler input: '+relative)
        inputs.append({'origin':origin,'file':relative,'sha256':expected})
    result={'compile_units':len(sources),'source_manifest_sha256':sha(ROOT/'formats.inputs.lock.json'),'locked_header_reads':len(inputs),'external_toolchain_headers':len(external),'inputs':inputs,'toolchain_headers':external}
    (work/'format-compiler-inputs.json').write_text(json.dumps(result,indent=2),'utf-8');return result


def compile_formats(work,core,boost,lock,vs_root=None):
    env=msvc_environment(discover_vs(vs_root,version_range='[17.0,18.0)'),work);env['VSLANG']='1033'
    compiler=shutil.which('cl.exe',path=env['PATH']);librarian=shutil.which('lib.exe',path=env['PATH'])
    folder=work/'format-build';folder.mkdir(exist_ok=True);(work/'lib').mkdir(exist_ok=True);log=work/'format-build.log'
    report=work/'format-build-report.json'
    if report.exists():report.unlink()
    for name,profile in lock['profiles'].items():
        objects=folder/name;objects.mkdir(exist_ok=True);deps=objects/'dependencies';deps.mkdir(exist_ok=True)
        flags=['/nologo','/c','/O2','/MD','/EHsc','/std:c++17','/MP4','/bigobj','/utf-8','/w','/DNOMINMAX','/DBOOST_ALL_NO_LIB',
               '/D_CRT_SECURE_NO_WARNINGS','/DKERNEL_USE_DYNAMIC_LIBRARY','/DUNICODECONVERTER_USE_DYNAMIC_LIBRARY',
               '/I'+str(core),'/I'+str(boost),'/Fo'+str(objects)+os.sep]
        flags+=['/D'+d for d in profile['defines']]+['/I'+str(core/d) for d in profile['include_directories']]
        rsp=folder/(name+'-compile.rsp');response_file(rsp,flags+[core/p for p in profile['sources']])
        execute([compiler,'/sourceDependencies',str(deps)+os.sep,'@'+str(rsp)],folder,env,log)
        rsp=folder/(name+'-library.rsp');response_file(rsp,['/NOLOGO','/MACHINE:X64','/OUT:'+str(work/'lib'/(name+'.lib')),*[objects/(Path(p).stem+'.obj') for p in profile['sources']]])
        execute([librarian,'@'+str(rsp)],folder,env,log)
    audit_compiler_inputs(work,core,boost,lock,env)
    return env,compiler


def test_formats(work,core,boost,lock,env,compiler):
    folder=work/'format-build';source=ROOT/'tests/native/formats_test.cpp';exe=work/'bin/formats-test.exe';log=work/'format-build.log'
    execute([compiler,'/nologo','/std:c++17','/O2','/MD','/EHsc','/utf-8','/DNOMINMAX','/DUNICODE','/D_UNICODE','/DBOOST_ALL_NO_LIB',
             '/DKERNEL_USE_DYNAMIC_LIBRARY','/DUNICODECONVERTER_USE_DYNAMIC_LIBRARY','/I'+str(core),'/I'+str(boost),str(source),
             '/Fo'+str(folder/'native-test.obj'),'/Fe'+str(exe),'/link',str(work/'lib/VbaFormatLib.lib'),str(work/'lib/TxtXmlFormatLib.lib'),
             str(work/'lib/PoleSupport.lib'),str(work/'bin/kernel.lib'),str(work/'bin/UnicodeConverter.lib'),'ole32.lib','advapi32.lib'],folder,env,log)
    execute([sys.executable,str(ROOT/'tests/run_format_tests.py'),'--exe',str(exe),'--work-dir',str(work)],folder,env,log)
    result=json.loads((work/'format-test-result.json').read_text('utf-8'))
    if result!={'passed':36,'failed':0}:raise RuntimeError('Format native tests did not fully pass')
    report={'core_revision':lock['revision'],'compile_units':{n:len(p['sources']) for n,p in lock['profiles'].items()},
            'core_input_files':len(lock['files']),'source_manifest_sha256':sha(ROOT/'formats.inputs.lock.json'),
            'native_test_source_sha256':sha(source),'test_driver_sha256':sha(ROOT/'tests/run_format_tests.py'),'native_tests':result,
            'artifacts':{n+'.lib':{'sha256':sha(work/'lib'/(n+'.lib'))} for n in lock['profiles']},
            'kernel_dll_sha256':sha(work/'bin/kernel.dll'),'compiler_locked_header_reads':json.loads((work/'format-compiler-inputs.json').read_text('utf-8'))['locked_header_reads'],
            'compiler':compiler,'runtime':'MSVC x64 /MD','old_office_baseline_used':False,'macros_executed':False,
            'test_executable_sha256':sha(exe),'full_txt_docx_conversion_linked':False,'full_vba_xml_export_linked':False,
            'x2t_converter_built':False,'full_office_built':False,'application_gui_tested':False}
    (work/'format-build-report.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('verify','build'))
    for name in ('work-dir','archive-cache','source-cache','vs-root'):parser.add_argument('--'+name,type=Path)
    a=parser.parse_args();lock=verify_format_inputs()
    if a.command=='verify':print(json.dumps({'ok':True,'compile_units':13,'source_inputs':len(lock['files'])}));return
    if os.name!='nt' or not a.work_dir:parser.error('Windows and explicit --work-dir are required')
    work=a.work_dir.resolve()
    if work==ROOT or work in ROOT.parents or ROOT in work.parents:raise ValueError('Select a workspace outside this repository')
    marker=work/'.qingliang-dependency-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():raise ValueError('Unknown nonempty format workspace; preserved')
    work.mkdir(parents=True,exist_ok=True);marker.write_text('One stable dependency and format workspace.\n','utf-8')
    fd=os.open(work/'.build.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,str(os.getpid()).encode('ascii'));verify();core,boost=prepare_formats(work,lock,a.archive_cache,a.source_cache)
        env,compiler=compile_formats(work,core,boost,lock,a.vs_root);test_formats(work,core,boost,lock,env,compiler)
    finally:os.close(fd);(work/'.build.lock').unlink()


if __name__=='__main__':main()
