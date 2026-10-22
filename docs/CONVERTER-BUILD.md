# 完整 Windows x2t 转换器源码构建

2026-10-23：在前序依赖和 217 单元 DOCX 构建基础上，已从固定源码编译并链接完整 `x2t.exe`。新增 16 个工程配置共 721 次编译，涉及 709 个不同源码文件；同时源码构建 OpenSSL 1.1.1f、V8 8.9，并编译 Word、Cell、Slide、Visio 四套 SDKJS 脚本。未使用原机 Office DLL、导入定义桩、未解析符号强制链接或功能裁剪。

## 已验证范围

本机 Windows 11 / VS2022 的 25 项实际文件检查全部通过，共启动 38 次转换进程：

- UTF-8 TXT↔DOCX：中文、emoji、XML 特殊字符、制表符、空行、混合换行、BOM、前后空格及末尾换行。
- 独立 python-docx 生成的正文和表格提取；DOCX↔RTF、DOCX↔ODT，检查返回的正文及表格。
- openpyxl 生成的 XLSX→UTF-8 CSV；带引号中文 CSV→XLSX；XLSX↔ODS，逐格核对表头、文本和数值。
- python-pptx 生成的 PPTX↔ODP，独立读取返回的文字。
- DOCX、XLSX、PPTX→PDF；PyMuPDF 独立读取中英文内容、检查页数/损坏修复状态并栅格化。三张本机样本页另经目视检查。
- 缺失输入、截断的 OOXML ZIP，以及负数、溢出、尾随字符和不适用的编码哨兵；编码参数拒绝时保留既有输出。

这不是全部格式、复杂排版或 Microsoft Office/WPS 实际打开验收。宏未执行，签名和加密工作流、HTML/EPUB/FB2、旧 DOC/XLS/PPT、Apple/HWP/Visio 等路径未逐一验收。可执行文件包含相应上游模块，编译成功不等于这些路径已通过功能测试。上游转换器会检测文件内容；纯文本改成 `.docx` 后缀不一定被当作损坏 DOCX 拒绝。

## 输入与修复

`converter.inputs.lock.json` 固定 core、Boost、外部源码归档、九项 V8 DEPS、构建工具、SDKJS、Closure 编译器和测试字体的来源及 SHA256。`sources/` 原 96 文件和 `patches/` 原五份补丁保持冻结字节。

新增修改单独放在 `converter-sources/` 和 `converter-patches/`：

1. 复现固定 ONLYOFFICE Apple 导入库适配，保留 GLM、MDDS、librevenge、libodfgen、libetonyek 原版权和许可；五份 token 输入从固定 core 复制。
2. V8/Chromium 构建脚本适配 MSVC 动态运行时、当前安装的 Windows SDK、Python 3 和中文 MSVC 头文件诊断。旧 Windows 调试兼容 DLL 改为可选，核心调试 DLL 仍要求存在。Windows wrappers 翻译单元调用真实上游头文件实现，替代上游脚本临时改 Ninja 文件的做法。
3. ODS→XLSX 的 `selection` 写入 `pane`，修复误用 `activePane` 导致独立读取器拒绝文件的问题；属性定义见 [Microsoft Open XML 文档](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.spreadsheet.selection.pane?view=openxml-3.0.1)。
4. 修复 XLSX 空单元格压缩：含内联文本或公式的当前/前一单元格不能参与空白压缩，避免相邻表头丢失。修复单元独立编译为 `ConverterOoxml.lib`，在完整转换器中优先链接；前序 DOCX 构建入口及其锁文件保持原身份。

本机 MSVC 实际读取审计覆盖 8,047 个锁定源码/头文件以及 390 个编译器/SDK 头文件。V8 Ninja 审计记录 1,627 个具有头文件依赖的对象、3,029 个固定输入和 2,695 个构建生成输入；生成项单独记录，未冒称为原始源码。OpenSSL 安装头文件另列 74 项，其中 73 项与源头文件相同，一项由固定 Configure 配置生成。不同工具链的计数可能不同，构建必须通过来源/内容核对。

## 构建

需要 Python 3.11+、Git、7-Zip、VS2022 C++ Build Tools / Windows SDK、CMake 3.x、Java 21 和 Node.js。GN、Perl、辅助 Python 3.8 和 Closure JAR 由工具按固定身份下载到显式工作目录，不全局安装。旧工具版本用于复现固定上游，不代表完成安全维护审核。

先按 [DOCX-BUILD.md](DOCX-BUILD.md) 完成依赖、内核、网络/加密、字体、HEIF、绘图、VBA/文本和 DOCX 的顺序构建。继续使用同一个 `--work-dir`，不要另复制源码树。下面假定该目录为 `D:\CodexCache\qingliang-community-build`：

```powershell
$env:PIP_CACHE_DIR = 'D:\CodexCache\qingliang-pip'
$env:TEMP = 'D:\CodexCache\qingliang-community-build\tmp'
$env:TMP = $env:TEMP
python -m venv D:\CodexCache\qingliang-validation
D:\CodexCache\qingliang-validation\Scripts\python.exe -m pip install -r tests/converter-requirements.txt
python tools/build_converter.py verify
python tools/build_converter.py build --work-dir D:\CodexCache\qingliang-community-build --test-python D:\CodexCache\qingliang-validation\Scripts\python.exe
```

Java/Node 未在 PATH 时，可用 `--java <java.exe>`、`--node <node.exe>` 明确指定。输出包括 `bin/x2t.exe`、新构建 DLL、`bin/sdkjs/` 和 `bin/DoctRenderer.config`。Noto CJK 2.004 测试字体只下载到任务缓存，用于跨机中英文 PDF 验证，不安装系统字体；保留 SIL OFL 许可。

每次只运行一个完整构建。已有无法识别的源码、工具或归档字节会停止并保留。`build` 执行编译和完整检查；只复核现有二进制时运行：

```powershell
python tools/build_converter.py check --work-dir D:\CodexCache\qingliang-community-build --test-python D:\CodexCache\qingliang-validation\Scripts\python.exe --reuse-fixtures
```

`check` 不能替代干净重建；`--reuse-fixtures` 明确允许重复写入工具生成的样本目录，首次运行不需要该选项。失败报告应先保留，不删除用户文档。

## 证据与边界

工作目录保留 `converter-build-report.json`、`converter-test-result.json`、`converter-native-cases.json`、`converter-compiler-inputs.json`、`converter-v8-input-audit.json`、四份 SDK 编译日志，以及 `converter-fixtures/` 中的输入、输出、PDF 页面和进程日志。

GitHub Actions 在同一 Windows 2022 工作目录中顺序构建全部前置组件和完整转换器，并安装固定独立读取器执行相同检查。干净环境结果以对应提交的 [Actions](https://github.com/huangpengcheng209-cloud/qingliang-office-windows/actions/workflows/source-checks.yml) 为准。

本批未编译桌面编辑器、未运行应用 GUI、未构建安装器，也未发布二进制软件 Release。完整桌面 Beta 仍需界面/宿主依赖、安装载荷与许可材料核对，以及独立编辑、保存重开、转换、打印和安装卸载验收。
