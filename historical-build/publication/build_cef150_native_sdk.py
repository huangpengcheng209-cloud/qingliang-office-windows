"""Focused compiler checks then one release build in the stable task staging tree."""
import argparse,ast,difflib,json,re,sys,subprocess,shutil,os
from zipfile import ZipFile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import build_windows_components as build
SDK=build.SOURCE/'desktop-sdk/ChromiumBasedEditors/lib'
CEF=build.STAGE/'build/cef-upgrade-preflight'
def execute(command,log,env,folder):
    command=command.copy();command[0]=shutil.which(command[0],path=env['PATH']) or command[0]
    with log.open('ab') as stream:
        stream.write(('\nCOMMAND '+repr(command)+'\n').encode('utf-8'))
        offset=stream.tell()
        result=subprocess.run(command,cwd=folder,env=env,stdout=stream,stderr=stream)
    if result.returncode:
        with log.open('rb') as stream:stream.seek(offset);raw=stream.read()
        try:text=raw.decode('utf-8')
        except UnicodeDecodeError:text=raw.decode('mbcs',errors='replace')
        lines=[line for line in text.splitlines() if re.search(r'error C\d+|fatal error|LNK\d+|U1073|U1052',line)]
        print('\n'.join(line[:320] for line in (lines[:8] or text.splitlines()[-4:])),flush=True)
        raise RuntimeError('Compiler exit '+str(result.returncode)+'; see '+str(log))
def prepare():
    text=(CEF/'libcef_dll/CMakeLists.txt').read_text(encoding='utf-8')
    groups=re.findall(r'set\((LIBCEF_[A-Z_]+_SRCS)\s+(.*?)\n\s*\)',text,re.S)
    source=[]
    for name,body in groups:
        if name.endswith(('_LINUX','_MAC')) or '_TEST_' in name:continue
        for relative in re.findall(r'^\s*([^\s()]+\.cc)\s*$',body,re.M):
            p=CEF/'libcef_dll'/relative
            if p.is_file():source.append(p.relative_to(CEF).as_posix())
    # LIBCEF_SRCS is the one upstream group without a trailing _SRCS category.
    group=re.search(r'set\(LIBCEF_SRCS\s+(.*?)\n\s*\)',text,re.S)
    source.extend('libcef_dll/'+p for p in re.findall(r'^\s*([^\s()]+\.cc)\s*$',group[1],re.M))
    old=(SDK/'cef_pri/cef_client.pri').read_text(encoding='utf-8')
    # Preserve the utility selection, only replacing the matching upstream source.
    lines=old.splitlines();in_sources=False;platform='common';samples=[]
    for line in lines:
        if line.strip().startswith('core_windows {'):platform='win'
        elif line.strip().startswith('core_linux {'):platform='linux'
        elif line.strip().startswith('core_mac {'):platform='mac'
        elif line.strip()=='}':platform='common'
        if line.strip().startswith('SOURCES +='):in_sources=True
        elif line.strip().startswith(('HEADERS +=','OBJECTIVE_SOURCES +=')):in_sources=False
        if in_sources and platform in ('common','win') and not line.lstrip().startswith('#'):
            match=re.search(r'\$\$CEF_SRC_PATH/(\S+\.cc)',line)
            if match and (CEF/match[1]).is_file():samples.append(match[1])
    # Modern ClientHandler and RootWindowManager depend on additional helpers.
    # Use the exact upstream Windows source groups, excluding the sample entry.
    archive=next((build.STAGE/'downloads').glob('cef-c1a097e*.zip'))
    with ZipFile(archive) as z:
        variables=ast.literal_eval(z.read(next(n for n in z.namelist() if n.endswith('/cef_paths2.gypi'))).decode())['variables']
        client_path='tests/cefclient/browser/client_handler.cc'
        original=z.read(next(n for n in z.namelist() if n.endswith('/'+client_path))).decode()
    before='''    : use_views_(delegate ? delegate->UseViews()
                          : MainContext::Get()->UseViewsGlobal()),
      use_alloy_style_(delegate ? delegate->UseAlloyStyle()
                                : MainContext::Get()->UseAlloyStyleGlobal()),'''
    assert original.count(before)==1
    after='''    // Office's self delegate is not constructed during this base constructor.
    // Its Qt host always requires native windows with Alloy rendering.
#ifdef ONLYOFFICE_CEF_150
    : use_views_(false),
      use_alloy_style_(true),
#else
'''+before+'''
#endif'''
    patched=original.replace(before,after)
    client=CEF/client_path
    if client.read_text(encoding='utf-8')!=patched:client.write_text(patched,encoding='utf-8')
    patch=''.join(difflib.unified_diff(original.splitlines(True),patched.splitlines(True),'a/'+client_path,'b/'+client_path))
    Path(__file__).with_name('cef150-client-handler-construction.patch').write_text(patch,encoding='utf-8')
    for family in ('shared','cefclient'):
        for category in ('browser','common','renderer','win'):
            for path in variables[family+'_sources_'+category]:
                # Office supplies these callbacks in its own wrapper sources.
                excluded=('cefclient_win.cc','client_app_delegates_common.cc','client_app_delegates_renderer.cc')
                if path.endswith('.cc') and Path(path).name not in excluded:
                    assert (CEF/path).is_file(),path
                    samples.append(path)
    pri=SDK/'cef_pri_150';pri.mkdir(exist_ok=True)
    for name,paths in (('cef_sources.pri',source),('cef_client_sources.pri',samples)):
        paths=sorted(set(paths));assert paths
        (pri/name).write_text('SOURCES += '+' \\\n    '.join('$$CEF_SRC_PATH/'+p for p in paths)+'\n',encoding='utf-8')
    return {'wrapper_sources':len(set(source)),'client_sources':len(set(samples))}
