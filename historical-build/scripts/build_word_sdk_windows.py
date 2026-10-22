"""Compile the pinned patched desktop Word SDK with Closure on Windows."""
import hashlib
import argparse
import json
import subprocess
from pathlib import Path

TASK = Path(r"D:\CodexWorkspaces\2026-10-13\office-windows")
STAGE = Path(r"D:\CodexCache\office-windows")
SDK = STAGE / "upstream/DesktopEditors/sdkjs"
OUTPUT = STAGE / "build/sdk-word/deploy/word"
JAVA = Path(r"C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot\bin\java.exe")
NODE = Path(r"D:\New Folder\node.exe")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--editor', choices=('word', 'cell', 'slide', 'visio'), default='word')
    editor = parser.parse_args().editor
    output = STAGE / ('build/sdk-' + editor) / 'deploy' / editor
    jar = STAGE / "js-tools/node_modules/google-closure-compiler-java/compiler.jar"
    config = json.loads((SDK / ('configs/' + editor + '.json')).read_text(encoding="utf-8"))["sdk"]
    externs = json.loads((SDK / "configs/externs.json").read_text(encoding="utf-8"))["externs"]
    minimum = config["min"] + config["desktop"]["min"]
    common = config["common"] + config["desktop"]["common"]
    inputs = {p: sha(SDK / p) for p in minimum + common + externs}
    output.mkdir(parents=True, exist_ok=True)
    arguments = ["-Xmx4096m", "-jar", jar.as_posix()]
    arguments += ["--externs=" + (SDK / p).as_posix() for p in externs]
    arguments += ["--define=window.AscCommon.g_cCompanyName='onlyoffice'", "--define=window.AscCommon.g_cProductVersion='9.4.0'", "--define=window.AscCommon.g_cBuildNumber='129'", "--define=window.AscCommon.g_cIsBeta='false'", "--rewrite_polyfills=true", "--warning_level=QUIET", "--language_out=ECMASCRIPT5", "--compilation_level=ADVANCED"]
    arguments += ["--js=" + (SDK / p).as_posix() for p in minimum]
    arguments += ["--chunk=sdk-all-min:" + str(len(minimum))]
    arguments += ["--js=" + (SDK / p).as_posix() for p in common]
    arguments += ["--chunk=sdk-all:" + str(len(common)) + ":sdk-all-min", "--chunk_output_path_prefix=" + output.as_posix() + "/"]
    argfile = output.parent.parent / "java-arguments.txt"
    argfile.write_text("\n".join('"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"' for value in arguments), encoding="utf-8")
    log = STAGE / ('logs/build-' + editor + '-sdk.log')
    print(f"Compiling {len(minimum) + len(common)} desktop {editor} source units", flush=True)
    with log.open("wb") as stream:
        result = subprocess.run([str(JAVA), "@" + str(argfile)], stdout=stream, stderr=stream)
    if result.returncode:
        raise RuntimeError(f"Closure exit {result.returncode}; see {log}")
    license_text = (SDK / "build/license.header").read_text(encoding="utf-8")
    values = {"@@AppCopyright": "Copyright (C) Ascensio System SIA 2012-2026. All rights reserved", "@@PublisherUrl": "https://www.onlyoffice.com/", "@@Version": "9.4.0", "@@Build": "129"}
    for key, value in values.items():
        license_text = license_text.replace(key, value)
    outputs = {}
    for name in ("sdk-all-min.js", "sdk-all.js"):
        path = output / name
        content = path.read_text(encoding="utf-8")
        if name == "sdk-all.js":
            content = "(function(window, undefined) {" + content + "})(window);"
        path.write_text(license_text + "\n" + content, encoding="utf-8")
        subprocess.run([str(NODE), "--check", str(path)], check=True)
        outputs[str(path)] = sha(path)
    if any(sha(SDK / p) != digest for p, digest in inputs.items()):
        raise RuntimeError("Source changed during compilation")
    package = json.loads((jar.parent / "package.json").read_text(encoding="utf-8"))
    report = {"kind": "Windows-desktop-" + editor + "-SDK-component-build", "source_revision": subprocess.check_output(["git", "-C", str(SDK), "rev-parse", "HEAD"], text=True).strip(), "source_units": len(minimum) + len(common), "inputs": inputs, "outputs": outputs, "compiler_version": package["version"], "compiler_sha256": sha(jar), "advanced": True, "node_syntax_checked": True, "exit": 0, "integrated": False, "windows_functional_acceptance": "not_run", "release_ready": False}
    (TASK / ('evidence/' + editor + '-sdk-build.json')).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Built and syntax-checked both desktop " + editor + " SDK bundles.", flush=True)


if __name__ == "__main__":
    main()
