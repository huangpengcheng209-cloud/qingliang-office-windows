// Integration acceptance of the source-built ONLYOFFICE kernel and UnicodeConverter.
// AGPLv3 and applicable upstream notices are retained by the repository.
#include <windows.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include "DesktopEditor/common/File.h"
#include "DesktopEditor/common/Path.h"
#include "OfficeUtils/src/OfficeUtils.h"
#include "DesktopEditor/xml/include/xmlutils.h"
#include "UnicodeConverter/UnicodeConverter.h"

namespace fs = std::filesystem;
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }

void write_kernel(const fs::path& path, const std::string& data) {
    NSFile::CFileBinary file;
    require(file.CreateFileW(path.wstring()), "Kernel file creation failed");
    require(file.WriteFile(data.data(), static_cast<DWORD>(data.size())), "Kernel file write failed");
    file.CloseFile();
}
std::string read_kernel(const fs::path& path) {
    BYTE* bytes = nullptr;
    DWORD length = 0;
    require(NSFile::CFileBinary::ReadAllBytes(path.wstring(), &bytes, length), "Kernel binary read failed");
    std::string result(reinterpret_cast<char*>(bytes), length);
    delete[] bytes;
    return result;
}
void clear_owned(const fs::path& path, const fs::path& owner) {
    const auto actual = fs::weakly_canonical(path).wstring();
    const auto parent = fs::weakly_canonical(owner).wstring();
    require(actual == parent || actual.find(parent + L"\\") == 0, "Fixture cleanup escapes owned directory");
    for (const auto& entry : fs::directory_iterator(path)) {
        require(!entry.is_symlink(), "Unexpected fixture link; preserved");
        if (entry.is_directory()) clear_owned(entry.path(), owner);
        else { SetFileAttributesW(entry.path().c_str(), FILE_ATTRIBUTE_NORMAL); require(DeleteFileW(entry.path().c_str()) != FALSE, "Cannot clean owned file"); }
    }
    require(RemoveDirectoryW(path.c_str()) != FALSE, "Cannot clean owned directory");
}
fs::path make_zip(const fs::path& dir, const std::wstring& name, const std::string& contents) {
    const auto source = dir / L"source";
    require(CreateDirectoryW(source.c_str(), nullptr) != FALSE, "Cannot create ZIP fixture source");
    write_kernel(source / name, contents);
    COfficeUtils office;
    const auto archive = dir / L"document.zip";
    require(office.CompressFileOrDirectory(source.wstring(), archive.wstring(), true) == S_OK, "Kernel ZIP creation failed");
    return archive;
}
std::string zip_entry(const fs::path& archive, const std::wstring& name) {
    COfficeUtils office;
    BYTE* bytes = nullptr;
    ULONG length = 0;
    require(office.LoadFileFromArchive(archive.wstring(), name, &bytes, length) == S_OK, "Kernel ZIP entry read failed");
    std::string result(reinterpret_cast<char*>(bytes), length);
    delete[] bytes;
    return result;
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 4) return 2;
    const fs::path external_fixtures = fs::absolute(argv[3]);
    const fs::path root = fs::absolute(argv[1]);
    require(fs::is_directory(root) && fs::is_empty(root), "Fixture root must be empty");
    unsigned passed = 0, failed = 0;
    auto test = [&](const wchar_t* name, auto body) {
        const auto dir = root / name;
        try {
            require(CreateDirectoryW(dir.c_str(), nullptr) != FALSE, "Case directory exists");
            body(dir);
            clear_owned(dir, dir);
            ++passed;
            std::cout << "PASS case " << passed + failed << '\n';
        } catch (const std::exception& error) {
            ++failed;
            std::cerr << "FAIL case " << passed + failed << ": " << error.what() << '\n';
        }
    };
    test(L"loaded-components", [](const fs::path&) {
        wchar_t current[32768];
        require(GetModuleFileNameW(nullptr, current, 32768) != 0, "Cannot locate test executable");
        const auto directory = fs::path(current).parent_path();
        for (const wchar_t* name : {L"kernel.dll", L"UnicodeConverter.dll", L"icuuc74.dll", L"icudt74.dll"}) {
            const HMODULE module = GetModuleHandleW(name);
            require(module != nullptr, "Required source-built module not loaded");
            wchar_t location[32768];
            require(GetModuleFileNameW(module, location, 32768) != 0, "Cannot locate loaded module");
            require(fs::equivalent(directory / name, fs::path(location)), "Loaded a DLL outside the new build output");
        }
    });
    test(L"binary-file", [](const fs::path& dir) {
        const std::string bytes("abc\0xyz\1\2", 9);
        write_kernel(dir / L"binary.bin", bytes);
        require(read_kernel(dir / L"binary.bin") == bytes, "Kernel binary bytes differ");
    });
    test(L"utf8-chinese", [](const fs::path& dir) {
        const auto path = dir / L"中文.txt";
        const std::wstring text = L"中文办公文档";
        require(NSFile::CFileBinary::SaveToFile(path.wstring(), text, true), "Kernel UTF-8 save failed");
        std::wstring result;
        require(NSFile::CFileBinary::ReadAllTextUtf8(path.wstring(), result) && result == text, "Kernel UTF-8 read differs");
    });
    test(L"utf8-emoji", [](const fs::path& dir) {
        const std::wstring text = L"测试 \U0001F600";
        const auto path = dir / L"emoji.txt";
        require(NSFile::CFileBinary::SaveToFile(path.wstring(), text, false), "Emoji save failed");
        std::wstring result;
        require(NSFile::CFileBinary::ReadAllTextUtf8(path.wstring(), result) && result == text, "Emoji roundtrip differs");
    });
    test(L"path-name", [](const fs::path& dir) {
        require(NSSystemPath::GetFileName((dir / L"报告.txt").wstring()) == L"报告.txt", "Kernel path filename differs");
    });
    test(L"deflate-memory", [](const fs::path&) {
        COfficeUtils office;
        const std::string input(8000, 'Z');
        std::vector<BYTE> compressed(9000), restored(9000);
        ULONG compressed_size = static_cast<ULONG>(compressed.size());
        ULONG restored_size = static_cast<ULONG>(restored.size());
        require(office.Compress(compressed.data(), &compressed_size, reinterpret_cast<BYTE*>(const_cast<char*>(input.data())), static_cast<ULONG>(input.size())) == S_OK, "Deflate failed");
        require(office.Uncompress(restored.data(), &restored_size, compressed.data(), compressed_size) == S_OK, "Inflate failed");
        require(std::string(reinterpret_cast<char*>(restored.data()), restored_size) == input, "Deflate roundtrip differs");
    });
    test(L"zip-create", [](const fs::path& dir) {
        const auto archive = make_zip(dir, L"document.xml", "<root/>");
        COfficeUtils office;
        require(office.IsArchive(archive.wstring()) == S_OK, "Created ZIP not recognized");
    });
    test(L"zip-unicode-entry", [](const fs::path& dir) {
        const std::string contents = "Unicode entry content";
        const auto archive = make_zip(dir, L"报告\U0001F600.xml", contents);
        require(zip_entry(archive, L"报告\U0001F600.xml") == contents, "Unicode ZIP entry differs");
    });
    test(L"zip-extract", [](const fs::path& dir) {
        const auto archive = make_zip(dir, L"报告\U0001F600.xml", "<root>office</root>");
        const auto destination = dir / L"unzip";
        require(CreateDirectoryW(destination.c_str(), nullptr) != FALSE, "Cannot create extraction directory");
        COfficeUtils office;
        require(office.ExtractToDirectory(archive.wstring(), destination.wstring(), nullptr, 0) == S_OK, "ZIP extraction failed");
        require(read_kernel(destination / L"报告\U0001F600.xml") == "<root>office</root>", "Extracted content differs");
    });
    test(L"xml-unicode", [](const fs::path&) {
        XmlUtils::CXmlNode node;
        require(node.FromXmlString(L"<root name='办公'>中文</root>"), "XML Unicode parse failed");
        require(node.GetAttribute(L"name") == L"办公" && node.GetText() == L"中文", "XML Unicode values differ");
    });
    test(L"xml-gbk-single-quotes", [](const fs::path& dir) {
        NSUnicodeConverter::CUnicodeConverter converter;
        const auto bytes = converter.fromUnicode(L"<?xml version='1.0' encoding='GBK'?><root>中文</root>", "GBK");
        const auto file = dir / L"gbk.xml";
        write_kernel(file, bytes);
        XmlUtils::CXmlNode node;
        require(node.FromXmlFile(file.wstring()) && node.GetText() == L"中文", "Kernel GBK XML decode differs");
    });
    test(L"xml-gbk-double-quotes", [](const fs::path& dir) {
        NSUnicodeConverter::CUnicodeConverter converter;
        const auto bytes = converter.fromUnicode(L"<?xml version=\"1.0\" encoding=\"GBK\"?><root>中文</root>", "GBK");
        const auto file = dir / L"gbk.xml";
        write_kernel(file, bytes);
        XmlUtils::CXmlNode node;
        require(node.FromXmlFile(file.wstring()) && node.GetText() == L"中文", "Double-quoted GBK XML differs");
    });
    test(L"xml-utf16-file", [](const fs::path& dir) {
        NSUnicodeConverter::CUnicodeConverter converter;
        const auto bytes = std::string("\xFF\xFE", 2) + converter.fromUnicode(L"<?xml version='1.0' encoding='UTF-16'?><root>中文 \U0001F600</root>", "UTF-16LE");
        const auto file = dir / L"utf16.xml";
        write_kernel(file, bytes);
        XmlUtils::CXmlNode node;
        require(node.FromXmlFile(file.wstring()) && node.GetText() == L"中文 \U0001F600", "Kernel UTF-16 XML decode differs");
    });
    test(L"xml-entities", [](const fs::path&) {
        XmlUtils::CXmlNode node;
        require(node.FromXmlString(L"<root>A &amp; B &lt; C</root>") && node.GetText() == L"A & B < C", "XML entity decode differs");
    });
    test(L"missing-file", [](const fs::path& dir) {
        BYTE* bytes = nullptr; DWORD length = 0;
        require(!NSFile::CFileBinary::ReadAllBytes((dir / L"missing.bin").wstring(), &bytes, length), "Missing file reported readable");
        delete[] bytes;
    });
    test(L"invalid-xml", [](const fs::path&) {
        // Reject a parser failure before the first element. Later errors may still return a partial DOM.
        XmlUtils::CXmlNode node;
        require(!node.FromXmlString(L"<root><broken></root>"), "Malformed XML accepted");
    });
    test(L"empty-xml", [](const fs::path&) {
        XmlUtils::CXmlNode node;
        require(!node.FromXmlString(L""), "Empty XML accepted");
    });
    test(L"encoded-file-zip-xml-chain", [](const fs::path& dir) {
        NSUnicodeConverter::CUnicodeConverter converter;
        const auto gbk = converter.fromUnicode(L"中文", "GBK");
        const auto text = converter.toUnicode(gbk, "GBK", true);
        require(text == L"中文", "Chain encoding differs");
        const auto xml = converter.fromUnicode(L"<?xml version='1.0' encoding='UTF-8'?><root>" + text + L" \U0001F600</root>", "UTF-8");
        const auto archive = make_zip(dir, L"content.xml", xml);
        XmlUtils::CXmlNode node;
        require(node.FromXmlStringA(zip_entry(archive, L"content.xml")) && node.GetText() == L"中文 \U0001F600", "Encoding-file-ZIP-XML chain differs");
    });
    test(L"external-utf8-zip", [&](const fs::path& dir) {
        const auto archive = dir / L"external.zip";
        fs::copy_file(external_fixtures / L"utf8-entry.zip", archive);
        require(zip_entry(archive, L"报告\U0001F600.xml") == "external UTF-8 archive", "External UTF-8 ZIP differs");
    });
    test(L"legacy-unflagged-zip", [&](const fs::path& dir) {
        const auto archive = dir / L"legacy.zip";
        fs::copy_file(external_fixtures / L"legacy-entry.zip", archive);
        require(zip_entry(archive, L"legacy.txt") == "legacy entry", "Legacy unflagged ZIP differs");
    });
    test(L"single-file-unicode-zip", [](const fs::path& dir) {
        const auto input = dir / L"报告\U0001F600.xml";
        const auto archive = dir / L"single.zip";
        write_kernel(input, "single Unicode file");
        COfficeUtils office;
        require(office.CompressFileOrDirectory(input.wstring(), archive.wstring()) == S_OK, "Single-file ZIP failed");
        require(zip_entry(archive, input.filename().wstring()) == "single Unicode file", "Single-file ZIP entry differs");
    });
    test(L"memory-unicode-zip", [](const fs::path& dir) {
        struct State { bool supplied = false; unsigned received = 0; bool correct = false; std::string data = "memory Unicode entry"; } state;
        const auto source = [](std::wstring& name, BYTE*& data, long& size, void* context) -> bool {
            auto& value = *static_cast<State*>(context);
            if (value.supplied) return false;
            value.supplied = true;
            name = L"报告\U0001F600.xml";
            data = reinterpret_cast<BYTE*>(value.data.data());
            size = static_cast<long>(value.data.size());
            return true;
        };
        const auto receive = [](const std::wstring& name, BYTE* data, const long& size, void* context) {
            auto& value = *static_cast<State*>(context);
            ++value.received;
            value.correct = name == L"报告\U0001F600.xml" && std::string(reinterpret_cast<char*>(data), size) == value.data;
        };
        const auto archive = dir / L"memory.zip";
        COfficeUtils office;
        bool result = false;
        require(office.CompressFilesFromMemory(archive.wstring(), source, &state, -1, &result) == S_OK && result, "Memory ZIP write failed");
        require(zip_entry(archive, L"报告\U0001F600.xml") == state.data, "Memory ZIP entry differs");
        result = false;
        require(office.ExtractFilesToMemory(archive.wstring(), receive, &state, &result) == S_OK && result, "Memory ZIP read failed");
        require(state.received == 1 && state.correct, "Memory ZIP callback differs");
    });
    std::ofstream output(fs::path(argv[2]), std::ios::binary | std::ios::trunc);
    output << "{\"passed\":" << passed << ",\"failed\":" << failed << "}\n";
    output.close();
    std::cout << passed << " passed, " << failed << " failed\n";
    return failed ? 1 : 0;
}
