"""Build pinned DOCX and OOXML support code and test actual text/document conversion."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from build_dependencies import prepare,sha,acquire_archive
from build_fonts import extract_selected
from build_graphics import source_groups
from build_kernel import prepare_kernel_sources,response_file
from build_x2t_dependencies import kernel_current
from build_windows import discover_vs,msvc_environment,execute
from verify_sources import ROOT,safe_relative,verify


def verify_docx_inputs():
    lock=json.loads((ROOT/'docx.inputs.lock.json').read_text('utf-8'))
    upstream=json.loads((ROOT/'upstream.lock.json').read_text('utf-8'))
    if lock['repository']!='https://github.com/ONLYOFFICE/core' or lock['revision']!=next(r['revision'] for r in upstream if r['repository']=='core'):
        raise ValueError('Format identity differs from pinned core')
    archive=lock['core_archive']
    if archive['repository']!=lock['repository'] or archive['revision']!=lock['revision'] or archive['url']!='https://codeload.github.com/ONLYOFFICE/core/zip/'+lock['revision'] or archive['root']!='core-'+lock['revision']:
        raise ValueError('Unexpected DOCX core archive origin')
    safe_relative(archive['archive'])
    if not re.fullmatch('[a-f0-9]{64}',archive['sha256']):raise ValueError('Invalid DOCX archive hash')
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
            if 'frozen_parent_sha256' in row:
                parent=frozen.get(row['file'])
                if parent is None or parent['sha256']!=row['frozen_parent_sha256'] or parent['base_sha256']!=row['base_sha256']:raise ValueError('Derived DOCX frozen parent identity differs')
        if row['origin']=='frozen-overlay':
            original=frozen.get(row['file'])
            if original is None or row['modified_source']!='sources/core/'+row['file'] or any(row[k]!=original[k] for k in ('sha256','base_sha256')):
                raise ValueError('Format frozen overlay differs from original 96-file identity')
    indexed={r['file'] for r in lock['files']}
    if set(lock['support_archives'])!={'katana','gumbo','md4c'}:raise ValueError('Unexpected HTML support archives')
    for archive in lock['support_archives'].values():
        for key in ('destination','archive','root'):safe_relative(archive[key])
        if not re.fullmatch('[a-f0-9]{40}',archive['revision']) or archive['url']!=archive['repository'].replace('https://github.com/','https://codeload.github.com/')+'/zip/'+archive['revision']:raise ValueError('Unpinned HTML archive')
        if not re.fullmatch('[a-f0-9]{64}',archive['sha256']):raise ValueError('Invalid HTML archive hash')
        seen=set()
        for row in archive['files']:
            safe_relative(row['file'])
            if row['file'].casefold() in seen or not re.fullmatch('[a-f0-9]{64}',row['sha256']):raise ValueError('Duplicate or invalid HTML input')
            seen.add(row['file'].casefold());indexed.add(archive['destination']+'/'+row['file'])
        for row in archive.get('patches',[]):
            for key in ('file','modified_source','patch'):safe_relative(row[key])
            base=next((p for p in archive['files'] if p['file']==row['file']),None)
            if base is None or base['sha256']!=row['base_sha256']:raise ValueError('HTML overlay base differs')
            if sha(ROOT/row['modified_source'])!=row['result_sha256'] or sha(ROOT/row['patch'])!=row['patch_sha256']:raise ValueError('HTML overlay identity mismatch')
    counts={'DocxFormatLib':8,'PPTXFormatLib':60,'XlsbFormatLib':1,'XlsFormatLib':42,'BinDocument':43,'DocFormatLib':8,'OoxmlSupport':5,'RtfFormatLib':3,'HtmlFile2':40,'TxtDocxBridge':7}
    if set(lock['profiles'])!=set(counts):raise ValueError('Unexpected format build profiles')
    for name,count in counts.items():
        profile=lock['profiles'][name];units=profile['sources'];safe_relative(profile['project'])
        if len(units)!=count or len(set(units))!=count:raise ValueError('Unexpected format units')
        if not set(units+[profile['project']]).issubset(indexed):raise ValueError('Unpinned format compile unit or project')
        for directory in profile['include_directories']:safe_relative(directory)
    return lock


def prepare_docx(work,lock,archive_cache=None,source_cache=None):
    roots=prepare(work,archive_cache)
    if not kernel_current(work):raise ValueError('Build and test kernel with ICU/UnicodeConverter in this workspace first')
    # The DOCX overlay is separate from the published frozen file. Only this exact
    # known intermediate may be upgraded; arbitrary local changes still stop.
    for row in lock['files']:
        if 'frozen_parent_sha256' not in row:continue
        target=work/'sources/core'/row['file']
        if not target.resolve().is_relative_to((work/'sources/core').resolve()):raise ValueError('Derived source escapes workspace')
        if target.is_file() and sha(target)==row['frozen_parent_sha256']:
            target.write_bytes((ROOT/row['modified_source']).read_bytes())
    if source_cache is None:
        archive=acquire_archive(lock['core_archive'],work,archive_cache)
        row={**lock['core_archive'],'destination':'','files':[{'file':r['file'],'sha256':r.get('base_sha256',r['sha256'])} for r in lock['files']],
             'patches':[{'file':r['file'],'result_sha256':r['sha256']} for r in lock['files'] if r['origin']!='pinned-upstream']}
        extract_selected(archive,row,work/'sources/core')
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
    for archive in lock['support_archives'].values():
        destination=extract_selected(acquire_archive(archive,work,archive_cache),archive,core)
        for row in archive.get('patches',[]):
            target=destination/row['file']
            if sha(target)==row['base_sha256']:
                cmd=['git','-c','core.autocrlf=false','-C',str(core),'apply','--whitespace=nowarn']
                subprocess.run(cmd+['--check',str(ROOT/row['patch'])],check=True)
                subprocess.run(cmd+[str(ROOT/row['patch'])],check=True)
            if sha(target)!=row['result_sha256']:raise ValueError('HTML support overlay mismatch')
    return core,roots['boost']


def audit_compiler_inputs(work,core,boost,lock,env):
    core=core.resolve();boost=boost.resolve()
    index={r['file'].casefold():r['sha256'] for r in lock['files']};bi={r['file'].casefold():r['sha256'] for r in lock['boost']['files']}
    for archive in lock['support_archives'].values():
        for row in archive['files']:index[(archive['destination']+'/'+row['file']).casefold()]=row['sha256']
        for row in archive.get('patches',[]):index[(archive['destination']+'/'+row['file']).casefold()]=row['result_sha256']
    sources=set();included=set()
    for path in (work/'docx-build').glob('**/dependencies/*.json'):
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
    result={'compile_units':len(sources),'source_manifest_sha256':sha(ROOT/'docx.inputs.lock.json'),'locked_header_reads':len(inputs),'external_toolchain_headers':len(external),'inputs':inputs,'toolchain_headers':external}
    (work/'docx-compiler-inputs.json').write_text(json.dumps(result,indent=2),'utf-8');return result


def compile_docx(work,core,boost,lock,vs_root=None,only_profiles=None,only_sources=None):
    env=msvc_environment(discover_vs(vs_root,version_range='[17.0,18.0)'),work);env['VSLANG']='1033'
    compiler=shutil.which('cl.exe',path=env['PATH']);librarian=shutil.which('lib.exe',path=env['PATH'])
    folder=work/'docx-build';folder.mkdir(exist_ok=True);(work/'lib').mkdir(exist_ok=True);log=work/'docx-build.log'
    report=work/'docx-build-report.json'
    if report.exists():report.unlink()
    for name,profile in lock['profiles'].items():
        if only_profiles is not None and name not in only_profiles:continue
        objects=folder/name;objects.mkdir(exist_ok=True)
        flags=['/nologo','/c','/O2','/MD','/EHsc','/std:c++17','/MP2','/Gy','/Gw','/bigobj','/utf-8','/w','/DNOMINMAX','/DBOOST_ALL_NO_LIB',
               '/D_CRT_SECURE_NO_WARNINGS','/DKERNEL_USE_DYNAMIC_LIBRARY','/DUNICODECONVERTER_USE_DYNAMIC_LIBRARY',
               '/I'+str(core),'/I'+str(boost),'/I'+str(core/Path(profile['project']).parent)]
        flags+=['/D'+d for d in profile['defines']]+['/I'+str(core/d) for d in profile['include_directories']]
        object_paths=[]
        for number,group in enumerate(source_groups(profile['sources'])):
            group_dir=objects/f'group-{number}' if name=='HtmlFile2' else objects
            group_dir.mkdir(exist_ok=True);deps=group_dir/'dependencies';deps.mkdir(exist_ok=True)
            units=group if only_sources is None else [p for p in group if p in only_sources.get(name,group)]
            if units:
                rsp=folder/(name+f'-compile-{number}.rsp');response_file(rsp,flags+['/Fo'+str(group_dir)+os.sep]+[core/p for p in units])
                execute([compiler,'/sourceDependencies',str(deps)+os.sep,'@'+str(rsp)],folder,env,log)
            object_paths.extend(group_dir/(Path(p).stem+'.obj') for p in group)
        rsp=folder/(name+'-library.rsp')
        if profile.get('kind')=='shared':
            linker=shutil.which('link.exe',path=env['PATH'])
            libraries=[work/'bin'/(p+'.lib') for p in ('kernel','UnicodeConverter','graphics','kernel_network')]
            libraries += [work/'lib'/(p+'.lib') for p in ('boost_regex','boost_date_time')]
            response_file(rsp,['/NOLOGO','/DLL','/MACHINE:X64','/OPT:REF','/OPT:ICF','/INCREMENTAL:NO','/OUT:'+str(work/'bin'/(name+'.dll')),'/IMPLIB:'+str(work/'lib'/(name+'.lib')),*object_paths,*libraries,'ole32.lib','oleaut32.lib','advapi32.lib','gdi32.lib','user32.lib','shell32.lib','ws2_32.lib'])
            execute([linker,'@'+str(rsp)],folder,env,log)
        else:
            response_file(rsp,['/NOLOGO','/MACHINE:X64','/OUT:'+str(work/'lib'/(name+'.lib')),*object_paths])
            execute([librarian,'@'+str(rsp)],folder,env,log)
    audit_compiler_inputs(work,core,boost,lock,env)
    return env,compiler


def test_docx(work,core,boost,lock,env,compiler):
    folder=work/'docx-build';source=ROOT/'tools/native/text_docx_preview.cpp';exe=work/'bin/text-docx-preview.exe';log=work/'docx-build.log'
    libraries=[work/'lib'/(n+'.lib') for n in (*lock['profiles'],'VbaFormatLib','CryptoPPLib','boost_regex','boost_date_time','CompoundFileLib')]
    libraries += [work/'bin'/(n+'.lib') for n in ('kernel','UnicodeConverter','graphics','kernel_network')]
    args=['/nologo','/std:c++17','/O2','/Gy','/Gw','/MD','/EHsc','/utf-8','/DNOMINMAX','/DUNICODE','/D_UNICODE','/DBOOST_ALL_NO_LIB',
          '/DKERNEL_USE_DYNAMIC_LIBRARY','/DUNICODECONVERTER_USE_DYNAMIC_LIBRARY','/DGRAPHICS_USE_DYNAMIC_LIBRARY','/I'+str(core),'/I'+str(boost),source,
          '/Fo'+str(folder/'preview.obj'),'/Fe'+str(exe),'/link','/OPT:REF','/OPT:ICF',*libraries,'ole32.lib','oleaut32.lib','advapi32.lib','gdi32.lib','user32.lib','shell32.lib','ws2_32.lib']
    rsp=folder/'preview-link.rsp';response_file(rsp,args);execute([compiler,'@'+str(rsp)],folder,env,log)
    execute([sys.executable,str(ROOT/'tests/run_docx_tests.py'),'--exe',str(exe),'--work-dir',str(work)],folder,env,log)
    result=json.loads((work/'docx-test-result.json').read_text('utf-8'))
    if result!={'passed':23,'failed':0}:raise RuntimeError('DOCX conversion tests did not fully pass')
    report={'core_revision':lock['revision'],'compile_units':{n:len(p['sources']) for n,p in lock['profiles'].items()},
            'core_input_files':len(lock['files']),'source_manifest_sha256':sha(ROOT/'docx.inputs.lock.json'),
            'native_test_source_sha256':sha(source),'test_driver_sha256':sha(ROOT/'tests/run_docx_tests.py'),'native_tests':result,
            'artifacts':{n+'.lib':{'sha256':sha(work/'lib'/(n+'.lib'))} for n in lock['profiles']},
            'kernel_dll_sha256':sha(work/'bin/kernel.dll'),'compiler_locked_header_reads':json.loads((work/'docx-compiler-inputs.json').read_text('utf-8'))['locked_header_reads'],
            'compiler':compiler,'runtime':'MSVC x64 /MD','old_office_baseline_used':False,'macros_executed':False,
            'test_executable_sha256':sha(exe),'full_txt_docx_conversion_linked':True,'full_vba_xml_export_linked':False,
            'wrapper_sha256':sha(ROOT/'tools/text_docx_preview.py'),'html_dll_sha256':sha(work/'bin/HtmlFile2.dll'),
            'x2t_converter_built':False,'full_office_built':False,'application_gui_tested':False}
    (work/'docx-build-report.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('verify','build'))
    for name in ('work-dir','archive-cache','source-cache','vs-root'):parser.add_argument('--'+name,type=Path)
    a=parser.parse_args();lock=verify_docx_inputs()
    if a.command=='verify':print(json.dumps({'ok':True,'compile_units':sum(len(p['sources']) for p in lock['profiles'].values()),'source_inputs':len(lock['files'])}));return
    if os.name!='nt' or not a.work_dir:parser.error('Windows and explicit --work-dir are required')
    work=a.work_dir.resolve()
    if work==ROOT or work in ROOT.parents or ROOT in work.parents:raise ValueError('Select a workspace outside this repository')
    marker=work/'.qingliang-dependency-build'
    if work.exists() and any(work.iterdir()) and not marker.is_file():raise ValueError('Unknown nonempty format workspace; preserved')
    work.mkdir(parents=True,exist_ok=True);marker.write_text('One stable dependency and format workspace.\n','utf-8')
    fd=os.open(work/'.build.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,str(os.getpid()).encode('ascii'));verify();core,boost=prepare_docx(work,lock,a.archive_cache,a.source_cache)
        env,compiler=compile_docx(work,core,boost,lock,a.vs_root);test_docx(work,core,boost,lock,env,compiler)
    finally:os.close(fd);(work/'.build.lock').unlink()


if __name__=='__main__':main()
