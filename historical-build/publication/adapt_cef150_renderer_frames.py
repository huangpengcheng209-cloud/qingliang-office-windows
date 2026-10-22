"""Apply explicit renderer protocol edits; preserve legacy integer semantics."""
import re
from pathlib import Path
ROOT=Path(r'D:\CodexCache\office-windows\upstream\DesktopEditors\desktop-sdk\ChromiumBasedEditors\lib\src')
path=ROOT/'cefwrapper/client_renderer_wrapper.cpp'
data=path.read_bytes();text=data.decode('utf-8');counts={}
newline='\r\r\n' if '\r\r\n' in text else ('\r\n' if '\r\n' in text else '\n')
def replace(old,new):
    global text
    count=text.count(old);assert count>0,old;counts[old]=count;text=text.replace(old,new)
replace('browser->GetFrame("frameEditor")','NSCefFrame::GetByName(browser, "frameEditor")')
replace('CefV8Context::GetCurrentContext()->GetBrowser()->GetFrame("frameEditor")','NSCefFrame::GetByName(CefV8Context::GetCurrentContext()->GetBrowser(), "frameEditor")')
replace('std::to_string(CefV8Context::GetCurrentContext()->GetFrame()->GetIdentifier())','NSCefFrame::ToString(CefV8Context::GetCurrentContext()->GetFrame()->GetIdentifier())')
text,n=re.subn(r'\bint64 (frameId|frameID) = (CefV8Context::GetCurrentContext\(\)->GetFrame\(\)->GetIdentifier\(\));',r'NSCefFrame::Id \1 = \2;',text);counts['frame local type']=n
text,n=re.subn(r'NSArgumentList::SetInt64\(([^;\n]*), (CefV8Context::GetCurrentContext\(\)->GetFrame\(\)->GetIdentifier\(\)|frameId)\);',r'NSCefFrame::SetArgument(\1, \2);',text);counts['frame IPC setters']=n
replace('std::to_string(frameID)','NSCefFrame::ToString(frameID)')
old='uint64 uframeID = (uint64)frameID;\r\n\t\t\t\tstd::string sId = std::to_string(uframeID);'
new='#ifdef ONLYOFFICE_CEF_150\r\n\t\t\t\tstd::string sId = NSCefFrame::ToString(frameID);\r\n#else\r\n\t\t\t\tuint64 uframeID = (uint64)frameID;\r\n\t\t\t\tstd::string sId = std::to_string(uframeID);\r\n#endif'
old=old.replace('\r\n',newline);new=new.replace('\r\n',newline)
replace(old,new)
old='int64 frameId = (int64)(std::stoull(sId));\r\n\t\t\t\tCefRefPtr<CefFrame> frame = CefV8Context::GetCurrentContext()->GetBrowser()->GetFrame(frameId);'
new='#ifdef ONLYOFFICE_CEF_150\r\n\t\t\t\tNSCefFrame::Id frameId = NSCefFrame::FromString(sId);\r\n#else\r\n\t\t\t\tNSCefFrame::Id frameId = (int64)(std::stoull(sId));\r\n#endif\r\n\t\t\t\tCefRefPtr<CefFrame> frame = NSCefFrame::GetById(CefV8Context::GetCurrentContext()->GetBrowser(), frameId);'
old=old.replace('\r\n',newline);new=new.replace('\r\n',newline)
replace(old,new)
path.write_bytes(text.encode('utf-8'))
print({key:value for key,value in counts.items() if len(key)<60})
