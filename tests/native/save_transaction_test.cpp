// Native acceptance fixture for the published modified ONLYOFFICE Win32 save component.
// Distributed under this repository's AGPLv3 terms and applicable upstream notices.
#include "windows_save_transaction.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;
using NSSystem::WindowsSave::WinApi;
using NSSystem::WindowsSave::Commit;
const std::string old_bytes = "original content must survive\n";
const std::string new_bytes = std::string(140000, 'N') + "\nnew complete content\n";

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void put(const fs::path& path, const std::string& data) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    require(stream.is_open(), "Cannot create fixture file");
    stream.write(data.data(), static_cast<std::streamsize>(data.size()));
    stream.close();
    require(!stream.fail(), "Cannot complete fixture file");
}

std::string get(const fs::path& path) {
    std::ifstream stream(path, std::ios::binary);
    require(stream.is_open(), "Expected fixture file missing");
    return std::string(std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>());
}

struct FailRead : WinApi {
    static BOOL Read(HANDLE, void*, DWORD, DWORD*) { SetLastError(ERROR_READ_FAULT); return FALSE; }
};
struct FailWrite : WinApi {
    static BOOL Write(HANDLE, const void*, DWORD, DWORD*) { SetLastError(ERROR_DISK_FULL); return FALSE; }
};
struct FailFlush : WinApi {
    static BOOL Flush(HANDLE) { SetLastError(ERROR_WRITE_FAULT); return FALSE; }
};
struct FailReplace : WinApi {
    static BOOL Replace(const wchar_t*, const wchar_t*, const wchar_t*) { SetLastError(ERROR_ACCESS_DENIED); return FALSE; }
};
struct CompetingCreation : WinApi {
    static BOOL Move(const wchar_t* from, const wchar_t* to) {
        put(fs::path(to), "another writer wins\n");
        return WinApi::Move(from, to);
    }
};
struct ReplaceAfterBackup : WinApi {
    static BOOL Replace(const wchar_t* target, const wchar_t*, const wchar_t* backup) {
        require(MoveFileExW(target, backup, MOVEFILE_WRITE_THROUGH) != FALSE, "Cannot simulate backup transition");
        SetLastError(ERROR_UNABLE_TO_MOVE_REPLACEMENT);
        return FALSE;
    }
};

void pair(const fs::path& dir) {
    put(dir / L"source.bin", new_bytes);
    put(dir / L"target.bin", old_bytes);
}

template<class Api> void failure_preserves(const fs::path& dir) {
    pair(dir);
    require(!Commit<Api>((dir / L"source.bin").wstring(), (dir / L"target.bin").wstring()), "Injected failure reported success");
    require(get(dir / L"target.bin") == old_bytes, "Original target corrupted after injected failure");
    require(get(dir / L"source.bin") == new_bytes, "Converted source corrupted");
    for (const auto& item : fs::directory_iterator(dir)) {
        require(item.path().filename().wstring().find(L".~qingliang-") != 0, "Temporary/backup content not cleaned after recoverable failure");
    }
}

