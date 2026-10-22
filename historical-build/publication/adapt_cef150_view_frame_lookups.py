import re
from pathlib import Path
p=Path(r'D:\CodexCache\office-windows\upstream\DesktopEditors\desktop-sdk\ChromiumBasedEditors\lib\src\cefview.cpp')
s=p.read_bytes().decode('utf-8');counts={}
s,n=re.subn(r'std::vector<int64>',r'std::vector<NSCefFrame::Id>',s);counts['frame vectors']=n
s=s.replace('std::map<std::wstring, int_64_type>::iterator','std::map<std::wstring, CAscFrameId>::iterator')
s,n=re.subn(r'(m_view->GetBrowser\(\)|GetBrowser\(\))->GetFrame\((frameId|m_frameId)\)',r'NSCefFrame::GetById(\1, \2)',s);counts['request frame lookup']=n
p.write_bytes(s.encode('utf-8'));print(counts)
