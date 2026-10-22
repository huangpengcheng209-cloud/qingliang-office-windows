"""Fetch versioned dependency assets to D: and retain download provenance."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

import requests

TASK = Path(r"D:\CodexWorkspaces\2026-10-13\office-windows")
STAGE = Path(r"D:\CodexCache\office-windows")
CORE = STAGE / "upstream" / "DesktopEditors" / "core"


def download(url, path, algorithm, expected):
    if not path.exists():
        response = requests.get(url, timeout=(30, 120), stream=True)
        response.raise_for_status()
        partial = path.with_suffix(path.suffix + ".part")
        with partial.open("wb") as stream:
            for chunk in response.iter_content(1024 * 1024):
                stream.write(chunk)
        partial.replace(path)
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, algorithm).hexdigest()
    if actual != expected:
        raise RuntimeError("Dependency asset checksum mismatch: " + str(path))
    return {"url": url, "path": str(path), "bytes": path.stat().st_size, algorithm: actual, "upstream_checksum_matched": True}


def main():
    downloads = STAGE / "downloads"
    records = []
    boost_url = "https://archives.boost.io/release/1.72.0/source/boost_1_72_0.7z"
    response = requests.get(boost_url + ".json", timeout=40)
    response.raise_for_status()
    boost_metadata = response.json()
    boost_archive = downloads / "boost_1_72_0.7z"
    print("Fetching checksum-verified Boost 1.72.0 source", flush=True)
    records.append(download(boost_url, boost_archive, "sha256", boost_metadata["sha256"]))
    boost_root = CORE / "Common/3dParty/boost"
    if not (boost_root / "boost_1_72_0/boost/version.hpp").exists():
        with (STAGE / "logs" / "boost-extraction.log").open("wb") as log:
            subprocess.run(["7z", "x", "-y", "-o" + str(boost_root), str(boost_archive)], stdout=log, stderr=log, check=True)
    print("Boost 1.72.0 extracted", flush=True)
    icu_url = "https://github.com/unicode-org/icu/releases/download/release-74-2/icu4c-74_2-src.zip"
    checksums = requests.get("https://github.com/unicode-org/icu/releases/download/release-74-2/SHASUM512.txt", timeout=40)
    checksums.raise_for_status()
    expected = next(line.split()[0] for line in checksums.text.splitlines() if line.split() and line.split()[-1].lstrip("*") == "icu4c-74_2-src.zip")
    icu_archive = downloads / "icu4c-74_2-src.zip"
    print("Fetching checksum-verified ICU 74.2 source headers", flush=True)
    records.append(download(icu_url, icu_archive, "sha512", expected))
    icu_root = CORE / "Common/3dParty/icu/win_64"
    icu_root.mkdir(parents=True, exist_ok=True)
    if not (icu_root / "icu/source/common/unicode/utypes.h").exists():
        with zipfile.ZipFile(icu_archive) as archive:
            for name in archive.namelist():
                if not (icu_root / name).resolve().is_relative_to(icu_root.resolve()):
                    raise RuntimeError("Unsafe ICU archive member")
            archive.extractall(icu_root)
    output = TASK / "evidence" / "dependency-assets.json"
    output.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print("Dependency assets verified and extracted", flush=True)


if __name__ == "__main__":
    main()
