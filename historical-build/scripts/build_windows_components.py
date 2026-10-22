"""Rebuild patched Windows components with pinned official support DLLs.

This is a component rebuild, not a complete source rebuild of Qt/CEF/V8 and
the unchanged official support libraries. Evidence records that distinction.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TASK = Path(r"D:\CodexWorkspaces\2026-10-13\office-windows")
STAGE = Path(r"D:\CodexCache\office-windows")
SOURCE = STAGE / "upstream" / "DesktopEditors"
CORE = SOURCE / "core"
BASELINE = STAGE / "baseline" / "Office-Win11-x64"
QT = STAGE / "qt" / "5.15.2" / "msvc2019_64"
VS = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
LIBRARIES = CORE / "build" / "lib" / "win_64"
PROJECTS = {
    "kernel": CORE / "Common/kernel.pro",
    "crypto": CORE / "Common/3dParty/cryptopp/project/cryptopp.pro",
    "compound": CORE / "Common/cfcpp/cfcpp.pro",
    "xlsb": CORE / "OOXML/Projects/Linux/XlsbFormatLib/XlsbFormatLib.pro",
    "vba": CORE / "MsBinaryFile/Projects/VbaFormatLib/Linux/VbaFormatLib.pro",
    "docx": CORE / "OOXML/Projects/Linux/DocxFormatLib/DocxFormatLib.pro",
    "pptx": CORE / "OOXML/Projects/Linux/PPTXFormatLib/PPTXFormatLib.pro",
    "bin": CORE / "OOXML/Projects/Linux/BinDocument/BinDocument.pro",
    "txt": CORE / "TxtFile/Projects/Linux/TxtXmlFormatLib.pro",
    "rtf": CORE / "RtfFile/Projects/Linux/RtfFormatLib.pro",
    "ppt": CORE / "MsBinaryFile/Projects/PPTFormatLib/Linux/PPTFormatLib.pro",
    "doc": CORE / "MsBinaryFile/Projects/DocFormatLib/Linux/DocFormatLib.pro",
    "odf": CORE / "OdfFile/Projects/Linux/OdfFormatLib.pro",
    "xls": CORE / "MsBinaryFile/Projects/XlsFormatLib/Linux/XlsFormatLib.pro",
    "pdf": CORE / "PdfFile/PdfFile.pro",
    "fonts": CORE / "DesktopEditor/AllFontsGen/AllFontsGen.pro",
    "converter": CORE / "X2tConverter/build/Qt/X2tConverter.pro",
    "shell": SOURCE / "desktop-apps/win-linux/ASCDocumentEditor.pro",
}
for module in ("regex", "date_time", "filesystem", "system"):
    PROJECTS["boost-" + module] = STAGE / "build" / ("boost-" + module) / "boost.pro"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def environment():
    env_script = STAGE / "msvc-env.cmd"
    env_script.write_text('@echo off\ncall "' + str(VS / "VC/Auxiliary/Build/vcvarsall.bat") + '" x64 >nul\nif errorlevel 1 exit /b 1\nset\n', encoding="ascii")
    result = subprocess.run(["cmd", "/d", "/c", str(env_script)], capture_output=True, check=True)
    env = os.environ.copy()
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        if "=" in line and not line.startswith("="):
            name, value = line.split("=", 1)
            if name.upper() in ("PATH", "LIB", "INCLUDE", "LIBPATH", "VCTOOLSINSTALLDIR", "WINDOWSSDKDIR", "WINDOWSSDKVERSION"):
                env[name.upper()] = value
    env["PATH"] = str(QT / "bin") + os.pathsep + env.get("PATH", env.get("Path", ""))
    env["PRODUCT_VERSION"] = "9.4.0"
    env["BUILD_NUMBER"] = "129"
    env["VSLANG"] = "1033"
    env["TEMP"] = str(STAGE / "temp")
    env["TMP"] = env["TEMP"]
    Path(env["TEMP"]).mkdir(exist_ok=True)
    return env


def execute(command, log, env, cwd=None):
    command = command.copy()
    command[0] = shutil.which(command[0], path=env["PATH"]) or command[0]
    with log.open("ab") as stream:
        stream.write(("\nCOMMAND " + repr(command) + "\n").encode())
        result = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=stream)
    if result.returncode:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        errors = [line for line in lines if re.search(r"(?i)fatal error|error [a-z]+[0-9]+|LNK[0-9]+|U1077|cannot find|Project ERROR", line)]
        print("\n".join(errors[-5:] or lines[-8:]), flush=True)
        raise RuntimeError(f"Exit {result.returncode}; see {log}")


def prepare_imports(env):
    manifest = json.loads((BASELINE / "manifest.json").read_text(encoding="utf-8"))
    failures = []
    for item in manifest["files"]:
        path = BASELINE / item["path"]
        if not path.resolve().is_relative_to(BASELINE.resolve()) or not path.is_file() or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            failures.append(item["path"])
    if failures:
        raise RuntimeError("Baseline integrity failure: " + repr(failures[:10]))
    LIBRARIES.mkdir(parents=True, exist_ok=True)
    definitions = STAGE / "import-definitions"
    definitions.mkdir(exist_ok=True)
    report = []
    dlls = list((BASELINE / "app" / "converter").glob("*.dll"))
    dlls += [BASELINE / "app" / name for name in ("ascdocumentscore.dll", "qtascdocumentscore.dll", "videoplayer.dll", "hunspell.dll")]
    for dll in dlls:
        dump = subprocess.check_output([shutil.which("dumpbin", path=env["PATH"]), "/nologo", "/exports", str(dll)], env=env)
        names = []
        for line in dump.decode("utf-8", "replace").splitlines():
            match = re.match(r"\s*\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]{8}\s+(\S+)", line)
            if match:
                names.append(match.group(1))
        if not names:
            raise RuntimeError("No exports in " + str(dll))
        definition = definitions / (dll.stem + ".def")
        definition.write_text('LIBRARY "' + dll.name + '"\nEXPORTS\n' + "\n".join(names) + "\n", encoding="ascii")
        library = LIBRARIES / (dll.stem + ".lib")
        if not library.exists():
            execute(["lib", "/nologo", "/machine:x64", "/def:" + str(definition), "/out:" + str(library)], STAGE / "logs" / "import-libraries.log", env)
        if dll.name == "icuuc74.dll":
            target = CORE / "Common/3dParty/icu/win_64/build/icuuc.lib"
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(library.read_bytes())
        report.append({"dll": str(dll), "dll_sha256": sha(dll), "exports": len(names), "import_library": str(library), "source_rebuilt": False})
    output = TASK / "evidence" / "official-support-libraries.json"
    output.write_text(json.dumps({"baseline_manifest_checked": len(manifest["files"]), "libraries": report, "full_source_rebuild": False}, indent=2), encoding="utf-8")
    print(f"Verified {len(manifest['files'])} baseline files and prepared {len(report)} import libraries.", flush=True)


def build_project(name, env):
    project = PROJECTS[name]
    folder = STAGE / "build" / name
    folder.mkdir(parents=True, exist_ok=True)
    if name.startswith("boost-"):
        module = name.removeprefix("boost-")
        boost = CORE / "Common/3dParty/boost/boost_1_72_0"
        destination = CORE / "Common/3dParty/boost/build/win_64/lib"
        destination.mkdir(parents=True, exist_ok=True)
        sources = sorted((boost / "libs" / module / "src").rglob("*.cpp"))
        if not sources:
            raise RuntimeError("Missing Boost module source: " + module)
        project.write_text("\n".join([
            "QT -= core gui", "TEMPLATE = lib", "CONFIG += staticlib",
            "TARGET = libboost_" + module + "-vc142-mt-x64-1_72",
            "CORE_ROOT_DIR = " + CORE.as_posix(), "PWD_ROOT_DIR = " + folder.as_posix(),
            "include(" + (CORE / "Common/base.pri").as_posix() + ")",
            "INCLUDEPATH += " + boost.as_posix(),
            "DEFINES += BOOST_ALL_NO_LIB",
            "DESTDIR = " + destination.as_posix(),
            "SOURCES += " + (" " + chr(92) + "\n").join(p.as_posix() for p in sources),
        ]), encoding="utf-8")
    log = STAGE / "logs" / ("build-" + name + ".log")
    started = time.monotonic()
    print(f"Building {name} from {project.relative_to(SOURCE) if project.is_relative_to(SOURCE) else project}", flush=True)
    object_dir = STAGE / "o" / name
    object_dir.mkdir(parents=True, exist_ok=True)
    command = [str(QT / "bin/qmake.exe"), str(project), "CONFIG-=debug", "CONFIG+=release vs2019 core_disable_all_warnings", "QMAKE_CXXFLAGS+=/MP4 /bigobj /utf-8", "QMAKE_CFLAGS+=/MP4 /utf-8", "DEFINES+=BOOST_ALL_NO_LIB", "-after", "OBJECTS_DIR=" + object_dir.as_posix()]
    if name == "converter":
        command.append("PRE_TARGETDEPS+=" + " ".join(p.as_posix() for p in sorted(LIBRARIES.glob("*.lib"))))
    execute(command, log, env, folder)
    execute(["nmake", "/nologo"], log, env, folder)
    report_path = TASK / "evidence" / "windows-component-builds.json"
    records = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    records[name] = {"project": str(project), "exit": 0, "elapsed_seconds": round(time.monotonic() - started, 1), "log": str(log), "compiler_toolchain": "MSVC 2022 14.44 x64", "qt": "5.15.2 msvc2019_64", "product_version": "9.4.0.129", "full_source_desktop_rebuild": False, "functional_acceptance": "not_run"}
    report_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Built {name} in {records[name]['elapsed_seconds']} s", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-imports", action="store_true")
    parser.add_argument("--projects", nargs="*", choices=list(PROJECTS), default=[])
    args = parser.parse_args()
    env = environment()
    if args.prepare_imports:
        prepare_imports(env)
    for name in args.projects:
        build_project(name, env)


if __name__ == "__main__":
    main()
