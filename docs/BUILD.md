# 源码准备与构建边界

当前最新入口：在同一稳定目录依次构建完整转换器、原生宿主、工作台、Qt 桌面和编辑资源。命令见 [CONVERTER-BUILD.md](CONVERTER-BUILD.md)、[HOST-BUILD.md](HOST-BUILD.md)、[QT-DESKTOP-BUILD.md](QT-DESKTOP-BUILD.md) 和 [EDITOR-BUILD.md](EDITOR-BUILD.md)。最新有 40 项 DOCX、50 项 XLSX、47 项 PPTX、40 项普通 PDF 和 16 项空白字段专项检查，见 [EDITOR-QUALITY.md](EDITOR-QUALITY.md)、[PRESENTATION-QUALITY.md](PRESENTATION-QUALITY.md) 和 [PDF-QUALITY.md](PDF-QUALITY.md)；完整产品与安装仍未完成。PDF 的桌面 SDK 覆盖层首次接入需重新编译 SDK，不能复用旧的未修复结果。以下分阶段记录中的限制按各阶段当时范围理解。

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

HEIF 前置库入口为 `tools/build_heif.py build --work-dir D:\CodexCache\qingliang-community-dependencies`，在同一树构建 x265/libde265/libheif，运行 16 项 HEIC 场景；需要 VS2022 和 CMake >=3.21,<4，详见 HEIF-BUILD.md。字体前置库入口为 `tools/build_fonts.py build`，命令与 32 项场景见 FONT-BUILD.md。完整图形库尚未编译链接。

网络/加密入口是 `tools/build_transport.py build --work-dir D:\CodexCache\qingliang-community-dependencies`，构建 kernel_network、CryptoPPLib 并运行 20 项 HTTP/CNG/Office 数据包装器测试；步骤与图形库前置缺项见 NETWORK-CRYPTO-BUILD.md。

x2t 首组前置库入口为 `tools/build_x2t_dependencies.py build --work-dir D:\CodexCache\qingliang-community-dependencies`，构建 Boost.Regex/DateTime 和 CompoundFileLib，并运行 21 项原生/Windows OLE 检查；详见 X2T-DEPENDENCIES.md。这仍不是 x2t 可执行文件构建入口。

内核阶段入口为 `tools/build_kernel.py build --work-dir D:\CodexCache\qingliang-community-dependencies`：复用固定依赖构建树，编译 47 个上游编译单元，链接新依赖并运行 22 项文件/ZIP/XML 测试。详细输入、独立补丁和边界见 KERNEL-BUILD.md。

新增可移植入口是 `tools/build_windows.py save-transaction`，可独立编译公开 Win32 保存事务组件并运行 14 个场景，完整步骤见 PORTABLE-BUILD.md。它不需要旧机 Office 支持库，也不依赖 Qt/CEF/VLC；这是首个组件的构建闭环，尚不是完整应用构建入口。

原构建使用 Visual Studio 2022 Build Tools/MSVC、Qt 5.15.2 msvc2019_64、Git、Python 和 Node.js；CEF 150.0.22/Chromium 150.0.7871.256 及其他支持库来自固定材料。核心脚本见 historical-build/scripts/build_windows_components.py、build_word_sdk_windows.py，以及 historical-build/publication/ 下 CEF 适配和 SDK 构建工具。

历史脚本保留原机器路径、环境依赖和打包前提，**不是可直接运行的一键构建入口**。直接执行其中打包脚本可能指向原项目目录；请先阅读并将路径调整到自己的隔离工作目录。源码准备工具也不下载原机器的私有文件或本地基线。

整套桌面应用仍缺完整的干净环境构建流程。历史应用仅重建了修改组件；后续社区阶段已另行源码构建 V8 和完整转换器，Qt/CEF、桌面宿主及其余依赖仍需对应。VLC 历史 x64 补丁、静态库精确版本和选择条件尚待核清。当前没有完整离线依赖包、桌面应用干净构建保证或安装器下载。

## 完整绘图 DLL 阶段

固定 Windows 绘图工程 515 个编译单元已在独立依赖目录完成编译、链接和 21 项原生场景；包括新字体/HEIF 库、Katana/Hyphen 输入，HEIF 透明度与 SVG 内存修复。命令、实际编译输入审计及范围见 [GRAPHICS-BUILD.md](GRAPHICS-BUILD.md)。这不代表完整 x2t、桌面程序或安装器已构建。

## VBA 与文本前置阶段

完整格式静态库及 POLE/Unicode 支持共 13 单元已构建，36 项底层解析和文本读写场景本机通过；源码、补丁、命令及仍未链接的完整格式转换范围见 [FORMAT-BUILD.md](FORMAT-BUILD.md)。
# TXT/DOCX 后续构建

在已有 VBA/文本及全部前置依赖的同一构建目录继续运行 `python tools/build_docx.py build --work-dir D:\CodexCache\qingliang-community-build`，可构建实际 TXT↔DOCX 命令行预览。完整步骤和输入限制见 [DOCX-BUILD.md](DOCX-BUILD.md)；它尚不是完整 x2t 或桌面应用构建。

## 完整 x2t 后续构建

前序阶段完成后，继续在同一目录运行 `python tools/build_converter.py build --work-dir D:\CodexCache\qingliang-community-build --test-python <独立读取器环境的 python.exe>`。该入口源码构建剩余格式/渲染库、OpenSSL、V8、完整 x2t 和四套 SDKJS，并执行 25 项真实文件检查。Java/Node、固定读取器、来源审计及范围见 [CONVERTER-BUILD.md](CONVERTER-BUILD.md)；桌面程序和安装器仍需后续工作。

## 桌面宿主前置

`python tools/build_desktop.py build --work-dir D:\CodexCache\qingliang-community-build` 源码构建 Hunspell 桌面拼写检查 DLL，运行 22 项真实词典操作；可复用同一缓存，也可独立运行。固定输入、三份既有适配、Qt/CEF 材料复核及桌面构建顺序见 [DESKTOP-BUILD.md](DESKTOP-BUILD.md)。
