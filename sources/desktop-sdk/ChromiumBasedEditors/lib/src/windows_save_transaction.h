/* Windows save transaction for the modified ONLYOFFICE desktop SDK.
 * Distributed under the GNU Affero General Public License version 3;
 * see the adjacent filelocker.h and the repository LICENSE for notices.
 */
#ifndef QINGLIANG_WINDOWS_SAVE_TRANSACTION_H
#define QINGLIANG_WINDOWS_SAVE_TRANSACTION_H
#ifdef _WIN32
#include <windows.h>
#include <objbase.h>
#include <functional>
#include <string>
#include <vector>

namespace NSSystem { namespace WindowsSave {
// The template seam is used only by native tests. Production uses these OS calls.
struct WinApi
{
    static BOOL Read(HANDLE file, void* data, DWORD size, DWORD* done) { return ::ReadFile(file,data,size,done,NULL); }
    static BOOL Write(HANDLE file, const void* data, DWORD size, DWORD* done) { return ::WriteFile(file,data,size,done,NULL); }
    static BOOL Flush(HANDLE file) { return ::FlushFileBuffers(file); }
    static BOOL Replace(const wchar_t* target,const wchar_t* staged,const wchar_t* backup) { return ::ReplaceFileW(target,staged,backup,0,NULL,NULL); }
    static BOOL Move(const wchar_t* from,const wchar_t* to) { return ::MoveFileExW(from,to,MOVEFILE_WRITE_THROUGH); }
};

class Handle
{
public:
    HANDLE value=INVALID_HANDLE_VALUE;
    Handle()=default;
    explicit Handle(HANDLE handle):value(handle){}
    ~Handle(){Close();}
    Handle(const Handle&)=delete;
    Handle& operator=(const Handle&)=delete;
    void Close(){if(value!=INVALID_HANDLE_VALUE){DWORD error=::GetLastError();::CloseHandle(value);value=INVALID_HANDLE_VALUE;::SetLastError(error);}}
};

inline std::wstring FullPath(const std::wstring& path)
{
    DWORD size=::GetFullPathNameW(path.c_str(),0,NULL,NULL);
    if(!size)return L"";
    std::vector<wchar_t> buffer(size);
    DWORD count=::GetFullPathNameW(path.c_str(),size,buffer.data(),NULL);
    return count && count<size ? std::wstring(buffer.data(),count) : L"";
}

inline std::wstring UniqueSibling(const std::wstring& target,const wchar_t* kind)
{
    const size_t slash=target.find_last_of(L"\\/");
    if(slash==std::wstring::npos){::SetLastError(ERROR_INVALID_NAME);return L"";}
    GUID id;
    if(FAILED(::CoCreateGuid(&id))){::SetLastError(ERROR_GEN_FAILURE);return L"";}
    wchar_t text[40]={0};
    if(!::StringFromGUID2(id,text,40)){::SetLastError(ERROR_GEN_FAILURE);return L"";}
    return target.substr(0,slash+1)+L".~qingliang-"+kind+L"-"+text+L".tmp";
}

inline bool SameIdentity(const BY_HANDLE_FILE_INFORMATION& first,const BY_HANDLE_FILE_INFORMATION& last)
{
    return first.dwVolumeSerialNumber==last.dwVolumeSerialNumber && first.nFileIndexHigh==last.nFileIndexHigh &&
        first.nFileIndexLow==last.nFileIndexLow && first.nFileSizeHigh==last.nFileSizeHigh &&
        first.nFileSizeLow==last.nFileSizeLow && ::CompareFileTime(&first.ftLastWriteTime,&last.ftLastWriteTime)==0;
}

// A successful conversion is copied to a sibling, flushed, then committed. No in-place fallback.
// release/reacquire close only the editor's data handle; its advisory lock file remains intact.
template<class Api=WinApi>
bool Commit(const std::wstring& source,const std::wstring& destination,
            const std::function<bool()>& release={},const std::function<void()>& reacquire={})
{
    std::wstring target=FullPath(destination);
    if(target.empty())return false;
    Handle input(::CreateFileW(source.c_str(),GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL));
    if(input.value==INVALID_HANDLE_VALUE)return false;
    LARGE_INTEGER sourceSize;
    if(!::GetFileSizeEx(input.value,&sourceSize) || sourceSize.QuadPart<0)return false;

    DWORD attributes=::GetFileAttributesW(target.c_str());
    const bool existed=attributes!=INVALID_FILE_ATTRIBUTES;
    BY_HANDLE_FILE_INFORMATION original={0};
    if(existed)
    {
        if(attributes & (FILE_ATTRIBUTE_READONLY|FILE_ATTRIBUTE_DIRECTORY)){::SetLastError(ERROR_ACCESS_DENIED);return false;}
        Handle check(::CreateFileW(target.c_str(),FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                                   NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL));
        if(check.value==INVALID_HANDLE_VALUE || !::GetFileInformationByHandle(check.value,&original))return false;
        attributes=original.dwFileAttributes;
        if(attributes & (FILE_ATTRIBUTE_READONLY|FILE_ATTRIBUTE_DIRECTORY)){::SetLastError(ERROR_ACCESS_DENIED);return false;}
        // Replacing one name of a hard-linked file would silently leave the other names stale.
        if(original.nNumberOfLinks>1){::SetLastError(ERROR_NOT_SUPPORTED);return false;}
        BY_HANDLE_FILE_INFORMATION sourceInfo={0};
        if(!::GetFileInformationByHandle(input.value,&sourceInfo))return false;
        if(original.dwVolumeSerialNumber==sourceInfo.dwVolumeSerialNumber && original.nFileIndexHigh==sourceInfo.nFileIndexHigh &&
           original.nFileIndexLow==sourceInfo.nFileIndexLow){::SetLastError(ERROR_INVALID_PARAMETER);return false;}
        // Preserve a symbolic-link entry by committing to its resolved file, not replacing the link.
        DWORD needed=::GetFinalPathNameByHandleW(check.value,NULL,0,FILE_NAME_NORMALIZED);
        if(!needed)return false;
        std::vector<wchar_t> resolved(needed+1);
        DWORD length=::GetFinalPathNameByHandleW(check.value,resolved.data(),(DWORD)resolved.size(),FILE_NAME_NORMALIZED);
        if(!length || length>=resolved.size())return false;
        target.assign(resolved.data(),length);
    }
    else if(::GetLastError()!=ERROR_FILE_NOT_FOUND && ::GetLastError()!=ERROR_PATH_NOT_FOUND)return false;

    const std::wstring staged=UniqueSibling(target,L"save");
    const std::wstring backup=UniqueSibling(target,L"backup");
    if(staged.empty() || backup.empty())return false;
    if(::GetFileAttributesW(backup.c_str())!=INVALID_FILE_ATTRIBUTES){::SetLastError(ERROR_FILE_EXISTS);return false;}
    // Protect temporary content with the target's DACL from creation, including crash leftovers.
    std::vector<BYTE> security;
    SECURITY_ATTRIBUTES access={sizeof(access),NULL,FALSE};
    if(existed)
    {
        DWORD needed=0;
        ::GetFileSecurityW(target.c_str(),DACL_SECURITY_INFORMATION,NULL,0,&needed);
        if(!needed)return false;
        security.resize(needed);
        if(!::GetFileSecurityW(target.c_str(),DACL_SECURITY_INFORMATION,security.data(),needed,&needed))return false;
        access.lpSecurityDescriptor=security.data();
    }
    Handle output(::CreateFileW(staged.c_str(),GENERIC_WRITE,0,existed?&access:NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL));
    if(output.value==INVALID_HANDLE_VALUE)return false;
    struct Cleanup
    {
        Handle& output;const std::wstring& path;bool erase=true;
        ~Cleanup(){DWORD error=::GetLastError();output.Close();if(erase)::DeleteFileW(path.c_str());::SetLastError(error);}
    } cleanup{output,staged};
    std::vector<BYTE> buffer(64*1024);
    unsigned long long copied=0;
    while(copied<(unsigned long long)sourceSize.QuadPart)
    {
        const unsigned long long remaining=(unsigned long long)sourceSize.QuadPart-copied;
        DWORD count=remaining<buffer.size()?(DWORD)remaining:(DWORD)buffer.size();
        DWORD read=0,written=0;
        if(!Api::Read(input.value,buffer.data(),count,&read))return false;
        if(read!=count){::SetLastError(ERROR_HANDLE_EOF);return false;}
        if(!Api::Write(output.value,buffer.data(),read,&written))return false;
        if(written!=read){::SetLastError(ERROR_WRITE_FAULT);return false;}
        copied+=written;
    }
    if(!Api::Flush(output.value))return false;
    output.Close();
    if(existed)
    {
        const DWORD basic=attributes & (FILE_ATTRIBUTE_ARCHIVE|FILE_ATTRIBUTE_HIDDEN|FILE_ATTRIBUTE_SYSTEM|FILE_ATTRIBUTE_NOT_CONTENT_INDEXED);
        if(!::SetFileAttributesW(staged.c_str(),basic?basic:FILE_ATTRIBUTE_NORMAL))return false;
    }
    // Allocate/copy all buffers before releasing the editor's original-file handle.
    if(release && !release())return false;
    struct Relock {const std::function<void()>& call;~Relock(){DWORD error=::GetLastError();if(call)call();::SetLastError(error);}} relock{reacquire};

    bool committed=false;
    DWORD error=ERROR_SUCCESS;
    if(existed)
    {
        // Detect changes while the output was being prepared, including a replaced directory entry.
        Handle check(::CreateFileW(target.c_str(),FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                                   NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL));
        BY_HANDLE_FILE_INFORMATION current={0};
        if(check.value==INVALID_HANDLE_VALUE || !::GetFileInformationByHandle(check.value,&current))return false;
        if(!SameIdentity(original,current)){::SetLastError(ERROR_SHARING_VIOLATION);return false;}
        check.Close();
        if(Api::Replace(target.c_str(),staged.c_str(),backup.c_str()))
        {
            committed=true;
            ::DeleteFileW(backup.c_str());
        }
        else
        {
            error=::GetLastError();
            // ReplaceFile can fail after moving the original to the backup. Restore without overwriting another file.
            if(::GetFileAttributesW(target.c_str())==INVALID_FILE_ATTRIBUTES && ::GetFileAttributesW(backup.c_str())!=INVALID_FILE_ATTRIBUTES)
            {
                if(!Api::Move(backup.c_str(),target.c_str()))cleanup.erase=false;
            }
            // Never delete a backup on failure. If rollback fails, retain both complete files for recovery.
        }
    }
    else
    {
        // No REPLACE_EXISTING: another program creating the destination wins instead of being overwritten.
        committed=Api::Move(staged.c_str(),target.c_str())!=FALSE;
        if(!committed)error=::GetLastError();
    }
    if(!committed)::SetLastError(error?error:ERROR_WRITE_FAULT);
    return committed;
}
} }
#endif
#endif
