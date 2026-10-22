"""Retain the exact stock Qt source after all shipped Qt PE sections matched."""
import hashlib
import json
import time
from pathlib import Path
import requests

TASK = Path(r"D:\CodexWorkspaces\2026-10-13\office-windows")
URL = "https://download.qt.io/archive/qt/5.15/5.15.2/single/qt-everywhere-src-5.15.2.tar.xz"
SHA256 = "3a530d1b243b5dec00bc54937455471aaa3e56849d2593edb8ded07228202240"
BYTES = 586690220

def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def main():
    target = TASK / "source/third-party/qt-everywhere-src-5.15.2.tar.xz"
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        part = target.with_suffix(target.suffix + ".part")
        offset = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        with requests.get(URL, headers=headers, stream=True, timeout=(30, 60)) as r:
            r.raise_for_status()
            mode = "ab" if offset and r.status_code == 206 else "wb"
            last = time.monotonic()
            with part.open(mode) as f:
                for data in r.iter_content(1024 * 1024):
                    f.write(data)
                    if time.monotonic() - last >= 20:
                        print(f"Qt source downloaded {f.tell()} / {BYTES} bytes", flush=True)
                        last = time.monotonic()
        if part.stat().st_size != BYTES or sha(part) != SHA256:
            raise RuntimeError("Qt official source hash mismatch")
        part.replace(target)
    if target.stat().st_size != BYTES or sha(target) != SHA256:
        raise RuntimeError("Existing Qt source identity mismatch")
    report = {"file": str(target), "bytes": BYTES, "sha256": SHA256, "version": "5.15.2", "source_url": URL, "official_hash_metadata": URL + ".mirrorlist", "shipped_qt_pe_sections_match_stock_sdk": True, "identity_evidence": "qt-source-identity-check.json", "full_program_corresponding_source_closure": False}
    (TASK / "evidence/qt-corresponding-source.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)

if __name__ == "__main__":
    main()
