"""Migrate frame storage and IPC in explicit application-owned files."""
import re
from pathlib import Path
ROOT=Path(r'D:\CodexCache\office-windows\upstream\DesktopEditors\desktop-sdk\ChromiumBasedEditors\lib')
paths=['src/cefview.cpp','src/fileconverter.h','src/applicationmanager_p.h','src/applicationmanager.cpp','src/spellchecker.cpp']
for relative in paths:
    p=ROOT/relative;s=p.read_bytes().decode('utf-8');counts={}
    s,n=re.subn(r'\bint_64_type (m_nFrameId|nFrameId|nFrameID|FrameID|FrameId)\b',r'CAscFrameId \1',s);counts['frame storage']=n
    s,n=re.subn(r'std::(list|map|pair)<([^>\n]*?)int_64_type',r'std::\1<\2CAscFrameId',s) if relative=='src/spellchecker.cpp' else (s,0);counts['spell queue']=n
    if relative=='src/spellchecker.cpp':s=s.replace('int_64_type nId','CAscFrameId nId')
    if relative=='src/cefview.cpp':
        s=s.replace('std::map<std::wstring, int_64_type> m_arCryptoImagesFrameId','std::map<std::wstring, CAscFrameId> m_arCryptoImagesFrameId')
        s=s.replace('std::pair<std::wstring, int_64_type>(sUrl1, nFrameID)','std::pair<std::wstring, CAscFrameId>(sUrl1, nFrameID)')
        s=s.replace('WOD_NEW_BACKGROUND_TAB','NSCefFrame::NewBackgroundTab')
        s,n=re.subn(r'(?P<receiver>(?:this->|this->m_pInternal->)?(?:GetBrowser\(\)|pBrowser|browser))->GetFrame\("frameEditor"\)',r'NSCefFrame::GetByName(\g<receiver>, "frameEditor")',s);counts['named frame lookup']=n
        s,n=re.subn(r'(?P<receiver>(?:View->m_handler->)?GetBrowser\(\)|pBrowser|browser)->GetFrame\((FrameID|nFrameID|nFrameId|nId|\*iter)\)',r'NSCefFrame::GetById(\g<receiver>, \2)',s);counts['frame id lookup']=n
        s,n=re.subn(r'std::vector<int_64_type>',r'std::vector<NSCefFrame::Id>',s);counts['frame enumeration']=n
        s,n=re.subn(r'NSArgumentList::GetInt64\(args, (2|3|nIndex\+\+|0|1)\)',r'NSCefFrame::GetArgument(args, \1)',s);counts['frame decode']=n
        # Every GetInt64(args, ...) occurrence in this view file addresses a frame,
        # confirmed from the adjacent message case and stored FrameId variables.
        s,n=re.subn(r'NSArgumentList::SetInt64\(([^;\n]+), ([^;\n]*?(?:FrameId|FrameID|frameId|get_FrameId)[^;\n]*)\);',r'NSCefFrame::SetArgument(\1, \2);',s);counts['frame encode']=n
    s,n=re.subn(r'\b(m_nFrameId|FrameID) = 0;',r'\1 = {};',s);counts['empty frame']=n
    if relative in ('src/cefview.cpp','src/applicationmanager_p.h'):
        s=s.replace('FrameID = -1;','#ifdef ONLYOFFICE_CEF_150\n\t\t\tFrameID.clear();\n#else\n\t\t\tFrameID = -1;\n#endif')
    p.write_bytes(s.encode('utf-8'));print(relative,counts)