def main():
    p=argparse.ArgumentParser();p.add_argument('--compile',action='store_true');p.add_argument('--symbols',action='store_true');p.add_argument('--check',choices=('application','renderer','view'));a=p.parse_args()
    counts=prepare();env=build.environment();env['OFFICE_CEF_SDK_ROOT']=str(CEF)
    folder=build.STAGE/'build/native-sdk';folder.mkdir(exist_ok=True)
    objects=build.STAGE/'o/native-sdk';objects.mkdir(exist_ok=True)
    log=build.STAGE/'logs'/('build-native-sdk-cef150-'+(a.check or 'full')+'.log')
    cmd=[str(build.QT/'bin/qmake.exe'),str(SDK/'ascdocumentscore.pro'),'CONFIG-=debug','CONFIG+=release vs2019 core_disable_all_warnings office_cef150','QMAKE_CXXFLAGS+=/MP4 /bigobj /utf-8','QMAKE_CFLAGS+=/MP4 /utf-8','DEFINES+=BOOST_ALL_NO_LIB','-after','OBJECTS_DIR='+objects.as_posix()]
    if a.symbols:
        cmd.extend(['QMAKE_CXXFLAGS+=/Z7','QMAKE_LFLAGS+=/DEBUG /PDB:'+str(folder/'ascdocumentscore.pdb')])
        # Retain release optimization, adding debug records only to key callers.
        selected=[SDK/'src'/n for n in ('applicationmanager.cpp','cefapplication.cpp','cefview.cpp')]
        selected.extend(CEF/'tests/cefclient/browser'/n for n in ('main_context.cc','main_context_impl.cc','base_client_handler.cc','client_handler.cc'))
        selected.append(CEF/'tests/shared/browser/client_app_browser.cc')
        for path in selected:os.utime(path,None)
    execute(cmd,log,env,folder)
    makefile='Makefile.Release' if (folder/'Makefile.Release').is_file() else 'Makefile'
    if a.compile:execute(['nmake','/nologo'],log,env,folder)
    if a.check:
        target={'application':'cefapplication','renderer':'client_renderer_wrapper','view':'cefview'}[a.check]
        rules=(folder/makefile).read_text(encoding='utf-8').splitlines()
        matches=[line.split(': ',1)[0] for line in rules if target+'.obj: ' in line]
        assert len(matches)==1,matches
        execute(['nmake','/nologo','/f',makefile,matches[0]],log,env,folder)
    report={'project':str(SDK/'ascdocumentscore.pro'),'cef':'150.0.22','selected_sources':counts,'makefile':str(folder/makefile),'compile_release_passed':bool(a.compile),'focused_check':a.check,'current_release_replaced':False}
    (build.TASK/'evidence/native-sdk-cef150-build.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
if __name__=='__main__':main()
