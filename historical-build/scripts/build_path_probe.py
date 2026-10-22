import os
import subprocess
from pathlib import Path
from build_windows_components import environment, execute, CORE, STAGE, TASK

def main():
    folder = STAGE / "build/path-probe"
    folder.mkdir(exist_ok=True)
    exe = folder / "path-probe.exe"
    env = environment()
    execute(["cl", "/nologo", "/EHsc", "/MD", "/utf-8", "/I" + str(CORE), str(TASK / "scripts/runtime_path_probe.cpp"), "/Fo" + str(folder / "path-probe.obj"), "/Fe" + str(exe), "/link", str(CORE / "build/lib/win_64/kernel.lib")], STAGE / "logs/path-probe-build.log", env, folder)
    env["PATH"] = str(STAGE / "candidate/app/converter") + os.pathsep + env["PATH"]
    for case, source in (("candidate", TASK / "evidence/accepted-files/文字保存.docx"), ("candidate-ascii", STAGE / "qa/cli-pdf-probe/source.docx")):
        result = subprocess.run([str(exe), str(STAGE / "qa/cli-pdf-probe" / case / "task.xml"), str(source)], capture_output=True, env=env)
        print(case, result.returncode, result.stdout.decode("ascii", "replace"), result.stderr.decode("ascii", "replace"), flush=True)

if __name__ == "__main__":
    main()
