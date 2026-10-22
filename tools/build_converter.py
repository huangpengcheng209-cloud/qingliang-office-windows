"""Build the complete pinned Windows x64 x2t converter, including V8 and SDK scripts.

This extends the existing dependency/DOCX workspace. It does not build the editor GUI.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from build_dependencies import acquire_archive, sha
from build_docx import prepare_docx
from build_fonts import extract_selected
from build_graphics import source_groups
from build_kernel import response_file
from build_windows import discover_vs, execute, msvc_environment
from verify_sources import ROOT, safe_relative, verify

V8_PATH='Common/3dParty/v8_89/v8'
COUNTS={'x2t':4,'OdfFormatLib':26,'PptFormatLib':1,'Fb2File':13,'EpubFile':5,
        'PdfFile':215,'XpsFile':7,'OFDFile':27,'DjVuFile':57,'DocxRenderer':17,
        'IWorkFile':221,'HWPFile':75,'StarMathConverter':4,'ooxmlsignature':5,'doctrenderer':43,'ConverterOoxml':1}


def checked_rows(rows):
    seen=set()
    for row in rows:
        safe_relative(row['file'])
        if row['file'].casefold() in seen or not re.fullmatch('[a-f0-9]{64}',row['sha256']):
            raise ValueError('Duplicate input or invalid hash')
        seen.add(row['file'].casefold())


def verify_converter_inputs():
    lock=json.loads((ROOT/'converter.inputs.lock.json').read_text('utf-8'))
    upstream={r['repository']:r['revision'] for r in json.loads((ROOT/'upstream.lock.json').read_text('utf-8'))}
    if lock['repository']!='https://github.com/ONLYOFFICE/core' or lock['revision']!=upstream['core']:
        raise ValueError('Converter core differs from main source lock')
    checked_rows(lock['files']);checked_rows(lock['boost']['files'])
    if lock['boost']['version']!='1.72.0':raise ValueError('Unsupported Boost version')
    frozen={r['file']:r for r in json.loads((ROOT/'source-manifest.json').read_text('utf-8'))['modified_files'] if r['repository']=='core'}
    for row in lock['files']:
        if row['origin'] not in {'pinned-upstream','frozen-overlay','community-overlay'}:raise ValueError('Unknown source origin')
        if row['origin']!='pinned-upstream':
            safe_relative(row['modified_source'])
            if sha(ROOT/row['modified_source'])!=row['sha256']:raise ValueError('Modified source differs')
        if row['origin']=='frozen-overlay':
            original=frozen.get(row['file'])
            if original is None or any(row[k]!=original[k] for k in ['sha256','base_sha256']):raise ValueError('Frozen source identity differs')
        if row['origin']=='community-overlay':
            safe_relative(row['patch'])
            if sha(ROOT/row['patch'])!=row['patch_sha256']:raise ValueError('Community patch differs')
    archive=lock['core_archive']
    safe_relative(archive['archive']);safe_relative(archive['root'])
    if archive['revision']!=upstream['core'] or archive['root']!='core-'+upstream['core'] or archive['url']!='https://codeload.github.com/ONLYOFFICE/core/zip/'+upstream['core'] or not re.fullmatch('[a-f0-9]{64}',archive['sha256']):
        raise ValueError('Unpinned core archive')
    indexed={r['file'] for r in lock['files']}
    for name,archive in lock['support_archives'].items():
        for key in ['destination','archive','root']:safe_relative(archive[key])
        if not re.fullmatch('[a-f0-9]{40}',archive['revision']) or archive['url']!=archive['repository'].replace('https://github.com/','https://codeload.github.com/')+'/zip/'+archive['revision']:
            raise ValueError('Unpinned support archive')
        verify_archive_rows(archive);indexed.update(archive['destination']+'/'+r['file'] for r in archive['files'])
    for name,archive in lock['v8_dependencies'].items():
        safe_relative(name)
        if not archive['repository'].startswith('https://chromium.googlesource.com/') or archive['url']!=archive['repository']+'/+archive/'+archive['revision']+'.tar.gz':raise ValueError('Unpinned V8 dependency')
        verify_archive_rows(archive)
    if set(lock['tools'])!={'perl532','python38','gn'}:raise ValueError('Unexpected converter build tools')
    for tool in lock['tools'].values():
        safe_relative(tool['archive']);checked_rows(tool['files'])
        if not re.fullmatch('[a-f0-9]{64}',tool['sha256']):raise ValueError('Invalid converter tool archive hash')
    for row in lock.get('license_supplements',[]):
        safe_relative(row['file'])
        if sha(ROOT/row['file'])!=row['sha256']:raise ValueError('Retained license differs')
    checked_rows(lock['generated_headers'])
    openssl={r['file']:r['sha256'] for r in lock['support_archives']['openssl']['files']}
    for row in lock['generated_headers']:
        if not row['file'].startswith('Common/3dParty/openssl/build/win_64/include/openssl/'):raise ValueError('Unexpected generated header location')
        if row['origin']=='copied-source' and openssl.get(row['source_file'])!=row['sha256']:raise ValueError('Installed OpenSSL source header differs')
        if row['origin']=='generated-config-header' and row.get('template_source') not in openssl:raise ValueError('Unpinned OpenSSL header template')
        if row['origin'] not in {'copied-source','generated-config-header'}:raise ValueError('Unknown generated header origin')
    sdk=lock['sdkjs']
    if sdk['revision']!=upstream['sdkjs'] or sdk['url']!='https://codeload.github.com/ONLYOFFICE/sdkjs/zip/'+upstream['sdkjs']:raise ValueError('Unpinned SDKJS')
    checked_rows(sdk['files'])
    frozen_sdk={r['file']:r['sha256'] for r in json.loads((ROOT/'source-manifest.json').read_text('utf-8'))['modified_files'] if r['repository']=='sdkjs'}
    if {r['file']:r['sha256'] for r in sdk['files'] if r['origin']=='frozen-overlay'}!=frozen_sdk:raise ValueError('SDKJS frozen identity differs')
    font=lock['test_font']
    for row in font['files']:
        safe_relative(row['file']);safe_relative(row['archive']);safe_relative(row['source_file'])
        if row['url']!='https://raw.githubusercontent.com/notofonts/noto-cjk/'+font['revision']+'/'+row['source_file'] or not re.fullmatch('[a-f0-9]{64}',row['sha256']):raise ValueError('Unpinned test font')
    closure=lock['closure_compiler'];safe_relative(closure['archive'])
    if closure['version']!='20240317.0.0' or closure['url']!='https://registry.npmjs.org/google-closure-compiler-java/-/google-closure-compiler-java-20240317.0.0.tgz':raise ValueError('Unpinned SDK compiler')
    indexed.update(row['file'] for row in lock['apple_generated'])
    if set(lock['profiles'])!=set(COUNTS):raise ValueError('Unexpected converter profiles')
    for name,count in COUNTS.items():
        p=lock['profiles'][name];safe_relative(p['project'])
        if len(p['sources'])!=count or len(set(p['sources']))!=count or not set(p['sources']).issubset(indexed):raise ValueError('Unpinned or incomplete converter compile units')
        for directory in p['include_directories']:safe_relative(directory)
        for lib in p['libraries']:
            if lib.startswith('@core/'):safe_relative(lib[6:])
            elif not re.fullmatch(r'-l[A-Za-z0-9_.-]+',lib):raise ValueError('Unexpected converter library')
    return lock


def verify_archive_rows(archive):
    safe_relative(archive['archive'])
    if not re.fullmatch('[a-f0-9]{64}',archive['sha256']):raise ValueError('Invalid archive hash')
    checked_rows(archive['files']);base={r['file']:r['sha256'] for r in archive['files']}
    for row in archive.get('patches',[]):
        for key in ['file','patch','modified_source']:safe_relative(row[key])
        if base.get(row['file'])!=row['base_sha256'] or sha(ROOT/row['patch'])!=row['patch_sha256'] or sha(ROOT/row['modified_source'])!=row['result_sha256']:
            raise ValueError('Archive overlay identity differs')
    for row in archive.get('added_files',[]):
        safe_relative(row['file']);safe_relative(row['source'])
        if row['file'] in base or sha(ROOT/row['source'])!=row['sha256']:raise ValueError('Added source identity differs')


def write_known(target,data,allowed):
    if target.exists() and sha(target) not in allowed:raise ValueError('Unknown existing input preserved: '+str(target))
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists() or target.read_bytes()!=data:target.write_bytes(data)


def apply_archive_overlays(destination,archive,core=None):
    for row in archive.get('patches',[]):
        write_known(destination/row['file'],(ROOT/row['modified_source']).read_bytes(),{row['base_sha256'],row['result_sha256']})
    for row in archive.get('added_files',[]):
        write_known(destination/row['file'],(ROOT/row['source']).read_bytes(),{row['sha256']})
    if core is not None:
        for patch in sorted({r['patch'] for r in archive.get('patches',[])}):
            subprocess.run(['git','-c','core.autocrlf=false','-C',str(core),'apply','--reverse','--check','--whitespace=nowarn',str(ROOT/patch)],check=True)


def extract_tar(archive,row,destination,core=None):
    overlays={p['file']:p['result_sha256'] for p in row.get('patches',[])};pending=[]
    with tarfile.open(archive,'r:gz') as source:
        members={};links={}
        for item in source.getmembers():
            name=item.name.removeprefix('./').rstrip('/')
            if not name:continue
            safe_relative(name)
            if name.casefold() in members:raise ValueError('Duplicate TAR input')
            members[name.casefold()]=item
            if item.issym():links[name]=item.linkname
            elif not item.isfile() and not item.isdir():raise ValueError('Unexpected TAR special file')
        if links!=row.get('skipped_symlinks',{}):raise ValueError('Unexpected TAR links')
        for item in row['files']:
            member=members.get(item['file'].casefold())
            if member is None or not member.isfile():raise ValueError('Missing TAR input')
            data=source.extractfile(member).read();digest=hashlib.sha256(data).hexdigest()
            if digest!=item['sha256']:raise ValueError('TAR input differs')
            target=destination/item['file']
            if not target.resolve().is_relative_to(destination.resolve()):raise ValueError('TAR path escapes source root')
            allowed={digest,overlays.get(item['file'])}
            if target.exists() and sha(target) not in allowed:raise ValueError('Unknown TAR source preserved: '+str(target))
            if not target.exists():pending.append((target,data))
    for target,data in pending:write_known(target,data,{hashlib.sha256(data).hexdigest()})
    apply_archive_overlays(destination,row,core)


def prepare_converter(work,lock,archive_cache=None,source_cache=None):
    # Reuse the existing core/Boost/ICU preparation, then materialize foreign archives.
    basic={**lock,'support_archives':{}}
    core,boost=prepare_docx(work,basic,archive_cache,source_cache)
    for archive in lock['support_archives'].values():
        destination=extract_selected(acquire_archive(archive,work,archive_cache),archive,core)
        apply_archive_overlays(destination,archive,core)
    for name,archive in lock['v8_dependencies'].items():
        extract_tar(acquire_archive(archive,work,archive_cache),archive,core/V8_PATH/name,core)
    for row in lock['apple_generated']:
        source=core/row['source_file'];safe_relative(row['file'])
        if sha(source)!=row['sha256']:raise ValueError('Apple generated token source differs')
        write_known(core/row['file'],source.read_bytes(),{row['sha256']})
    return core,boost


def prepare_tools(work,lock,archive_cache=None):
    for name,row in lock['tools'].items():
        archive=acquire_archive(row,work,archive_cache);destination=work/'tools'/name
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                safe_relative(item.filename)
                if stat.S_ISLNK(item.external_attr>>16):raise ValueError('Tool archive link')
            for entry in row['files']:
                target=destination/entry['file'];data=z.read(entry['file'])
                if hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('Tool input differs')
                # Disabling the embeddable isolation file is deliberate, not an unknown edit.
                if name=='python38' and entry['file']=='python38._pth' and target.with_suffix('._pth.disabled').exists():
                    if sha(target.with_suffix('._pth.disabled'))!=entry['sha256']:raise ValueError('Python isolation backup differs')
                    continue
                write_known(target,data,{entry['sha256']})


def build_openssl(work,core,env):
    perl=work/'tools/perl532/perl/bin/perl.exe';env=env.copy();env['PATH']=str(perl.parent)+os.pathsep+str(work/'tools/perl532/c/bin')+os.pathsep+env['PATH']
    source=core/'Common/3dParty/openssl/openssl';prefix=source.parent/'build/win_64';log=work/'converter-openssl-build.log'
    execute([str(perl),'Configure','VC-WIN64A','no-shared','no-asm','enable-md2','/MD','--prefix='+str(prefix),'--openssldir='+str(prefix)],source,env,log)
    make=shutil.which('nmake.exe',path=env['PATH'])
    for target in ['build_libs','install_dev']:execute([make,'/NOLOGO',target],source,env,log)


def build_v8(work,core,env,vcvars):
    v8=core/V8_PATH;python=work/'tools/python38/python.exe';gn=work/'tools/gn/gn.exe';env=env.copy();vs=Path(vcvars).parents[3]
    pth=python.parent/'python38._pth'
    if pth.exists():pth.rename(pth.with_suffix('._pth.disabled'))
    alias=python.parent/'python3.exe'
    if not alias.exists():os.link(python,alias)
    env.update({'DEPOT_TOOLS_WIN_TOOLCHAIN':'0','GYP_MSVS_OVERRIDE_PATH':str(vs),'GYP_MSVS_VERSION':'2019','vs2019_install':str(vs),'PYTHONHOME':str(python.parent),'PYTHONNOUSERSITE':'1','PYTHONIOENCODING':'utf-8'})
    env['PATH']=str(python.parent)+os.pathsep+str(gn.parent)+os.pathsep+env['PATH']
    options=['is_debug=false','is_clang=false','use_lld=false','use_custom_libcxx=false','target_cpu="x64"','v8_target_cpu="x64"','v8_static_library=true','is_component_build=false','v8_monolithic=true','v8_use_external_startup_data=false','v8_enable_pointer_compression=true','treat_warnings_as_errors=false','windows_sdk_path='+json.dumps(env['WINDOWSSDKDIR'].replace('\\','/').rstrip('/'))]
    execute([str(gn),'gen','out.gn/win_64/release','--script-executable='+str(python),'--args='+' '.join(options)],v8,env,work/'converter-v8-build.log')
    ninja=vs/'Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe'
    execute([str(ninja),'-C','out.gn/win_64/release','-j6','v8_monolith'],v8,env,work/'converter-v8-build.log')


def compile_profiles(work,core,boost,lock,env,profiles=None):
    compiler=shutil.which('cl.exe',path=env['PATH']);folder=work/'converter-build';folder.mkdir(exist_ok=True)
    for name,p in lock['profiles'].items():
        if profiles is not None and name not in profiles:continue
        objects=[]
        for number,group in enumerate(source_groups(p['sources'])):
            obj=folder/name/f'group-{number}';deps=obj/'dependencies';deps.mkdir(parents=True,exist_ok=True)
            flags=['/nologo','/c','/O2','/Gy','/Gw','/MD','/EHsc','/std:c++17','/bigobj','/MP2','/utf-8','/w','/DNOMINMAX','/DBOOST_ALL_NO_LIB','/D_CRT_SECURE_NO_WARNINGS','/Fo'+str(obj)+os.sep,'/I'+str(core),'/I'+str(boost),'/I'+str(core/Path(p['project']).parent)]
            flags+=['/D'+v for v in p['defines']]+['/I'+str(core/v) for v in p['include_directories']]
            rsp=folder/(name+f'-compile-{number}.rsp');response_file(rsp,flags+[core/v for v in group]);execute([compiler,'/sourceDependencies',str(deps)+os.sep,'@'+str(rsp)],folder,env,work/'converter-build.log')
            objects += [str(obj/(Path(v).stem+'.obj')) for v in group]
        (folder/(name+'-objects.json')).write_text(json.dumps(objects,indent=2),'utf-8')
        if p['kind']=='static':
            rsp=folder/(name+'-library.rsp');response_file(rsp,['/NOLOGO','/MACHINE:X64','/OUT:'+str(work/'lib'/(name+'.lib')),*objects]);execute([shutil.which('lib.exe',path=env['PATH']),'@'+str(rsp)],folder,env,work/'converter-build.log')
        print(json.dumps({'converter_profile':name,'compiled_units':len(p['sources'])}),flush=True)


def link_profiles(work,core,lock,env):
    folder=work/'converter-build';link=shutil.which('link.exe',path=env['PATH'])
    order=link_order(lock['profiles'])
    sdk_libs={'gdi32','advapi32','user32','shell32','ole32','crypt32','cryptui','ws2_32','winmm','dbghelp','shlwapi'}
    for name in order:
        p=lock['profiles'][name]
        if p['kind']=='static':continue
        libraries=[];objects=json.loads((folder/(name+'-objects.json')).read_text('utf-8'))
        for arg in p['libraries']:
            if arg.startswith('-l'):
                n=arg[2:]
                if n.startswith('libboost_regex-'):n='boost_regex'
                if n.startswith('libboost_date_time-'):n='boost_date_time'
                if n=='TxtXmlFormatLib':n='TxtDocxBridge'
                candidates=[work/'lib'/(n+'.lib'),work/'bin'/(n+'.lib')]
                if n=='icuuc':candidates.append(work/'sources/icu/icu/lib64/icuuc.lib')
                if n=='v8_monolith':candidates.append(core/V8_PATH/'out.gn/win_64/release/obj/v8_monolith.lib')
                found=next((f for f in candidates if f.is_file()),None)
                if found:libraries.append(str(found))
                elif n.lower() in sdk_libs:libraries.append(n+'.lib')
                else:raise ValueError('Missing converter prerequisite: '+n)
            else:
                f=core/arg.removeprefix('@core/')
                if not f.is_file():raise ValueError('Missing converter prerequisite: '+str(f))
                libraries.append(str(f))
        flags=['/NOLOGO','/MACHINE:X64','/OPT:REF','/OPT:ICF','/INCREMENTAL:NO','/OUT:'+str(work/'bin'/(name+('.exe' if p['kind']=='executable' else '.dll')))]
        if p['kind']!='executable':flags+=['/DLL','/IMPLIB:'+str(work/'lib'/(name+'.lib'))]
        libraries+=['ole32.lib','oleaut32.lib','advapi32.lib','gdi32.lib','user32.lib','shell32.lib','ws2_32.lib','comdlg32.lib','shlwapi.lib','uuid.lib']
        rsp=folder/(name+'-link.rsp');response_file(rsp,flags+objects+libraries);execute([link,'@'+str(rsp)],folder,env,work/'converter-build.log')
        print(json.dumps({'converter_profile':name,'linked':True}),flush=True)


def link_order(profiles):
    order=[];active=set()
    def visit(name):
        if name in active:raise ValueError('Cyclic converter shared-library dependencies')
        if name in order or profiles[name]['kind']=='static':return
        active.add(name)
        for arg in profiles[name]['libraries']:
            if arg.startswith('-l') and arg[2:] in profiles:visit(arg[2:])
        active.remove(name);order.append(name)
    for name in profiles:visit(name)
    return order


def compiler_index(lock):
    index={r['file'].casefold():r['sha256'] for r in lock['files']}
    for archive in lock['support_archives'].values():
        prefix=archive['destination']+'/'
        index.update({(prefix+r['file']).casefold():r['sha256'] for r in archive['files']})
        index.update({(prefix+r['file']).casefold():r['result_sha256'] for r in archive.get('patches',[])})
        index.update({(prefix+r['file']).casefold():r['sha256'] for r in archive.get('added_files',[])})
    for name,archive in lock['v8_dependencies'].items():
        prefix=V8_PATH+'/'+name+'/'
        index.update({(prefix+r['file']).casefold():r['sha256'] for r in archive['files']})
        index.update({(prefix+r['file']).casefold():r['result_sha256'] for r in archive.get('patches',[])})
    index.update({r['file'].casefold():r['sha256'] for r in lock['apple_generated']})
    index.update({r['file'].casefold():r['sha256'] for r in lock.get('generated_headers',[])})
    return index


def audit_compiler_inputs(work,core,boost,lock,env):
    core=core.resolve();boost=boost.resolve();index=compiler_index(lock);bi={r['file'].casefold():r['sha256'] for r in lock['boost']['files']}
    included=set();sources=set()
    for report in (work/'converter-build').glob('**/dependencies/*.json'):
        data=json.loads(report.read_text('utf-8-sig'))['Data'];sources.add(Path(data['Source']).resolve());included.update(data.get('Includes',[]))
    included={Path(p).resolve() for p in included}
    expected={(core/n).resolve() for p in lock['profiles'].values() for n in p['sources']}
    if sources!=expected:raise ValueError('Compiler reports do not cover exactly all converter units')
    roots=[Path(env[k]).resolve() for k in ['VCTOOLSINSTALLDIR','WINDOWSSDKDIR'] if env.get(k)];inputs=[];external=[];unknown=[]
    for path in sorted(sources|included):
        if path.is_relative_to(core):relative=path.relative_to(core).as_posix();digest=index.get(relative.casefold());origin='core'
        elif path.is_relative_to(boost):relative=path.relative_to(boost).as_posix();digest=bi.get(relative.casefold());origin='boost'
        elif any(path.is_relative_to(root) for root in roots):external.append(str(path));continue
        else:raise ValueError('Unreviewed external compiler input: '+str(path))
        if digest is None:unknown.append(relative);continue
        if sha(path)!=digest:raise ValueError('Converter compiler input changed: '+relative)
        inputs.append({'origin':origin,'file':relative,'sha256':digest})
    if unknown:
        (work/'converter-unpinned-compiler-inputs.json').write_text(json.dumps(unknown,indent=2),'utf-8')
        raise ValueError('Unpinned converter compiler inputs: '+str(len(unknown))+'; see converter-unpinned-compiler-inputs.json')
    profiles={name:len(p['sources']) for name,p in lock['profiles'].items()}
    for name,p in lock['profiles'].items():
        actual={Path(json.loads(report.read_text('utf-8-sig'))['Data']['Source']).resolve() for report in (work/'converter-build'/name).glob('**/dependencies/*.json')}
        if actual!={(core/n).resolve() for n in p['sources']}:raise ValueError('Incomplete compiler reports for '+name)
    result={'compile_units':sum(profiles.values()),'unique_compile_sources':len(sources),'profiles':profiles,'locked_source_and_header_reads':len(inputs),'external_toolchain_headers':len(external),'source_manifest_sha256':sha(ROOT/'converter.inputs.lock.json'),'inputs':inputs,'toolchain_headers':external}
    (work/'converter-compiler-inputs.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');return result


def audit_v8_inputs(work,core,lock,env,vcvars):
    root=(core/V8_PATH).resolve();output=root/'out.gn/win_64/release';ninja=Path(vcvars).parents[3]/'Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe'
    dump=work/'converter-v8-header-deps.txt'
    with dump.open('wb') as stream:subprocess.run([str(ninja),'-C',str(output),'-t','deps'],stdout=stream,stderr=subprocess.STDOUT,env=env,check=True)
    raw_paths=set();object_count=0
    for line in dump.read_text('utf-8',errors='strict').splitlines():
        if ': #deps ' in line:object_count+=1
        elif line.startswith('    '):raw_paths.add(line.strip())
    graph=work/'converter-v8-graph-inputs.txt'
    with graph.open('wb') as stream:subprocess.run([str(ninja),'-C',str(output),'-t','inputs','v8_monolith'],stdout=stream,stderr=subprocess.STDOUT,env=env,check=True)
    raw_paths.update(line.strip() for line in graph.read_text('utf-8').splitlines() if line.strip())
    paths={(output/p).resolve() for p in raw_paths}
    if object_count<1000 or len(paths)<1000:raise ValueError('V8 header dependency tracking is incomplete')
    index=compiler_index(lock);sdk=[Path(env[k]).resolve() for k in ['VCTOOLSINSTALLDIR','WINDOWSSDKDIR'] if env.get(k)];locked=[];generated=[];toolchain=[];unknown=[]
    for path in sorted(paths):
        if not path.is_file():raise ValueError('Missing V8 graph/header input: '+str(path))
        if path.is_relative_to(output):generated.append({'file':path.relative_to(output).as_posix(),'sha256':sha(path)})
        elif path.is_relative_to(core.resolve()):
            relative=path.relative_to(core.resolve()).as_posix();expected=index.get(relative.casefold())
            if expected is None:unknown.append(relative)
            elif sha(path)!=expected:raise ValueError('V8 input differs: '+relative)
            else:locked.append({'file':relative,'sha256':expected})
        elif any(path.is_relative_to(p) for p in sdk):toolchain.append(str(path))
        else:unknown.append(str(path))
    if unknown:
        (work/'converter-v8-unpinned-inputs.json').write_text(json.dumps(unknown,indent=2)+'\n','utf-8')
        raise ValueError('Unpinned V8 inputs: '+str(len(unknown)))
    result={'objects_with_header_deps':object_count,'locked_inputs':locked,'generated_build_inputs':generated,'toolchain_inputs':toolchain}
    (work/'converter-v8-input-audit.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');return result


def prepare_sdk(work,lock,archive_cache=None):
    sdk=lock['sdkjs'];source=work/'sources/sdkjs';frozen={r['file']:r for r in json.loads((ROOT/'source-manifest.json').read_text('utf-8'))['modified_files'] if r['repository']=='sdkjs'}
    row={**sdk,'destination':'sdkjs','files':[{'file':r['file'],'sha256':frozen.get(r['file'],{}).get('base_sha256',r['sha256'])} for r in sdk['files']],
         'patches':[{'file':n,'result_sha256':r['sha256']} for n,r in frozen.items()]}
    extract_selected(acquire_archive(sdk,work,archive_cache),row,work/'sources')
    for name,r in frozen.items():write_known(source/name,(ROOT/'sources/sdkjs'/name).read_bytes(),{r['base_sha256'],r['sha256']})
    compiler=lock['closure_compiler'];archive=acquire_archive(compiler,work,archive_cache);tools=work/'tools/closure20240317'
    with tarfile.open(archive,'r:gz') as tar:
        for m in tar.getmembers():
            safe_relative(m.name)
            if not m.isfile() or Path(m.name).name not in {'compiler.jar','package.json','LICENSE','LICENSE.txt','README.md'}:continue
            data=tar.extractfile(m).read();write_known(tools/Path(m.name).name,data,{hashlib.sha256(data).hexdigest()})
    jar=tools/'compiler.jar'
    if sha(jar)!=compiler['compiler_jar_sha256']:raise ValueError('Closure JAR differs')
    return source,jar


def build_sdk(work,lock,archive_cache=None,java=None,node=None):
    source,jar=prepare_sdk(work,lock,archive_cache);runtime=work/'bin/sdkjs';runtime.mkdir(parents=True,exist_ok=True)
    java=str(java or shutil.which('java') or '');node=str(node or shutil.which('node') or '')
    if not java or not node:raise ValueError('Java 21 and Node.js are required for SDK compilation and syntax checks')
    env=os.environ.copy();temp=work/'tmp';temp.mkdir(exist_ok=True);env.update({'TEMP':str(temp),'TMP':str(temp)})
    externs=json.loads((source/'configs/externs.json').read_text('utf-8'))['externs'];results={};header=(source/'build/license.header').read_text('utf-8')
    for a,b in {'@@AppCopyright':'Copyright (C) Ascensio System SIA 2012-2026. All rights reserved','@@PublisherUrl':'https://www.onlyoffice.com/','@@Version':'9.4.0','@@Build':'129'}.items():header=header.replace(a,b)
    for editor in ['word','cell','slide','visio']:
        config=json.loads((source/('configs/'+editor+'.json')).read_text('utf-8'))['sdk'];minimum=config['min'];common=config['common'];target=runtime/editor;target.mkdir(exist_ok=True)
        inputs={n:sha(source/n) for n in externs+minimum+common};indexed={r['file']:r['sha256'] for r in lock['sdkjs']['files']}
        if any(indexed.get(n)!=v for n,v in inputs.items()):raise ValueError('SDK compile input differs')
        args=['-Xmx4096m','-jar',jar.as_posix()]+['--externs='+(source/n).as_posix() for n in externs]
        args += ["--define=window.AscCommon.g_cCompanyName='onlyoffice'","--define=window.AscCommon.g_cProductVersion='9.4.0'","--define=window.AscCommon.g_cBuildNumber='129'","--define=window.AscCommon.g_cIsBeta='false'",'--rewrite_polyfills=true','--warning_level=QUIET','--language_out=ECMASCRIPT5','--compilation_level=ADVANCED']
        args += ['--js='+(source/n).as_posix() for n in minimum]+['--chunk=sdk-all-min:'+str(len(minimum))]
        args += ['--js='+(source/n).as_posix() for n in common]+['--chunk=sdk-all:'+str(len(common))+':sdk-all-min','--chunk_output_path_prefix='+target.as_posix()+'/']
        argfile=work/('converter-sdk-'+editor+'.rsp');argfile.write_text('\n'.join('"'+s.replace('\\','\\\\').replace('"','\\"')+'"' for s in args),'utf-8')
        print('Compiling converter SDK '+editor+': '+str(len(minimum)+len(common))+' source units',flush=True)
        execute([java,'@'+str(argfile)],source,env,work/('converter-sdk-'+editor+'.log'));outputs={}
        for filename in ['sdk-all-min.js','sdk-all.js']:
            p=target/filename;text=p.read_text('utf-8');text=('(function(window, undefined) {'+text+'})(window);') if filename=='sdk-all.js' else text;p.write_text(header+'\n'+text,'utf-8');execute([node,'--check',str(p)],source,env,work/('converter-sdk-'+editor+'.log'));outputs[filename]=sha(p)
        if any(sha(source/n)!=digest for n,digest in inputs.items()):raise ValueError('SDK source changed while compiling')
        results[editor]={'source_units':len(minimum)+len(common),'inputs':inputs,'outputs':outputs,'profile':'builder / no mobile or desktop addons'}
        (work/'converter-sdk-build.json').write_text(json.dumps(results,indent=2)+'\n','utf-8')
    files=['common/Native/native.js','common/Native/jquery_native.js','common/libfont/engine/fonts_native.js','common/Charts/ChartStyles.js','pdf/src/engine/drawingfile_native.js','pdf/src/annotations/stamps.json','vendor/xregexp-all-min.js']
    for name in files:
        if (source/name).is_file():(runtime/name).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,runtime/name)
    configuration='<Settings>\n<file>./sdkjs/common/Native/native.js</file>\n<file>./sdkjs/common/Native/jquery_native.js</file>\n<file>./sdkjs/vendor/xregexp-all-min.js</file>\n<allfonts>./sdkjs/common/AllFonts.js</allfonts>\n<sdkjs>./sdkjs</sdkjs>\n<LogFileConsoleLog>./renderer-console.log</LogFileConsoleLog>\n<LogFileErrors>./renderer-errors.log</LogFileErrors>\n</Settings>\n'
    (work/'bin/DoctRenderer.config').write_text(configuration,'utf-8')


def prepare_test_font(work,lock,archive_cache=None):
    folder=work/'test-fonts';folder.mkdir(exist_ok=True)
    for row in lock['test_font']['files']:
        source=acquire_archive(row,work,archive_cache);write_known(folder/row['file'],source.read_bytes(),{row['sha256']})
    return folder


def test_converter(work,lock,env,test_python=None,archive_cache=None,reuse=False):
    fonts=prepare_test_font(work,lock,archive_cache);exe=work/'bin/x2t.exe';runtime=work/'bin/sdkjs/common';log=work/'converter-acceptance.log'
    execute([str(exe),'-create-allfonts',str(runtime),str(fonts)],work,env,log)
    command=[str(test_python or sys.executable),str(ROOT/'tests/run_converter_tests.py'),'--exe',str(exe),'--work-dir',str(work)]
    if reuse:command.append('--reuse-fixtures')
    execute(command,work,env,log)
    result=json.loads((work/'converter-test-result.json').read_text('utf-8'))
    if result['failed'] or result['passed']!=25 or result['exe_sha256']!=sha(exe):raise ValueError('Converter acceptance incomplete or executable changed')
    sdk=json.loads((work/'converter-sdk-build.json').read_text('utf-8'))
    for editor,row in sdk.items():
        for name,digest in row['outputs'].items():
            if sha(work/'bin/sdkjs'/editor/name)!=digest:raise ValueError('Runtime SDK bundle differs from build report')
    compiler=json.loads((work/'converter-compiler-inputs.json').read_text('utf-8'));v8=json.loads((work/'converter-v8-input-audit.json').read_text('utf-8'))
    report={'core_revision':lock['revision'],'source_manifest_sha256':sha(ROOT/'converter.inputs.lock.json'),
            'native_units':compiler['compile_units'],'unique_native_sources':compiler['unique_compile_sources'],
            'compiler_locked_source_and_header_reads':compiler['locked_source_and_header_reads'],
            'v8_revision':lock['support_archives']['v8']['revision'],'v8_objects_with_header_deps':v8['objects_with_header_deps'],
            'v8_locked_inputs':len(v8['locked_inputs']),'v8_generated_inputs':len(v8['generated_build_inputs']),
            'sdkjs_revision':lock['sdkjs']['revision'],'sdk_source_units':{n:r['source_units'] for n,r in sdk.items()},
            'native_tests':result,'test_driver_sha256':sha(ROOT/'tests/run_converter_tests.py'),
            'artifacts':{p.name:sha(p) for p in sorted((work/'bin').glob('*.dll'))+ [exe]},
            'runtime':'Windows x64 MSVC /MD','old_office_baseline_used':False,'x2t_converter_built':True,
            'full_office_built':False,'application_gui_tested':False,'installer_built':False,
            'all_supported_format_paths_tested':False,'macros_executed':False}
    (work/'converter-build-report.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='artifacts'}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['verify','build','check'])
    for name in ['work-dir','archive-cache','source-cache','vs-root','java','node','test-python']:parser.add_argument('--'+name,type=Path)
    parser.add_argument('--reuse-fixtures',action='store_true')
    args=parser.parse_args();lock=verify_converter_inputs()
    if args.command=='verify':print(json.dumps({'ok':True,'native_compile_units':sum(COUNTS.values()),'core_inputs':len(lock['files']),'v8_dependencies':len(lock['v8_dependencies']),'sdkjs_inputs':len(lock['sdkjs']['files'])}));return
    if os.name!='nt' or not args.work_dir:parser.error('Windows and an explicit existing dependency --work-dir are required')
    work=args.work_dir.resolve()
    if work==ROOT or work in ROOT.parents or ROOT in work.parents:raise ValueError('Select a build workspace outside this repository')
    if not (work/'.qingliang-dependency-build').is_file():raise ValueError('Use the existing dependency/DOCX build workspace')
    fd=os.open(work/'.build.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,str(os.getpid()).encode('ascii'));verify();vcvars=discover_vs(args.vs_root,version_range='[17.0,18.0)');env=msvc_environment(vcvars,work);env['VSLANG']='1033'
        core=work/'sources/core';boost=work/'sources/boost/boost_1_72_0'
        report=work/'converter-build-report.json'
        if report.exists():report.unlink()
        if args.command=='build':
            core,boost=prepare_converter(work,lock,args.archive_cache,args.source_cache);prepare_tools(work,lock,args.archive_cache)
            build_openssl(work,core,env);build_v8(work,core,env,vcvars);compile_profiles(work,core,boost,lock,env);link_profiles(work,core,lock,env)
            build_sdk(work,lock,args.archive_cache,args.java,args.node)
        audit_compiler_inputs(work,core,boost,lock,env);audit_v8_inputs(work,core,lock,env,vcvars)
        test_converter(work,lock,env,args.test_python,args.archive_cache,args.reuse_fixtures)
    finally:os.close(fd);(work/'.build.lock').unlink()


if __name__=='__main__':main()
