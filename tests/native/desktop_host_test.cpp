// Qingliang community, 2026-10-23: native DLL boundary, profile and Unicode filesystem smoke tests.
// This test does not initialize CEF, edit Office documents or stand in for GUI acceptance.
#include <applicationmanager.h>
#include <boost/filesystem.hpp>
#include <windows.h>
#include <cstdio>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

int wmain(int argc, wchar_t** argv) {
    if (argc != 3) return 2;
    const boost::filesystem::path root(argv[1]);
    boost::filesystem::create_directories(root);
    int passed = 0, failed = 0;
    std::vector<std::string> cases;
    auto check = [&](const char* name, bool condition) {
        cases.push_back(name);
        (condition ? passed : failed)++;
        std::cout << (condition ? "PASS " : "FAIL ") << name << "\n";
    };
    check("source_built_host_dll_loaded", GetModuleHandleW(L"ascdocumentscore.dll") != nullptr);
    check("cef_runtime_resolved", GetModuleHandleW(L"libcef.dll") != nullptr);
    check("graphics_and_pdf_dependencies_resolved", GetModuleHandleW(L"graphics.dll") && GetModuleHandleW(L"PdfFile.dll"));
    CAscApplicationSettings settings;
    check("protection_and_signatures_retained", settings.protect_support && settings.sign_support && settings.pass_support);
    check("plugins_and_macros_capability_retained", settings.plugins_support && settings.macroses_support);
    const boost::filesystem::path profile = root / L"配置与文件-U0001f4c4";
    settings.SetUserDataPath(profile.wstring());
    std::wstring normalized = profile.wstring();
    for (wchar_t& ch : normalized) if (ch == L'\\') ch = L'/';
    check("unicode_profile_path_kept", settings.app_data_path == normalized);
    check("cache_and_cookie_routed_to_selected_profile", settings.cache_path == normalized + L"/data/cache" && settings.cookie_path == normalized + L"/data");
    check("recovery_and_user_dictionary_routed_to_profile", settings.recover_path == normalized + L"/data/recover" && settings.user_dictionaries_path == normalized + L"/data/dictionaries");
    check("user_plugins_and_templates_routed_to_profile", settings.user_plugins_path == normalized + L"/data/sdkjs-plugins" && settings.templates_cache_info_path == normalized + L"/data/templates_cache");
    check("125_percent_scale_native_abi", Core_GetMonitorScale(120,120) == 1.25);
    check("150_percent_scale_native_abi", Core_GetMonitorScale(144,144) == 1.5);
    check("mixed_axis_dpi_native_abi", Core_GetMonitorScale(96,144) == 1.25);
    check("docx_save_format_mapping", CAscApplicationManager::GetFileFormatByExtentionForSave(L"报告.docx") == 65);
    check("xlsx_and_pptx_save_format_mapping", CAscApplicationManager::GetFileFormatByExtentionForSave(L"预算.xlsx") == 257 && CAscApplicationManager::GetFileFormatByExtentionForSave(L"演示.pptx") == 129);
    check("pdf_save_format_mapping", CAscApplicationManager::GetFileFormatByExtentionForSave(L"附件.pdf") == 513);
    check("uppercase_office_save_extensions", CAscApplicationManager::GetFileFormatByExtentionForSave(L"报告.DOCX") == 65 && CAscApplicationManager::GetFileFormatByExtentionForSave(L"预算.XLSX") == 257 && CAscApplicationManager::GetFileFormatByExtentionForSave(L"演示.PPTX") == 129);
    check("mixed_case_pdf_save_extension", CAscApplicationManager::GetFileFormatByExtentionForSave(L"附件.PdF") == 513);
    boost::filesystem::create_directories(profile);
    const auto file = profile / L"中文 & [v2].txt";
    FILE* stream = nullptr;
    const std::string text = "Unicode file contents: 中文 café\n";
    const bool opened = _wfopen_s(&stream, file.c_str(), L"wb") == 0 && stream;
    if (opened) { fwrite(text.data(), 1, text.size(), stream); fclose(stream); }
    check("win32_created_unicode_file_seen_by_boost", opened && boost::filesystem::exists(file));
    const auto copied = profile / L"副本.txt";
    if (boost::filesystem::exists(copied)) boost::filesystem::remove(copied);
    boost::filesystem::copy_file(file, copied);
    check("unicode_copy_and_size", boost::filesystem::file_size(copied) == text.size());
    int count = 0;
    for (boost::filesystem::directory_iterator it(profile), end; it != end; ++it) ++count;
    check("unicode_directory_iteration", count == 2);
    boost::system::error_code error;
    boost::filesystem::copy_file(profile/L"absent.txt", profile/L"should-not-exist.txt", error);
    check("missing_source_reports_error_without_creating_output", bool(error) && !boost::filesystem::exists(profile/L"should-not-exist.txt"));
    // Retain only the intentionally generated text fixture after the copy lifecycle check.
    boost::filesystem::remove(copied);
    check("unicode_copy_removal_preserves_original", boost::filesystem::exists(file) && !boost::filesystem::exists(copied));
    std::ofstream output(std::filesystem::path(argv[2]), std::ios::binary | std::ios::trunc);
    output << "{\"passed\":" << passed << ",\"failed\":" << failed << ",\"cases\":[";
    for (size_t i=0; i<cases.size(); ++i) output << (i ? "," : "") << '"' << cases[i] << '"';
    output << "]}\n";
    return failed || !output ? 1 : 0;
}
