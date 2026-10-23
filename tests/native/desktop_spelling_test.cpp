// Authored miniature dictionaries exercise the real exported desktop Hunspell DLL.
#include <hunspell/hunspell.h>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 3) return 2;
    const std::string root = std::string(argv[1]) + "/";
    auto write = [&](const char* name, const std::string& bytes) {
        std::ofstream file(root + name, std::ios::binary | std::ios::trunc);
        file << bytes;
        if (!file) throw std::runtime_error("Cannot write dictionary fixture");
    };
    write("test.aff", "SET UTF-8\nLANG en_US\nTRY abcdefghijklmnopqrstuvwxyz\nFORBIDDENWORD X\n"
                      "SFX S Y 1\nSFX S 0 s .\nPFX U Y 1\nPFX U 0 un .\n");
    write("test.dic", u8"7\ncat/S\nplay/US\nhello\ncafé\n中文\nblocked/X\nworld\n");
    write("extra.dic", "1\nextraordinary\n");
    write("latin.aff", "SET ISO8859-1\n");
    write("latin.dic", std::string("1\ncaf") + char(0xe9) + "\n");
    auto create = [&]() { return Hunspell_create((root+"test.aff").c_str(), (root+"test.dic").c_str()); };
    Hunhandle* h = create();
    if (!h) return 3;
    int passed = 0, failed = 0;
    std::vector<std::string> names;
    auto check = [&](const char* name, bool ok) {
        names.push_back(name);
        (ok ? passed : failed)++;
        std::cout << (ok ? "PASS " : "FAIL ") << name << "\n";
    };
    auto spell = [&](const char* word) { return Hunspell_spell(h, word) != 0; };
    check("utf8_dictionary_encoding", std::string(Hunspell_get_dic_encoding(h)) == "UTF-8");
    check("dictionary_word", spell("cat"));
    check("misspelling_rejected", !spell("zzzzq"));
    check("suffix_plural", spell("cats"));
    check("prefix", spell("unplay"));
    check("cross_product_affixes", spell("unplays"));
    check("utf8_accent", spell(u8"café"));
    check("utf8_cjk_word", spell(u8"中文"));
    check("utf8_uppercase", spell(u8"CAFÉ"));
    check("forbidden_dictionary_word", !spell("blocked"));
    char** list = nullptr;
    int count = Hunspell_suggest(h, &list, "helo");
    bool found = false;
    for (int i=0; i<count; ++i) found |= std::string(list[i]) == "hello";
    check("suggestion_contents_and_release", found);
    Hunspell_free_list(h, &list, count);
    count = Hunspell_stem(h, &list, "cats");
    found = false;
    for (int i=0; i<count; ++i) found |= std::string(list[i]) == "cat";
    check("affixed_word_stemming", found);
    Hunspell_free_list(h, &list, count);
    check("runtime_word_add", Hunspell_add(h, "qingliang") == 0 && spell("qingliang"));
    check("runtime_affix_add", Hunspell_add_with_affix(h, "dog", "cat") == 0 && spell("dogs"));
    check("runtime_word_remove", Hunspell_remove(h, "qingliang") == 0 && !spell("qingliang"));
    Hunspell_add_dic(h, (root+"extra.dic").c_str());
    check("additional_dictionary", spell("extraordinary"));
    Hunhandle* other = create();
    check("instance_dictionary_isolation", other && !Hunspell_spell(other, "dog") && spell("dogs"));
    Hunspell_destroy(other);
    check("one_engine_survives_other_destroy", spell(u8"CAFÉ"));
    bool lifecycle = true;
    for (int i=0; i<64; ++i) {
        other = create();
        lifecycle &= other && Hunspell_spell(other, u8"CAFÉ") != 0;
        Hunspell_destroy(other);
    }
    check("repeated_engine_lifecycle_utf8", lifecycle && spell(u8"CAFÉ"));
    other = Hunspell_create((root+"latin.aff").c_str(), (root+"latin.dic").c_str());
    const std::string latin = std::string("caf") + char(0xe9);
    check("legacy_single_byte_dictionary", other && Hunspell_spell(other, latin.c_str()) != 0);
    check("dictionary_encoding_isolation", other && !Hunspell_spell(other, u8"café") && spell(u8"café"));
    Hunspell_destroy(other);
    Hunspell_destroy(h);
    h = create();
    check("runtime_changes_do_not_modify_dictionary", h && !Hunspell_spell(h, "dog") && Hunspell_spell(h, "cat"));
    Hunspell_destroy(h);
    std::ofstream result(argv[2], std::ios::binary | std::ios::trunc);
    result << "{\"passed\":" << passed << ",\"failed\":" << failed << ",\"cases\":[";
    for (size_t i=0; i<names.size(); ++i) result << (i ? "," : "") << '"' << names[i] << '"';
    result << "]}\n";
    return failed || !result ? 1 : 0;
}
