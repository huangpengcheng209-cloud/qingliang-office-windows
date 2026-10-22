// Native acceptance of pinned ONLYOFFICE UnicodeConverter with source-built ICU.
// Distributed under the repository AGPLv3 terms and applicable upstream notices.
#include "UnicodeConverter.h"
#include <boost/version.hpp>
#include <boost/algorithm/string.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

using NSUnicodeConverter::CUnicodeConverter;
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }

void roundtrip(const std::wstring& text, const char* encoding, const std::string* expected = nullptr) {
    CUnicodeConverter converter;
    const auto bytes = converter.fromUnicode(text, encoding);
    require(!bytes.empty() || text.empty(), "Unexpected empty encoded data");
    if (expected) require(bytes == *expected, "Known encoded bytes differ");
    require(converter.toUnicode(bytes, encoding, true) == text, "Encoding roundtrip differs");
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 2) return 2;
    unsigned passed = 0, failed = 0;
    auto test = [&](const char* name, auto body) {
        try { body(); ++passed; std::cout << "PASS " << name << '\n'; }
        catch (const std::exception& error) { ++failed; std::cerr << "FAIL " << name << ": " << error.what() << '\n'; }
    };
    test("boost-1.72-headers", [] {
        static_assert(BOOST_VERSION == 107200, "Unexpected Boost version");
        std::string text = "office";
        boost::to_upper(text);
        require(text == "OFFICE", "Boost algorithm failed");
    });
    test("utf8-ascii", [] { const std::string expected = "Office 123"; roundtrip(L"Office 123", "UTF-8", &expected); });
    test("utf8-chinese", [] { const std::string expected = "\xE4\xB8\xAD\xE6\x96\x87"; roundtrip(L"中文", "UTF-8", &expected); });
    test("utf8-emoji", [] { roundtrip(L"文档 \U0001F600", "UTF-8"); });
    test("gbk", [] { const std::string expected = "\xD6\xD0\xCE\xC4"; roundtrip(L"中文", "GBK", &expected); });
    test("shift-jis", [] { roundtrip(L"日本語", "Shift_JIS"); });
    test("windows-1251", [] { roundtrip(L"Привет", "windows-1251"); });
    test("windows-1252", [] { const std::string expected = "\x80 caf\xE9"; roundtrip(L"€ café", "windows-1252", &expected); });
    test("utf16-le", [] { roundtrip(L"中 \U0001F600", "UTF-16LE"); });
    test("utf16-be", [] { roundtrip(L"中 \U0001F600", "UTF-16BE"); });
    test("utf32-le", [] { roundtrip(L"中 \U0001F600", "UTF-32LE"); });
    test("utf32-be", [] { roundtrip(L"中 \U0001F600", "UTF-32BE"); });
    test("empty-string", [] { roundtrip(L"", "UTF-8"); });
    test("saslprep-data", [] {
        CUnicodeConverter converter;
        require(converter.SASLprepToUtf8(L"I\u00ADX") == "IX", "ICU SASLprep data not available or normalization differs");
    });
    std::ofstream output(std::filesystem::path(argv[1]), std::ios::binary | std::ios::trunc);
    output << "{\"passed\":" << passed << ",\"failed\":" << failed << "}\n";
    output.close();
    std::cout << passed << " passed, " << failed << " failed\n";
    return failed ? 1 : 0;
}
