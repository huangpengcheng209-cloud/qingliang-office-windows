"""Integrate rebuilt components into the single staged Windows candidate."""
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path

TASK = Path(r"D:\CodexWorkspaces\2026-10-13\office-windows")
STAGE = Path(r"D:\CodexCache\office-windows")
SOURCE = STAGE / "upstream/DesktopEditors"
CANDIDATE = STAGE / "candidate"
HANDOFF = TASK / "handoff/Office-source-handoff"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pe_machine(path):
    with path.open("rb") as stream:
        stream.seek(0x3C)
        offset = struct.unpack("<I", stream.read(4))[0]
        stream.seek(offset)
        if stream.read(4) != b"PE\0\0":
            raise RuntimeError("Not a Windows PE artifact")
        return struct.unpack("<H", stream.read(2))[0]


def main():
    app = CANDIDATE / "app"
    baseline_app = STAGE / "baseline/Office-Win11-x64/app"
    # The signed DesktopEditors.exe is the Windows launcher. It configures
    # DLL search paths before running the native editor stored as editors.exe.
    shutil.copyfile(baseline_app / "DesktopEditors.exe", app / "DesktopEditors.exe")
    sources = {
        "editors.exe": SOURCE / "desktop-apps/win-linux/build/win_64/DesktopEditors.exe",
        "converter/x2t.exe": SOURCE / "core/build/bin/win_64/x2t.exe",
        "converter/PdfFile.dll": SOURCE / "core/build/lib/win_64/PdfFile.dll",
        "editors/sdkjs/word/sdk-all-min.js": STAGE / "build/sdk-word/deploy/word/sdk-all-min.js",
        "editors/sdkjs/word/sdk-all.js": STAGE / "build/sdk-word/deploy/word/sdk-all.js",
        "editors/sdkjs/cell/sdk-all-min.js": STAGE / "build/sdk-cell/deploy/cell/sdk-all-min.js",
        "editors/sdkjs/cell/sdk-all.js": STAGE / "build/sdk-cell/deploy/cell/sdk-all.js",
    }
    if (app / "PdfFile.dll").exists():
        sources["PdfFile.dll"] = sources["converter/PdfFile.dll"]
    for editor in ("documenteditor", "spreadsheeteditor", "presentationeditor", "pdfeditor"):
        sources["editors/web-apps/apps/" + editor + "/main/app.js"] = STAGE / "build/web-apps" / editor / "main/app.js"
        sources["editors/web-apps/apps/" + editor + "/main/code.js"] = STAGE / "build/web-apps" / editor / "main/code.js"
    reports = []
    for relative, origin in sources.items():
        if not origin.is_file():
            raise RuntimeError("Missing build artifact: " + str(origin))
        if origin.suffix.lower() in (".exe", ".dll") and pe_machine(origin) != 0x8664:
            raise RuntimeError("Not an x64 Windows build: " + str(origin))
        destination = app / relative
        if not destination.is_file():
            raise RuntimeError("Expected original integration target is missing: " + relative)
        before = sha(baseline_app / relative)
        shutil.copyfile(origin, destination)
        if sha(destination) != sha(origin):
            raise RuntimeError("Integration byte mismatch")
        reports.append({"target": relative, "source": str(origin), "source_sha256": sha(origin), "previous_sha256": before, "windows_pe_x64": origin.suffix.lower() in (".exe", ".dll")})
    plugin = app / "editors/sdkjs-plugins/{440EBF13-9B19-4BD8-8621-05200E58140B}"
    if not plugin.is_dir():
        raise RuntimeError("Official OCR plugin directory is missing")
    preserved = {p.relative_to(plugin).as_posix(): sha(p) for p in plugin.rglob("*") if p.is_file()}
    overlay = HANDOFF / "source-changes/overrides/ocr"
    overlaid = []
    for origin in overlay.rglob("*"):
        if origin.is_file():
            relative = origin.relative_to(overlay)
            destination = plugin / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, destination)
            overlaid.append(relative.as_posix())
            if sha(origin) != sha(destination):
                raise RuntimeError("OCR overlay mismatch")
    retained = [p for p in preserved if p not in overlaid]
    if any(sha(plugin / p) != preserved[p] for p in retained):
        raise RuntimeError("Existing OCR supporting files were changed")
    report = {"kind": "Windows-patched-component-candidate", "candidate": str(CANDIDATE), "rebuilt_components": reports, "ocr_overlay_files": len(overlaid), "ocr_supporting_files_preserved": len(retained), "support_origin": "Signature-checked official Windows 9.4.0.129 baseline", "full_source_desktop_rebuild": False, "windows_functional_acceptance": "not_run", "installer_acceptance": "not_run", "release_ready": False}
    (TASK / "evidence/candidate-integration.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    patches = TASK / "source-changes"
    patches.mkdir(exist_ok=True)
    for repo in ("core", "sdkjs", "web-apps", "desktop-apps"):
        contents = subprocess.check_output(["git", "-C", str(SOURCE / repo), "diff", "--binary", "HEAD"])
        (patches / (repo + ".patch")).write_bytes(contents)
    print(json.dumps({"rebuilt_artifacts_integrated": len(reports), "ocr_overlay_files": len(overlaid), "ocr_original_support_files_retained": len(retained)}))


if __name__ == "__main__":
    main()
