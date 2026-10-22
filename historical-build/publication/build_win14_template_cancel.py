"""Build the integrated template-cancellation change with the normal SDK Makefile."""
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(r'D:\CodexWorkspaces\2026-10-13\office-windows')
STAGE=Path(r'D:\CodexCache\office-windows')
sys.path.insert(0,str(ROOT/'scripts'))
import build_windows_components as build


def main():
    source=STAGE/'upstream/DesktopEditors/desktop-sdk/ChromiumBasedEditors/lib/src'
    assert 'const std::atomic<bool>* pCancel' in (source/'x2t.h').read_text(encoding='utf-8')
    assert 'false, &m_bIsExit' in (source/'templatesmanager.h').read_text(encoding='utf-8')
    for name in ('applicationmanager.cpp','cefapplication.cpp','cefview.cpp'):
        text=(source/name).read_text(encoding='utf-8')
        assert 'QlShutdownTrace' not in text and 'shutdown_trace.h' not in text,name
    makefile=STAGE/'build/native-sdk/Makefile'
    text=makefile.read_text(encoding='utf-8')
    assert '/Z7' not in text and '/DEBUG' not in text and 'Makefile.diagnostic' not in text
    start=time.monotonic()
    build.execute(['nmake','/nologo'],STAGE/'logs/win14-native-sdk.log',build.environment(),makefile.parent)
    output=build.CORE/'build/lib/win_64/ascdocumentscore.dll'
    binary=output.read_bytes()
    assert b'OFFICE_SHUTDOWN_TRACE' not in binary and b'manager.close.private-begin' not in binary
    target=STAGE/'candidate/app/ascdocumentscore.dll'
    shutil.copyfile(output,target)
    assert build.sha(output)==build.sha(target)
    record={'version':'9.4.0.129-win.14','normal_release_makefile':True,'diagnostic_instrumentation_absent':True,
            'makefile_sha256':build.sha(makefile),'sdk_sha256':build.sha(output),
            'seconds':round(time.monotonic()-start,3),
            'headers':{name:build.sha(source/name) for name in ('x2t.h','templatesmanager.h')},
            'scope':'Only native SDK rebuilt; unchanged components reused with hash verification'}
    (ROOT/'evidence/win14-native-sdk-build.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record),flush=True)


if __name__=='__main__':main()
