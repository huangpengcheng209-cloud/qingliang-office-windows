# 源码准备与构建边界

## 源码结构

上游九个仓库的 URL 和精确提交见 ../upstream.lock.json。tools/prepare_sources.py 将 DesktopEditors 放在目标下 upstream/DesktopEditors，其他应用模块放在其同名子目录；build_tools 与 brotli 放在 upstream/ 下。该工具不执行递归子模块拉取，不自动下载全部嵌套依赖。

项目修改以五份累计补丁提供，每份仅应用一次；sources/ 中包含对应完整修改文件。DesktopEditors 本身没有程序文件修改。历史源码包中的 DesktopEditors.patch 仅记录子模块的 `-dirty` 状态，不是合法的新提交，故不作为补丁发布。task-first-home.patch 已包含在当前累计修改中，不能重复叠加。

## 本地检查

```powershell
python tools/verify_sources.py
python -m unittest discover -s tests -v
python tools/verify_patches.py --cache D:\CodexCache\qingliang-community-patch-bases
python tools/prepare_sources.py --target D:\CodexCache\qingliang-community-source
```

目标目录必须由调用者明确选择。工具不会覆盖提交不同或包含未知修改的既有仓库；补丁已经应用且修改文件哈希一致时可重复运行。上游 Git 子模块的已知 dirty 状态不会被当作程序文件修改。不同于一次完整构建，这只准备锁定源码和本项目修改。

`verify_patches.py` 仅下载 96 个修改文件中已有上游原文的部分，核对原文哈希，在专属缓存工作目录应用五份累计补丁，再核对最终 96 个文件哈希。新文件没有上游原文，直接由补丁创建。它不下载完整九仓库、嵌套依赖或二进制支持库。CI 在 Windows/Linux 上运行上述源码检查及保护行为测试，不运行最后一条完整准备命令，不编译应用。

## Windows 编译现状

原构建使用 Visual Studio 2022 Build Tools/MSVC、Qt 5.15.2 msvc2019_64、Git、Python 和 Node.js；CEF 150.0.22/Chromium 150.0.7871.256 及其他支持库来自固定材料。核心脚本见 historical-build/scripts/build_windows_components.py、build_word_sdk_windows.py，以及 historical-build/publication/ 下 CEF 适配和 SDK 构建工具。

历史脚本保留原机器路径、环境依赖和打包前提，**不是可直接运行的一键构建入口**。直接执行其中打包脚本可能指向原项目目录；请先阅读并将路径调整到自己的隔离工作目录。源码准备工具也不下载原机器的私有文件或本地基线。

尚缺可从全新 Windows 环境完整执行的依赖准备和构建流程。原应用重建了修改组件，未从源码重建全部 Qt/CEF/V8 及未修改支持库。VLC 历史 x64 补丁、静态库精确版本和选择条件尚待核清。故当前没有完整离线依赖包、干净机器构建保证或安装器下载。
