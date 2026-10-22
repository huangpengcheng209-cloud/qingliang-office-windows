// Source-built x2t prerequisites; native Windows OLE interoperability checks.
// This test is part of the AGPLv3 community project; upstream notices are preserved separately.
#include <windows.h>
#include <objbase.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <boost/regex.hpp>
#include <boost/date_time/gregorian/gregorian.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include "Common/cfcpp/compoundfile.h"
#include "Common/cfcpp/cfexception.h"

namespace fs = std::filesystem;
using Bytes = std::vector<BYTE>;
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
template<class T> struct Com {
    T* value = nullptr;
    ~Com() { if (value) value->Release(); }
    T** put() { return &value; }
    T* operator->() const { return value; }
};
Bytes pattern(size_t size) {
    Bytes data(size);
    for (size_t i = 0; i < size; ++i) data[i] = static_cast<BYTE>((i * 31 + 7) % 251);
    return data;
}
void clear_owned(const fs::path& path, const fs::path& owner) {
    const auto actual = fs::weakly_canonical(path).wstring();
    const auto parent = fs::weakly_canonical(owner).wstring();
    require(actual == parent || actual.find(parent + L"\\") == 0, "Cleanup escapes owned fixture directory");
    for (const auto& entry : fs::directory_iterator(path)) {
        require(!entry.is_symlink(), "Unexpected fixture link; preserved");
        if (entry.is_directory()) clear_owned(entry.path(), owner);
        else require(DeleteFileW(entry.path().c_str()) != FALSE, "Cannot clean owned file");
    }
    require(RemoveDirectoryW(path.c_str()) != FALSE, "Cannot clean owned directory");
}
void save_cf(const fs::path& file, const Bytes& data, const std::wstring& name = L"WordDocument",
             CFCPP::CFSVersion version = CFCPP::Ver_3) {
    CFCPP::CompoundFile document(version, CFCPP::Default);
    auto stream = document.RootStorage()->AddStream(name);
    // SetData requires nonempty data. AddStream alone creates a valid empty stream.
    if (!data.empty()) stream->SetData(data);
    require(document.Save(file.wstring()), "CompoundFileLib save failed");
    document.Close();
}
Bytes read_cf(const fs::path& file, const std::wstring& name = L"WordDocument") {
    CFCPP::CompoundFile document(file.wstring());
    auto result = document.RootStorage()->GetStream(name)->getData();
    document.Close();
    return result;
}
Bytes read_windows(const fs::path& file, const std::wstring& name) {
    Com<IStorage> storage;
    require(SUCCEEDED(StgOpenStorage(file.c_str(), nullptr, STGM_READ | STGM_SHARE_DENY_WRITE,
                                    nullptr, 0, storage.put())), "Windows cannot open generated OLE storage");
    Com<IStream> stream;
    require(SUCCEEDED(storage->OpenStream(name.c_str(), nullptr, STGM_READ | STGM_SHARE_EXCLUSIVE,
                                         0, stream.put())), "Windows cannot open generated OLE stream");
    STATSTG stats = {};
    require(SUCCEEDED(stream->Stat(&stats, STATFLAG_NONAME)) && stats.cbSize.QuadPart < 1000000, "Unexpected OLE stream size");
    Bytes data(static_cast<size_t>(stats.cbSize.QuadPart));
    ULONG count = 0;
    require(SUCCEEDED(stream->Read(data.data(), static_cast<ULONG>(data.size()), &count)) && count == data.size(), "Windows OLE stream read differs");
    return data;
}
void save_windows(const fs::path& file, const Bytes& data, const std::wstring& name) {
    Com<IStorage> storage;
    require(SUCCEEDED(StgCreateDocfile(file.c_str(), STGM_CREATE | STGM_READWRITE | STGM_SHARE_EXCLUSIVE,
                                     0, storage.put())), "Windows OLE creation failed");
    Com<IStream> stream;
    require(SUCCEEDED(storage->CreateStream(name.c_str(), STGM_CREATE | STGM_WRITE | STGM_SHARE_EXCLUSIVE,
                                           0, 0, stream.put())), "Windows OLE stream creation failed");
    ULONG count = 0;
    require(SUCCEEDED(stream->Write(data.data(), static_cast<ULONG>(data.size()), &count)) && count == data.size(), "Windows OLE write failed");
    require(SUCCEEDED(stream->Commit(STGC_DEFAULT)) && SUCCEEDED(storage->Commit(STGC_DEFAULT)), "Windows OLE commit failed");
}
Bytes raw_bytes(const fs::path& file) {
    std::ifstream input(file, std::ios::binary);
    require(input.good(), "Cannot read fixture bytes");
    return Bytes(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 3) return 2;
    const fs::path root = fs::absolute(argv[1]);
    require(fs::is_directory(root) && fs::is_empty(root), "Fixture root must be empty");
    require(SUCCEEDED(CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED)), "COM initialization failed");
    unsigned passed = 0, failed = 0;
    auto test = [&](const wchar_t* name, auto body) {
        const auto dir = root / name;
        try {
            require(CreateDirectoryW(dir.c_str(), nullptr) != FALSE, "Fixture directory exists");
            body(dir);
            clear_owned(dir, dir);
            ++passed;
            std::cout << "PASS case " << passed + failed << '\n';
        } catch (const std::exception& error) {
            ++failed;
            std::cerr << "FAIL case " << passed + failed << ": " << error.what() << '\n';
        }
    };
    test(L"regex-capture", [](const fs::path&) {
        boost::smatch match;
        const std::string value = "report-2026.docx";
        require(boost::regex_match(value, match, boost::regex("report-([0-9]{4})\\.docx")) && match[1] == "2026", "Regex capture differs");
    });
    test(L"regex-replace", [](const fs::path&) {
        require(boost::regex_replace(std::string("a  b\tc"), boost::regex("\\s+"), std::string(" ")) == "a b c", "Regex replace differs");
    });
    test(L"regex-invalid", [](const fs::path&) {
        bool rejected = false;
        try { boost::regex expression("["); } catch (const boost::regex_error&) { rejected = true; }
        require(rejected, "Invalid regex accepted");
    });
    test(L"regex-wide-chinese", [](const fs::path&) {
        require(boost::regex_match(std::wstring(L"中文2026"), boost::wregex(L"中文[0-9]{4}")), "Wide regex differs");
    });
    test(L"date-leap", [](const fs::path&) {
        using namespace boost::gregorian;
        require(date(2024, 2, 28) + days(1) == date(2024, 2, 29), "Leap day differs");
        require(std::string(greg_month(2).as_long_string()) == "February", "Compiled DateTime month function differs");
    });
    test(L"date-duration", [](const fs::path&) {
        using namespace boost::posix_time;
        const auto start = time_from_string("2026-10-22 23:30:00");
        require(to_iso_extended_string(start + hours(2)) == "2026-10-23T01:30:00", "DateTime midnight rollover differs");
    });
    test(L"date-invalid", [](const fs::path&) {
        bool rejected = false;
        try { boost::gregorian::date value(2023, 2, 29); } catch (const std::out_of_range&) { rejected = true; }
        require(rejected, "Invalid calendar date accepted");
    });
    for (const auto size : {63u, 4095u, 4096u, 100000u}) {
        const auto name = L"cf-size-" + std::to_wstring(size);
        test(name.c_str(), [&](const fs::path& dir) {
            const auto data = pattern(size);
            const auto file = dir / L"document.ole";
            save_cf(file, data);
            require(read_cf(file) == data, "Compound stream boundary roundtrip differs");
        });
    }
    test(L"cf-empty-stream", [](const fs::path& dir) {
        const auto file = dir / L"empty.ole";
        save_cf(file, {});
        require(read_cf(file).empty(), "Empty compound stream differs");
    });
    test(L"cf-nested-unicode", [](const fs::path& dir) {
        const auto file = dir / L"报告\U0001F600.ole";
        const auto data = pattern(123);
        {
            CFCPP::CompoundFile document;
            document.RootStorage()->AddStorage(L"中文目录")->AddStream(L"数据\U0001F600")->SetData(data);
            require(document.Save(file.wstring()), "Nested storage save failed");
            document.Close();
        }
        CFCPP::CompoundFile document(file.wstring());
        require(document.RootStorage()->GetStorage(L"中文目录")->GetStream(L"数据\U0001F600")->getData() == data, "Nested Unicode storage differs");
        document.Close();
    });
    test(L"cf-resize-overwrite", [](const fs::path& dir) {
        CFCPP::CompoundFile document;
        auto stream = document.RootStorage()->AddStream(L"WordDocument");
        stream->SetData(pattern(5000));
        stream->Resize(100);
        const Bytes update = {1, 2, 3};
        stream->Write(update, 10);
        auto expected = pattern(100);
        std::copy(update.begin(), update.end(), expected.begin() + 10);
        const auto file = dir / L"resize.ole";
        require(document.Save(file.wstring()), "Resize save failed");
        document.Close();
        require(read_cf(file) == expected, "Stream resize/overwrite differs");
    });
    test(L"cf-rename-delete", [](const fs::path& dir) {
        CFCPP::CompoundFile document;
        auto root = document.RootStorage();
        root->AddStream(L"old")->SetData(pattern(73));
        root->AddStream(L"remove")->SetData(pattern(1));
        root->RenameItem(L"old", L"new");
        root->Delete(L"remove");
        const auto file = dir / L"rename.ole";
        require(document.Save(file.wstring()), "Rename save failed");
        document.Close();
        CFCPP::CompoundFile reopened(file.wstring());
        std::shared_ptr<CFCPP::CFStream> missing;
        require(reopened.RootStorage()->GetStream(L"new")->getData() == pattern(73) && !reopened.RootStorage()->TryGetStream(L"remove", missing), "Rename/delete differs");
        reopened.Close();
    });
    test(L"cf-update-commit", [](const fs::path& dir) {
        const auto file = dir / L"update.ole";
        save_cf(file, pattern(63));
        {
            CFCPP::CompoundFile document(file.wstring(), CFCPP::Update);
            document.RootStorage()->GetStream(L"WordDocument")->SetData(pattern(8192));
            document.Commit();
            document.Close();
        }
        require(read_cf(file) == pattern(8192) && read_windows(file, L"WordDocument") == pattern(8192), "Update commit differs");
    });
    test(L"cf-invalid-signature", [](const fs::path& dir) {
        const auto file = dir / L"invalid.ole";
        { std::ofstream output(file, std::ios::binary); const std::string data(512, 'X'); output.write(data.data(), data.size()); }
        bool rejected = false;
        try { CFCPP::CompoundFile document(file.wstring()); } catch (const CFCPP::CFException&) { rejected = true; }
        require(rejected, "Invalid compound signature accepted");
    });
    test(L"windows-read-cf-v3", [](const fs::path& dir) {
        for (const auto size : {63u, 8192u}) {
            const auto file = dir / (std::to_wstring(size) + L".ole");
            const auto data = pattern(size);
            save_cf(file, data, L"数据");
            require(read_windows(file, L"数据") == data, "Windows cannot read generated v3 data");
        }
    });
    test(L"windows-read-cf-v4", [](const fs::path& dir) {
        const auto file = dir / L"version4.ole";
        const auto data = pattern(16384);
        save_cf(file, data, L"Data", CFCPP::Ver_4);
        require(read_cf(file, L"Data") == data && read_windows(file, L"Data") == data, "Version 4 OLE interoperability differs");
    });
    test(L"cf-read-windows", [](const fs::path& dir) {
        const auto file = dir / L"windows.ole";
        const auto data = pattern(10000);
        save_windows(file, data, L"中文数据");
        require(read_cf(file, L"中文数据") == data, "CompoundFileLib cannot read Windows-generated stream");
    });
    test(L"cf-readonly-preservation", [](const fs::path& dir) {
        const auto file = dir / L"readonly.ole";
        save_cf(file, pattern(100));
        const auto before = raw_bytes(file);
        bool rejected = false;
        {
            CFCPP::CompoundFile document(file.wstring(), CFCPP::ReadOnly);
            try { document.Commit(); } catch (const CFCPP::CFInvalidOperation&) { rejected = true; }
            document.Close();
        }
        require(rejected && raw_bytes(file) == before, "Read-only commit altered source or was accepted");
    });
    CoUninitialize();
    std::ofstream output(fs::path(argv[2]), std::ios::binary | std::ios::trunc);
    output << "{\"passed\":" << passed << ",\"failed\":" << failed << "}\n";
    output.close();
    std::cout << passed << " passed, " << failed << " failed\n";
    return failed ? 1 : 0;
}
