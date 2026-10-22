// Generated-data acceptance for source-built kernel_network and CryptoPPLib.
// Part of the AGPLv3 community project; upstream notices remain in their sources.
#include <windows.h>
#include <bcrypt.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "Common/3dParty/cryptopp/sha.h"
#include "Common/3dParty/cryptopp/hmac.h"
#include "Common/3dParty/cryptopp/pwdbased.h"
#include "Common/3dParty/cryptopp/aes.h"
#include "Common/3dParty/cryptopp/modes.h"
#include "OfficeCryptReader/source/CryptTransform.h"
#include "Common/Network/FileTransporter/include/FileTransporter.h"

namespace fs = std::filesystem;
using Bytes = std::vector<unsigned char>;
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
struct Algorithm {
    BCRYPT_ALG_HANDLE handle = nullptr;
    Algorithm(LPCWSTR name, ULONG flags = 0) { require(BCryptOpenAlgorithmProvider(&handle, name, nullptr, flags) >= 0, "CNG algorithm open failed"); }
    ~Algorithm() { if (handle) BCryptCloseAlgorithmProvider(handle, 0); }
};
Bytes cng_hash(LPCWSTR name, const Bytes& data, size_t size, const Bytes& key = {}) {
    Algorithm algorithm(name, key.empty() ? 0 : BCRYPT_ALG_HANDLE_HMAC_FLAG);
    Bytes result(size);
    require(BCryptHash(algorithm.handle, const_cast<PUCHAR>(key.data()), static_cast<ULONG>(key.size()),
                       const_cast<PUCHAR>(data.data()), static_cast<ULONG>(data.size()), result.data(), static_cast<ULONG>(size)) >= 0, "CNG hash failed");
    return result;
}
template<class Hash> Bytes crypto_hash(const Bytes& data) {
    Hash algorithm;
    Bytes result(algorithm.DigestSize());
    algorithm.CalculateDigest(result.data(), data.data(), data.size());
    return result;
}
Bytes cng_aes(const Bytes& key_bytes, const Bytes& input, bool cbc) {
    Algorithm algorithm(BCRYPT_AES_ALGORITHM);
    LPCWSTR mode = cbc ? BCRYPT_CHAIN_MODE_CBC : BCRYPT_CHAIN_MODE_ECB;
    require(BCryptSetProperty(algorithm.handle, BCRYPT_CHAINING_MODE, reinterpret_cast<PUCHAR>(const_cast<LPWSTR>(mode)),
                             static_cast<ULONG>((wcslen(mode) + 1) * sizeof(wchar_t)), 0) >= 0, "CNG mode failed");
    BCRYPT_KEY_HANDLE key = nullptr;
    require(BCryptGenerateSymmetricKey(algorithm.handle, &key, nullptr, 0, const_cast<PUCHAR>(key_bytes.data()), static_cast<ULONG>(key_bytes.size()), 0) >= 0, "CNG key failed");
    Bytes result(input.size()), iv(16, 7);
    ULONG count = 0;
    const auto status = BCryptEncrypt(key, const_cast<PUCHAR>(input.data()), static_cast<ULONG>(input.size()), nullptr,
                                      cbc ? iv.data() : nullptr, cbc ? 16 : 0, result.data(), static_cast<ULONG>(result.size()), &count, 0);
    BCryptDestroyKey(key);
    require(status >= 0 && count == result.size(), "CNG AES failed");
    return result;
}
void clear_owned(const fs::path& path, const fs::path& owner) {
    const auto actual = fs::weakly_canonical(path).wstring(), parent = fs::weakly_canonical(owner).wstring();
    require(actual == parent || actual.find(parent + L"\\") == 0, "Cleanup escapes owned fixture directory");
    for (const auto& entry : fs::directory_iterator(path)) {
        require(!entry.is_symlink(), "Unexpected fixture link");
        if (entry.is_directory()) clear_owned(entry.path(), owner);
        else require(DeleteFileW(entry.path().c_str()) != FALSE, "Cannot clean owned file");
    }
    require(RemoveDirectoryW(path.c_str()) != FALSE, "Cannot clean owned directory");
}
Bytes read_bytes(const fs::path& file) {
    std::ifstream input(file, std::ios::binary);
    require(input.good(), "Downloaded file missing");
    return Bytes(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
}
struct OfficePayload {
    CRYPT::_ecmaCryptData config;
    Bytes original, encrypted;
    OfficePayload() : original(9001) {
        for (size_t i = 0; i < original.size(); ++i) original[i] = static_cast<unsigned char>(i % 251);
        CRYPT::ECMAEncryptor encoder;
        encoder.SetCryptData(config);
        encoder.SetPassword(L"public-fixture-pass");
        unsigned char* output = nullptr;
        const auto size = encoder.Encrypt(original.data(), static_cast<int>(original.size()), output);
        std::unique_ptr<unsigned char[]> owned(output);
        require(size > 8 && output, "Office wrapper encryption failed");
        encrypted.assign(output, output + size);
        encoder.UpdateDataIntegrity(encrypted.data(), static_cast<int>(encrypted.size()));
        encoder.GetCryptData(config);
    }
};

int wmain(int argc, wchar_t** argv) {
    if (argc != 4) return 2;
    const fs::path root = fs::absolute(argv[1]);
    const std::wstring base = argv[3];
    require(base.find(L"http://127.0.0.1:") == 0, "Fixture server must use loopback");
    require(fs::is_directory(root) && fs::is_empty(root), "Fixture root must be empty");
    SetEnvironmentVariableA("allowNetworkRequest", "true");
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
    const Bytes input = {'a', 'b', 'c'};
    test(L"loaded-modules", [](const fs::path&) {
        wchar_t executable[32768];
        require(GetModuleFileNameW(nullptr, executable, 32768) != 0, "Cannot locate executable");
        for (const wchar_t* name : {L"kernel.dll", L"kernel_network.dll"}) {
            const auto module = GetModuleHandleW(name);
            wchar_t location[32768];
            require(module && GetModuleFileNameW(module, location, 32768) != 0 &&
                    fs::equivalent(fs::path(executable).parent_path() / name, fs::path(location)), "Unexpected loaded DLL path");
        }
    });
    test(L"sha256-cng", [&](const fs::path&) { require(crypto_hash<CryptoPP::SHA256>(input) == cng_hash(BCRYPT_SHA256_ALGORITHM, input, 32), "SHA256 differs from Windows CNG"); });
    test(L"sha1-cng", [&](const fs::path&) { require(crypto_hash<CryptoPP::SHA1>(input) == cng_hash(BCRYPT_SHA1_ALGORITHM, input, 20), "SHA1 differs from Windows CNG"); });
    test(L"sha512-cng", [&](const fs::path&) { require(crypto_hash<CryptoPP::SHA512>(input) == cng_hash(BCRYPT_SHA512_ALGORITHM, input, 64), "SHA512 differs from Windows CNG"); });
    test(L"hmac-cng", [&](const fs::path&) {
        const Bytes key(20, 11);
        CryptoPP::HMAC<CryptoPP::SHA256> hash(key.data(), key.size());
        Bytes result(hash.DigestSize()); hash.CalculateDigest(result.data(), input.data(), input.size());
        require(result == cng_hash(BCRYPT_SHA256_ALGORITHM, input, 32, key), "HMAC differs from Windows CNG");
    });
    test(L"pbkdf2-cng", [&](const fs::path&) {
        const Bytes salt = {'s','a','l','t'};
        Bytes result(32), expected(32);
        CryptoPP::PKCS5_PBKDF2_HMAC<CryptoPP::SHA256> derive;
        derive.DeriveKey(result.data(), result.size(), 0, input.data(), input.size(), salt.data(), salt.size(), 4096);
        Algorithm algorithm(BCRYPT_SHA256_ALGORITHM, BCRYPT_ALG_HANDLE_HMAC_FLAG);
        require(BCryptDeriveKeyPBKDF2(algorithm.handle, const_cast<PUCHAR>(input.data()), static_cast<ULONG>(input.size()),
                                      const_cast<PUCHAR>(salt.data()), static_cast<ULONG>(salt.size()), 4096, expected.data(), 32, 0) >= 0 && result == expected, "PBKDF2 differs from Windows CNG");
    });
    test(L"aes128-cng", [](const fs::path&) {
        const Bytes key(16, 3), plain(32, 9); Bytes output(32);
        CryptoPP::ECB_Mode<CryptoPP::AES>::Encryption aes(key.data(), key.size());
        aes.ProcessData(output.data(), plain.data(), plain.size());
        require(output == cng_aes(key, plain, false), "AES128 differs from Windows CNG");
    });
    test(L"aes256-cng", [](const fs::path&) {
        const Bytes key(32, 5), plain(64, 9), iv(16, 7); Bytes output(64), restored(64);
        CryptoPP::CBC_Mode<CryptoPP::AES>::Encryption aes(key.data(), key.size(), iv.data());
        aes.ProcessData(output.data(), plain.data(), plain.size());
        require(output == cng_aes(key, plain, true), "AES256 differs from Windows CNG");
        CryptoPP::CBC_Mode<CryptoPP::AES>::Decryption decoder(key.data(), key.size(), iv.data());
        decoder.ProcessData(restored.data(), output.data(), output.size());
        require(restored == plain, "AES256 decrypt differs");
    });
    test(L"aes-invalid-key", [](const fs::path&) {
        bool rejected = false;
        try { const Bytes key(7); CryptoPP::ECB_Mode<CryptoPP::AES>::Encryption aes(key.data(), key.size()); }
        catch (const CryptoPP::Exception&) { rejected = true; }
        require(rejected, "Invalid AES key accepted");
    });
    std::unique_ptr<OfficePayload> office;
    auto payload = [&]() -> OfficePayload& { if (!office) office.reset(new OfficePayload()); return *office; };
    test(L"office-payload-roundtrip", [&](const fs::path&) {
        auto& value = payload();
        CRYPT::ECMADecryptor decoder; decoder.SetCryptData(value.config);
        require(decoder.SetPassword(L"public-fixture-pass"), "Office verifier rejected fixture password");
        unsigned char* output = nullptr;
        decoder.Decrypt(value.encrypted.data() + 8, static_cast<int>(value.encrypted.size() - 8), output, 0);
        std::unique_ptr<unsigned char[]> owned(output);
        require(output && Bytes(output, output + value.original.size()) == value.original &&
                decoder.CheckDataIntegrity(value.encrypted.data(), static_cast<int>(value.encrypted.size())), "Office payload or integrity differs");
    });
    test(L"office-wrong-password", [&](const fs::path&) {
        auto& value = payload(); CRYPT::ECMADecryptor decoder; decoder.SetCryptData(value.config);
        require(!decoder.SetPassword(L"wrong-public-fixture-pass"), "Wrong Office password accepted");
    });
    test(L"office-integrity-tamper", [&](const fs::path&) {
        auto& value = payload(); CRYPT::ECMADecryptor decoder; decoder.SetCryptData(value.config);
        require(decoder.SetPassword(L"public-fixture-pass"), "Office verifier failed");
        auto altered = value.encrypted; altered[altered.size() - 1] ^= 1;
        require(!decoder.CheckDataIntegrity(altered.data(), static_cast<int>(altered.size())), "Tampered Office payload accepted");
    });
    auto download = [&](const fs::path& file, const std::wstring& path) {
        NSNetwork::NSFileTransport::CFileDownloader client(base + path, false);
        client.SetFilePath(file.wstring());
        return client.DownloadSync() && client.IsFileDownloaded();
    };
    test(L"download-text", [&](const fs::path& dir) {
        const auto file = dir / L"text.bin"; require(download(file, L"/payload"), "HTTP download failed");
        const auto data = read_bytes(file); require(std::string(data.begin(), data.end()) == "loopback office", "HTTP text differs");
    });
    test(L"download-binary-hash", [&](const fs::path& dir) {
        const auto file = dir / L"binary.bin"; require(download(file, L"/binary"), "Binary download failed");
        const auto data = read_bytes(file); require(data.size() == 256, "Binary size differs");
        for (size_t i = 0; i < data.size(); ++i) require(data[i] == i, "Binary bytes differ");
        require(crypto_hash<CryptoPP::SHA256>(data) == cng_hash(BCRYPT_SHA256_ALGORITHM, data, 32), "Downloaded hash differs");
    });
    test(L"download-large", [&](const fs::path& dir) {
        const auto file = dir / L"large.bin"; require(download(file, L"/large"), "Large download failed");
        const auto data = read_bytes(file); require(data.size() == 600000, "Large size differs");
        for (size_t i = 0; i < data.size(); ++i) require(data[i] == i % 251, "Large bytes differ");
    });
    test(L"download-redirect", [&](const fs::path& dir) {
        const auto file = dir / L"redirect.bin"; require(download(file, L"/redirect"), "Redirect download failed");
        const auto data = read_bytes(file); require(std::string(data.begin(), data.end()) == "loopback office", "Redirect bytes differ");
    });
    test(L"download-unicode-path", [&](const fs::path& dir) {
        const auto file = dir / L"报告\U0001F600.bin"; require(download(file, L"/payload"), "Unicode path download failed");
        const auto data = read_bytes(file); require(std::string(data.begin(), data.end()) == "loopback office", "Unicode path bytes differ");
    });
    test(L"download-empty", [&](const fs::path& dir) {
        const auto file = dir / L"empty.bin"; require(download(file, L"/empty") && read_bytes(file).empty(), "Empty download differs");
    });
    test(L"download-missing", [&](const fs::path& dir) {
        const auto file = dir / L"missing.bin"; require(!download(file, L"/missing") && !fs::exists(file), "Missing URL reported downloaded");
    });
    test(L"unsupported-upload", [&](const fs::path& dir) {
        const Bytes data = {1, 2, 3};
        NSNetwork::NSFileTransport::CFileUploader memory(base + L"/upload", data.data(), static_cast<int>(data.size()));
        require(!memory.UploadSync(), "Unimplemented memory upload reported success");
        const auto file = dir / L"upload.bin"; { std::ofstream output(file, std::ios::binary); output << "fixture"; }
        NSNetwork::NSFileTransport::CFileUploader disk(base + L"/upload", file.wstring());
        require(!disk.UploadSync() && fs::exists(file), "Unimplemented file upload reported success or removed input");
    });
    std::ofstream result(fs::path(argv[2]), std::ios::binary | std::ios::trunc);
    result << "{\"passed\":" << passed << ",\"failed\":" << failed << "}\n";
    std::cout << passed << " passed, " << failed << " failed\n";
    return failed ? 1 : 0;
}
