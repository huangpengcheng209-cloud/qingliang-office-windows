# Windows TXT ↔ DOCX 开发预览

这一阶段可将 UTF-8 TXT 生成真实 DOCX，也可将普通 DOCX 的正文与表格提取为 UTF-8 TXT。转换调用固定 ONLYOFFICE `CTxtXmlFile`、文档模型和原有文件写入器；Python 入口负责包校验、ZIP 打包和输出保护。它是独立命令行预览，完整 x2t、编辑器和安装器仍未生成。

## 构建

需要 Python 3.11+、Git、VS 2022 C++ Build Tools 和 Windows SDK。先按 [FORMAT-BUILD.md](FORMAT-BUILD.md) 及其前置说明，在同一个目录顺序构建依赖、内核、存储、网络/加密、字体、HEIF、绘图及 VBA/文本库，再执行：

```powershell
python tools/build_docx.py verify
python tools/build_docx.py build --work-dir D:\CodexCache\qingliang-community-build
```

不需要旧机 Office 支持库、Qt 工具或 Qt 运行库。固定 qmake 工程仅用于捕获源清单；实际构建由 MSVC 执行，CI 不运行 qmake。所有输入身份见 `docx.inputs.lock.json`：6357 个 core 输入、1428 个 Boost 输入，以及 Katana、Gumbo、md4c 的独立归档。完整 core 归档按 SHA256 校验后仅提取清单内文件，避免逐个下载数千文件；仍逐项核对源码字节。已有无法识别的修改会停止。

| 工程 | C/C++ 编译单元 |
| --- | ---: |
| DocxFormatLib | 8 |
| PPTXFormatLib | 60 |
| XlsbFormatLib / XlsFormatLib | 1 / 42 |
| BinDocument / DocFormatLib | 43 / 8 |
| RtfFormatLib | 3 |
| HtmlFile2 DLL | 40 |
| OoxmlSupport | 5 |
| TxtDocxBridge | 7 |
| 合计 | 217 |

部分编译单元是直接包含多个 `.cpp` 的上游合并单元。HTML 的通配符按固定 Git 树展开，避免尚未提取的源码被遗漏；同名 C 文件分组输出，避免对象覆盖。没有裁去 HTML、RTF 或旧格式分支来隐藏链接缺项。MSVC `/sourceDependencies` 审计覆盖全部 217 单元，本机实际读取 7196 个锁定头文件，其余 341 个来自 MSVC/Windows SDK；具体数值以构建报告为准。

## 使用

```powershell
python tools/text_docx_preview.py txt-to-docx D:\Documents\example.txt D:\Documents\example.docx --exe D:\CodexCache\qingliang-community-build\bin\text-docx-preview.exe --work-dir D:\CodexCache\qingliang-text-preview
python tools/text_docx_preview.py docx-to-txt D:\Documents\example.docx D:\Documents\example-export.txt --exe D:\CodexCache\qingliang-community-build\bin\text-docx-preview.exe --work-dir D:\CodexCache\qingliang-text-preview
```

输出目录应已存在，输出文件名应未使用。错误或原生进程失败不会覆盖已有输出。TXT 输入只接受 UTF-8（可带 BOM），换行按段落处理，最后一个行结束符不额外创建空段；TXT 输出为 UTF-8 BOM、CRLF。表格按上游文本形式输出行分隔线与 `|`，不保留表格排版。

这是有范围限制的离线预览：只接受常规 DOCX、UTF-8 XML 部件和标准 `word/document.xml` 主部件；拒绝外部关系、DTD、加密包、路径穿越、大小写冲突及超限输入。上限为 TXT 16 MiB、DOCX 64 MiB、2048 部件、展开后 128 MiB、单部件 32 MiB。带外部超链接的文档也会被拒绝。复杂排版、修订、公式、嵌入内容及所有 Word 特性尚未验收。

## 修复与验证

完整修改文件在 `docx-sources/`，独立补丁在 `docx-patches/`：修正 XLS 上游合并源中的四个相对包含路径；复现固定上游的 Gumbo `isspace(unsigned char)` 适配；转义 TXT 的 XML 特殊字符并将制表符放入 `w:r`；修正表格单元格属性被误输出为空列的问题。

表格修复继承原冻结版本的转换实现，但以单独修改文件发布，`frozen_parent_sha256` 校验其父版本。`sources/` 原有 96 个文件和五份累计补丁均保持原字节。

本机 23 项真实文件测试通过：10 组 TXT/DOCX 往返、独立构造的 OOXML 段落与表格、表格属性回归，以及无效输入、已有文件保护等检查。初次独立交叉检查发现带属性表格多输出分隔符，修复后另以 python-docx 1.2.0 / lxml 6.0.2 完成 5 项双向交叉检查；该交叉检查仅为本机证据。源码保护测试与全新 Windows 构建由 Actions 执行。报告保留原生程序、输入清单和驱动脚本的 SHA256。

这些证据没有覆盖 Microsoft Word/WPS 实机打开、编辑器 GUI、复杂排版或安装验收。完整 VBA XML 导出也仍待独立运行检查。
