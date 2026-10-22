// SPDX-License-Identifier: AGPL-3.0-only
// Preview adapter for the pinned ONLYOFFICE CTxtXmlFile implementation.
#include <TxtFile/Source/TxtXmlFile.h>
#include <filesystem>
#include <iostream>
#include <string>

int wmain(int argc, wchar_t** argv)
{
    if (argc != 4) return 2;
    const std::wstring mode(argv[1]);
    if (mode != L"txt-to-docx" && mode != L"docx-to-txt") return 2;
    try {
        CTxtXmlFile converter;
        const std::wstring options = L"<Options><fileOptions codePage=\"46\"/></Options>";
        if (mode == L"txt-to-docx") {
            if (!std::filesystem::is_regular_file(argv[2]) || !std::filesystem::is_directory(argv[3])) return 3;
            return converter.txt_LoadFromFile(argv[2], argv[3], options) == 0 ? 0 : 4;
        }
        if (!std::filesystem::is_regular_file(std::filesystem::path(argv[2]) / L"word/document.xml")) return 3;
        return converter.txt_SaveToFile(argv[3], argv[2], options) == 0 ? 0 : 4;
    } catch (...) {
        std::cerr << "Native text conversion failed\n";
        return 5;
    }
}
