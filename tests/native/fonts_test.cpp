// Qingliang community font-library integration tests, 2026-10-22.
#include <hb.h>
#include <hb-ft.h>
#include <hb-ot.h>
#include <ft2build.h>
#include FT_FREETYPE_H
#include <brotli/decode.h>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <string>
#include <vector>

static int passed = 0, failed = 0;
static void check(const char* name, bool ok) {
    std::cerr << (ok ? "PASS " : "FAIL ") << name << '\n';
    if (ok) ++passed; else ++failed;
}
static std::vector<unsigned char> read(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("Cannot read fixture: " + path);
    return {std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>()};
}
static hb_buffer_t* shape(hb_font_t* font, const char* text, bool liga = true) {
    hb_buffer_t* b = hb_buffer_create();
    hb_buffer_add_utf8(b, text, -1, 0, -1);
    hb_buffer_guess_segment_properties(b);
    hb_feature_t feature;
    hb_feature_from_string("liga=0", -1, &feature);
    hb_shape(font, b, liga ? nullptr : &feature, liga ? 0 : 1);
    return b;
}
static bool raster(FT_Face face, hb_font_t* font, const char* text, int baseline,
                   std::vector<unsigned char>& canvas) {
    constexpr int width = 1000, height = 220;
    hb_buffer_t* b = shape(font, text);
    unsigned count = 0;
    auto info = hb_buffer_get_glyph_infos(b, &count);
    auto pos = hb_buffer_get_glyph_positions(b, nullptr);
    int pen = 25 * 64;
    bool ok = count > 0;
    for (unsigned i = 0; i < count; ++i) {
        if (!info[i].codepoint || FT_Load_Glyph(face, info[i].codepoint, FT_LOAD_DEFAULT) ||
            FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL)) { ok = false; break; }
        auto slot = face->glyph;
        auto& bitmap = slot->bitmap;
        if (bitmap.pixel_mode != FT_PIXEL_MODE_GRAY && bitmap.width) { ok = false; break; }
        const int x = (pen + pos[i].x_offset) / 64 + slot->bitmap_left;
        const int y = baseline - pos[i].y_offset / 64 - slot->bitmap_top;
        for (unsigned r = 0; r < bitmap.rows; ++r) {
            for (unsigned c = 0; c < bitmap.width; ++c) {
                int xx = x + c, yy = y + r;
                if (xx >= 0 && xx < width && yy >= 0 && yy < height) {
                    auto value = bitmap.buffer[r * bitmap.pitch + c];
                    auto& dest = canvas[yy * width + xx];
                    dest = std::min(dest, static_cast<unsigned char>(255 - value));
                }
            }
        }
        pen += pos[i].x_advance;
    }
    hb_buffer_destroy(b);
    return ok;
}
static int self(const char* latinPath, const char* arabicPath, const char* brotliPath, const char* image) {
    FT_Library library = nullptr;
    if (FT_Init_FreeType(&library)) throw std::runtime_error("FreeType initialization failed");
    int major, minor, patch;
    FT_Library_Version(library, &major, &minor, &patch);
    check("FreeType pinned version", major == 2 && minor == 10 && patch == 4);
    FT_Face latin = nullptr, arabic = nullptr;
    if (FT_New_Face(library, latinPath, 0, &latin) || FT_New_Face(library, arabicPath, 0, &arabic))
        throw std::runtime_error("Cannot load pinned font fixtures");
    check("Unicode nominal and missing glyph lookup", FT_Get_Char_Index(latin, 'A') &&
          FT_Get_Char_Index(latin, ' ') && !FT_Get_Char_Index(latin, 0x10ffff));
    auto bytes = read(latinPath);
    FT_Face memory = nullptr;
    check("Memory-backed font", !FT_New_Memory_Face(library, bytes.data(), static_cast<FT_Long>(bytes.size()), 0, &memory)
          && FT_Get_Char_Index(memory, 'A') == FT_Get_Char_Index(latin, 'A'));
    if (memory) FT_Done_Face(memory);
    const unsigned char invalid[] = {0, 1, 2, 3, 4, 5};
    memory = nullptr;
    check("Malformed font rejected", FT_New_Memory_Face(library, invalid, sizeof(invalid), 0, &memory) != 0);
    if (memory) FT_Done_Face(memory);
    FT_Set_Pixel_Sizes(latin, 0, 48);
    FT_Set_Pixel_Sizes(arabic, 0, 48);
    auto font = hb_ft_font_create_referenced(latin);
    auto afont = hb_ft_font_create_referenced(arabic);
    hb_codepoint_t glyph = 0;
    check("HarfBuzz FreeType bridge", hb_font_get_nominal_glyph(font, 'A', &glyph) &&
          glyph == FT_Get_Char_Index(latin, 'A'));
    auto b = shape(font, "office");
    const auto ligatureCount = hb_buffer_get_length(b);
    check("Latin ligature enabled", ligatureCount > 0 && ligatureCount < 6);
    hb_buffer_destroy(b);
    b = shape(font, "office", false);
    check("Latin ligature disabled", hb_buffer_get_length(b) == 6);
    hb_buffer_destroy(b);
    b = shape(afont, u8"سلام");
    unsigned count = 0;
    auto infos = hb_buffer_get_glyph_infos(b, &count);
    bool rtl = hb_buffer_get_direction(b) == HB_DIRECTION_RTL && count > 0;
    bool contextual = false;
    const FT_ULong arabicCharacters[] = {0x633, 0x644, 0x627, 0x645};
    for (unsigned i = 0; i < count; ++i) {
        rtl = rtl && infos[i].codepoint && (!i || infos[i-1].cluster >= infos[i].cluster);
        if (infos[i].cluster < 8 && !(infos[i].cluster % 2))
            contextual = contextual || infos[i].codepoint != FT_Get_Char_Index(arabic, arabicCharacters[infos[i].cluster/2]);
    }
    std::cerr << "Arabic glyph count: " << count << ", contextual glyph substitution: " << contextual << '\n';
    check("Arabic contextual joining and RTL clusters", rtl && contextual);
    hb_buffer_destroy(b);
    std::vector<unsigned char> canvas(1000 * 220, 255);
    const bool rendered = raster(latin, font, "Office ffi - Qingliang", 75, canvas) &&
                          raster(arabic, afont, u8"السلام عليكم", 165, canvas);
    check("Shaped Latin and Arabic raster output", rendered &&
          std::count_if(canvas.begin(), canvas.end(), [](unsigned char c){ return c < 250; }) > 1000);
    std::ofstream output(image, std::ios::binary);
    output << "P5\n1000 220\n255\n";
    output.write(reinterpret_cast<const char*>(canvas.data()), canvas.size());
    if (!output) throw std::runtime_error("Cannot write raster evidence");
    std::vector<unsigned char> compressed;
    for (const char* name : {"empty", "ukkonooa"}) {
        const std::string path = std::string(brotliPath) + "/" + name;
        auto expected = read(path);
        compressed = read(path + ".compressed");
        std::vector<unsigned char> decoded(std::max<size_t>(1, expected.size()));
        size_t size = decoded.size();
        const auto status = BrotliDecoderDecompress(compressed.size(), compressed.data(), &size, decoded.data());
        decoded.resize(size);
        check(name, status == BROTLI_DECODER_RESULT_SUCCESS && decoded == expected);
    }
    std::vector<unsigned char> decoded(100000);
    size_t size = decoded.size();
    check("Truncated Brotli stream rejected", compressed.size() > 1 &&
          BrotliDecoderDecompress(compressed.size()/2, compressed.data(), &size, decoded.data()) != BROTLI_DECODER_RESULT_SUCCESS);
    hb_font_destroy(afont); hb_font_destroy(font);
    FT_Done_Face(arabic); FT_Done_Face(latin); FT_Done_FreeType(library);
    std::cout << "{\"passed\":" << passed << ",\"failed\":" << failed << "}\n";
    return failed ? 1 : 0;
}
static int golden(const char* path, const char* unicode) {
    auto blob = hb_blob_create_from_file_or_fail(path);
    if (!blob) throw std::runtime_error("Cannot load shaping font");
    auto face = hb_face_create(blob, 0);
    auto font = hb_font_create(face);
    hb_ot_font_set_funcs(font);
    const int upem = hb_face_get_upem(face);
    hb_font_set_scale(font, upem, upem);
    auto buffer = hb_buffer_create();
    hb_buffer_set_content_type(buffer, HB_BUFFER_CONTENT_TYPE_UNICODE);
    std::stringstream text(unicode);
    std::string token;
    unsigned cluster = 0;
    while (std::getline(text, token, ',')) {
        if (token.substr(0, 2) == "U+") token = token.substr(2);
        hb_buffer_add(buffer, std::stoul(token, nullptr, 16), cluster++);
    }
    hb_buffer_guess_segment_properties(buffer);
    hb_shape(font, buffer, nullptr, 0);
    char serialized[32768]; unsigned consumed = 0;
    hb_buffer_serialize_glyphs(buffer, 0, hb_buffer_get_length(buffer), serialized, sizeof(serialized),
                              &consumed, font, HB_BUFFER_SERIALIZE_FORMAT_TEXT, HB_BUFFER_SERIALIZE_FLAG_DEFAULT);
    std::cout.write(serialized, consumed); std::cout << '\n';
    hb_buffer_destroy(buffer); hb_font_destroy(font); hb_face_destroy(face); hb_blob_destroy(blob);
    return 0;
}
int main(int argc, char** argv) {
    try {
        if (argc == 4 && std::string(argv[1]) == "golden") return golden(argv[2], argv[3]);
        if (argc == 6 && std::string(argv[1]) == "self") return self(argv[2],argv[3],argv[4],argv[5]);
        throw std::runtime_error("Unexpected font test arguments");
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 2; }
}