void clear_case(const fs::path& dir) {
    // Each case directory was exclusively created by this process. Never recurse.
    for (const auto& item : fs::directory_iterator(dir)) {
        require(!item.is_directory(), "Unexpected directory in native fixture");
        SetFileAttributesW(item.path().c_str(), FILE_ATTRIBUTE_NORMAL);
        require(DeleteFileW(item.path().c_str()) != FALSE, "Cannot clean owned fixture file");
    }
    require(RemoveDirectoryW(dir.c_str()) != FALSE, "Cannot clean owned case directory");
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 3) return 2;
    const fs::path root = fs::absolute(fs::path(argv[1]));
    const fs::path report = fs::path(argv[2]);
    if (!fs::is_directory(root) || !fs::is_empty(root)) return 3;
    unsigned passed = 0, failed = 0;
    auto test = [&](const wchar_t* name, auto body) {
        const fs::path dir = root / name;
        try {
            require(CreateDirectoryW(dir.c_str(), nullptr) != FALSE, "Case directory already exists");
            body(dir);
            clear_case(dir);
            ++passed;
            std::cout << "PASS case " << passed + failed << '\n';
        } catch (const std::exception& error) {
            ++failed;
            std::cerr << "FAIL case " << passed + failed << ": " << error.what() << '\n';
        }
    };

    test(L"overwrite", [](const fs::path& dir) {
        pair(dir);
        require(Commit((dir / L"source.bin").wstring(), (dir / L"target.bin").wstring()), "Overwrite failed");
        require(get(dir / L"target.bin") == new_bytes, "Overwrite content differs");
        require(get(dir / L"source.bin") == new_bytes, "Source was consumed");
    });
    test(L"new-unicode", [](const fs::path& dir) {
        put(dir / L"source.bin", new_bytes);
        const auto target = dir / L"新建 文档.bin";
        require(Commit((dir / L"source.bin").wstring(), target.wstring()), "Unicode destination creation failed");
        require(get(target) == new_bytes, "Created content differs");
    });
    test(L"empty-content", [](const fs::path& dir) {
        pair(dir);
        put(dir / L"source.bin", "");
        require(Commit((dir / L"source.bin").wstring(), (dir / L"target.bin").wstring()), "Empty file commit failed");
        require(get(dir / L"target.bin").empty(), "Empty content not preserved");
    });
    test(L"same-file", [](const fs::path& dir) {
        put(dir / L"target.bin", old_bytes);
        auto target = (dir / L"target.bin").wstring();
        require(!Commit(target, target), "Same-file operation was accepted");
        require(get(dir / L"target.bin") == old_bytes, "Same-file target changed");
    });
    test(L"missing-source", [](const fs::path& dir) {
        put(dir / L"target.bin", old_bytes);
        require(!Commit((dir / L"missing.bin").wstring(), (dir / L"target.bin").wstring()), "Missing input accepted");
        require(get(dir / L"target.bin") == old_bytes, "Missing input changed target");
    });
    test(L"readonly", [](const fs::path& dir) {
        pair(dir);
        require(SetFileAttributesW((dir / L"target.bin").c_str(), FILE_ATTRIBUTE_READONLY) != FALSE, "Cannot set readonly fixture");
        require(!Commit((dir / L"source.bin").wstring(), (dir / L"target.bin").wstring()), "Readonly target overwritten");
        require(get(dir / L"target.bin") == old_bytes, "Readonly content changed");
    });
    test(L"hardlink", [](const fs::path& dir) {
        pair(dir);
        require(CreateHardLinkW((dir / L"alias.bin").c_str(), (dir / L"target.bin").c_str(), nullptr) != FALSE, "Cannot create hardlink fixture");
        require(!Commit((dir / L"source.bin").wstring(), (dir / L"target.bin").wstring()), "Hardlinked target accepted");
        require(get(dir / L"target.bin") == old_bytes && get(dir / L"alias.bin") == old_bytes, "Hardlink content changed");
    });
    test(L"locked-target", [](const fs::path& dir) {
        pair(dir);
        NSSystem::WindowsSave::Handle handle(CreateFileW((dir / L"target.bin").c_str(), GENERIC_READ,
            FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr));
        require(handle.value != INVALID_HANDLE_VALUE, "Cannot lock fixture");
        require(!Commit((dir / L"source.bin").wstring(), (dir / L"target.bin").wstring()), "Locked target overwritten");
        require(get(dir / L"target.bin") == old_bytes, "Locked target changed");
    });
    test(L"read-failure", [](const fs::path& dir) { failure_preserves<FailRead>(dir); });
    test(L"disk-full", [](const fs::path& dir) { failure_preserves<FailWrite>(dir); });
    test(L"flush-failure", [](const fs::path& dir) { failure_preserves<FailFlush>(dir); });
    test(L"replace-failure", [](const fs::path& dir) { failure_preserves<FailReplace>(dir); });
    test(L"competing-create", [](const fs::path& dir) {
        put(dir / L"source.bin", new_bytes);
        require(!Commit<CompetingCreation>((dir / L"source.bin").wstring(), (dir / L"target.bin").wstring()), "Competing writer overwritten");
        require(get(dir / L"target.bin") == "another writer wins\n", "Competing content corrupted");
    });
    test(L"backup-rollback", [](const fs::path& dir) { failure_preserves<ReplaceAfterBackup>(dir); });

    std::ofstream output(report, std::ios::binary | std::ios::trunc);
    output << "{\"passed\":" << passed << ",\"failed\":" << failed << "}\n";
    output.close();
    std::cout << passed << " passed, " << failed << " failed\n";
    return failed ? 1 : 0;
}
