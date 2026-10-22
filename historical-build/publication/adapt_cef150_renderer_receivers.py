import re
from pathlib import Path
path=Path(r'D:\CodexCache\office-windows\upstream\DesktopEditors\desktop-sdk\ChromiumBasedEditors\lib\src\cefwrapper\client_renderer_wrapper.cpp')
text=path.read_bytes().decode('utf-8');counts={}
for old,new in (('std::vector<int64> ids','std::vector<NSCefFrame::Id> ids'),('std::vector<int64>::iterator','std::vector<NSCefFrame::Id>::iterator'),('std::vector<int64> identifiers','std::vector<NSCefFrame::Id> identifiers'),('browser->GetFrame(sFrameName)','NSCefFrame::GetByName(browser, sFrameName)')):
    count=text.count(old);assert count>0,old;counts[old]=count;text=text.replace(old,new)
text,n=re.subn(r'int64 (nFrameId|frameId) = NSArgumentList::GetInt64\(([^;]+)\);',r'NSCefFrame::Id \1 = NSCefFrame::GetArgument(\2);',text);counts['frame argument decoding']=n
text,n=re.subn(r'int64 (nId|frameID) = \(int64\)std::stoll\(([^;]+)\);',r'NSCefFrame::Id \1 = NSCefFrame::FromString(\2);',text);counts['string frame decoding']=n
text,n=re.subn(r'browser->GetFrame\((nFrameId|frameId|nId|frameID|\*i)\)',r'NSCefFrame::GetById(browser, \1)',text);counts['frame lookup']=n
path.write_bytes(text.encode('utf-8'));print(counts)
