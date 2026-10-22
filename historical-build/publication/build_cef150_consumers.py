"""Build the three native consumers with matching modern frame event ABI."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import build_windows_components as build
from build_cef150_native_sdk import execute
SDK=build.SOURCE/'desktop-sdk/ChromiumBasedEditors/lib'
PROJECTS={'qt-wrapper':SDK/'qt_wrapper/qtascdocumentscore.pro','helper':SDK/'ascdocumentscore_helper.pro','shell':build.PROJECTS['shell']}
def main():
    p=argparse.ArgumentParser();p.add_argument('--projects',nargs='+',choices=list(PROJECTS),default=list(PROJECTS));a=p.parse_args()
    env=build.environment();records={}
    for name in a.projects:
        folder=build.STAGE/'build'/('native-'+name if name!='shell' else 'shell')
        folder.mkdir(exist_ok=True)
        objects=build.STAGE/'o'/('native-'+name if name!='shell' else 'shell');objects.mkdir(exist_ok=True)
        log=build.STAGE/'logs'/('build-cef150-'+name+'.log')
        command=[str(build.QT/'bin/qmake.exe'),str(PROJECTS[name]),'CONFIG-=debug','CONFIG+=release vs2019 core_disable_all_warnings office_cef150','DEFINES+=ONLYOFFICE_CEF_150 BOOST_ALL_NO_LIB','QMAKE_CXXFLAGS+=/MP4 /bigobj /utf-8','QMAKE_CFLAGS+=/MP4 /utf-8','-after','OBJECTS_DIR='+objects.as_posix()]
        execute(command,log,env,folder)
        execute(['nmake','/nologo'],log,env,folder)
        records[name]={'project':str(PROJECTS[name]),'macro':'ONLYOFFICE_CEF_150','exit':0,'log':str(log),'runtime_acceptance':False}
        (build.TASK/'evidence/cef150-consumer-builds.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        print('Built '+name,flush=True)
if __name__=='__main__':main()
