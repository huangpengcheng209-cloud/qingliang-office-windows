# 来源、修改及许可声明

2026-10-23 完整转换器阶段：原 Ascensio System SIA 的 ODS 选区写入和 XLSX 空白压缩代码分别修复为合法 `pane` 属性及文本/公式单元格保留；完整文件、修改日期和原声明位于 converter-sources/core/，补丁位于 converter-patches/。Apple 导入依赖按固定 ONLYOFFICE 脚本复现适配，GLM、MDDS、librevenge、libodfgen、libetonyek 继续适用各自原许可。V8/Chromium 构建适配保留原版权，OpenSSL/V8/ICU、Jinja2/MarkupSafe/zlib 等外部源码的版本和许可输入由 converter.inputs.lock.json 保留，不统一改为主程序许可。构建辅助工具按固定官方地址获取，不随源码发布其二进制。Noto CJK 测试字体沿用 SIL OFL，原许可见 licenses/Noto-CJK-LICENSE.txt；字体仅在构建缓存下载，不安装系统字体。原 96 文件身份保持不变，本阶段未分发 DLL、转换器软件 Release 或桌面安装器。

2026-10-22 VBA/文本前置阶段：新增 VBA 流解压和游标边界修复，以及文本空读行数、大端输出不再改动输入的修复。原软件开发者 Ascensio System SIA，社区修改日期 2026-10-22；原版权及许可保留于 format-sources/ 的三个完整文件，差异和来源身份见 format-patches/、formats.inputs.lock.json。POLE/Unicode 支持使用固定 core 及既有冻结修改，原作者和各自许可继续适用。本阶段未分发新库或测试程序二进制，不执行宏代码。

2026-10-22 绘图阶段：固定 Katana/Hyphen 源码，复现 ONLYOFFICE 的 Katana tokenizer/parser/foundation 适配，保留 MIT 原文与版权；完整修改文件及差异见 graphics-sources/katana/、graphics-patches/。Katana 原许可、Hyphen 的 GPL/LGPL/MPL 选择及其模式文件例外说明保留于 licenses/graphics/，不统一改为主程序许可。新增 HEIF 辅助 Alpha 和 SVG 内存读取修复由氢量办公社区维护，原 Ascensio System SIA 代码身份及原有声明保留，修改日期为 2026-10-22；详见 graphics.inputs.lock.json。原 win.22 冻结 96 文件不变，本阶段未分发新增二进制。

2026-10-22 HEIF 依赖阶段：固定 x265/libde265/libheif 官方源码，复现 ONLYOFFICE 的 x265 版本读取适配；新增 libheif YCbCr 输出路径修复，避免无损图像经历有损 RGB 往返。原 libheif 作者为 Dirk Farin 等，社区修改日期及原 LGPL 版权/免责声明保留于 heif-sources/ 的完整文件，差异和输入身份见 heif-patches/、heif.inputs.lock.json。x265 及其子组件、libde265 和 libheif 各适用原有许可，正文由固定归档保留，不统一改成主程序许可。样本和新静态库二进制未随本仓库分发。

2026-10-22 字体依赖阶段：按固定 ONLYOFFICE core 的原有脚本复现 HarfBuzz `hb-ft.cc` 字符映射适配，保留原块、版权与许可，独立补丁及完整源码见 font-patches/、font-sources/。原 HarfBuzz 作者及其 Old MIT 许可继续保留；ONLYOFFICE 适配来源和固定身份见 fonts.inputs.lock.json。Brotli、FreeType、zlib 仍各适用原许可。FreeType 原 vendored 目录未包含其引用的许可正文，已从官方 2.10.4 对应提交补齐到 licenses/fonts/freetype/。官方归档中的测试字体未随本仓库发布，也未将字体许可改成主程序许可。本阶段未发布字体库二进制。

2026-10-22 Windows 传输开发补丁：处理已确认零长度 HTTP 响应的目标文件、让未实现上传返回明确失败，并请求不写持久下载缓存。原开发者为 Ascensio System SIA，修改由氢量办公社区维护，完整文件/原许可/修改日期保留于 transport-sources/，差异及身份见 transport-patches/、transport.inputs.lock.json。CryptoPP 厂商源码及自己的 License.txt/Readme.txt 保留在输入清单中；各自许可继续适用。本阶段未发布新二进制。

2026-10-22 x2t 前置库开发补丁：CompoundFileLib 修复读取缓冲区长度、跨扇区目标偏移和提交扇区遍历数量。原开发者为 Ascensio System SIA，修改由氢量办公社区维护；完整文件、修改日期和原声明保留于 x2t-sources/，差异和身份见 x2t-patches/、x2t.inputs.lock.json，遵循原适用许可。Boost 原始源码及许可由固定官方归档提供。本阶段未发布新增静态库或测试程序二进制。

原软件：ONLYOFFICE Desktop Editors，开发者 Ascensio System SIA。
本项目：氢量办公 Windows 修改版 9.4.0.129-win.22，修改版日期 2026-10-16，社区源码整理日期 2026-10-22。仓库维护者 GitHub 账号为 huangpengcheng209-cloud。

这是独立维护的修改版，不是原始软件，不代表上游认可、赞助或官方发行。ONLYOFFICE is a trademark of Ascensio System SIA.

主程序及衍生代码适用随附 AGPLv3 和上游附加条款，详见根目录 LICENSE 及 licenses/upstream/ 下各仓库原始许可。构建工具、Brotli 等组件各依自己的许可；不能将其统一改成 AGPL 或声称全部为本项目原创。

某些非代码插图、图标和技术文档适用 CC BY-SA 4.0，具体以上游文件声明为准。OCR 自定义界面与第三方 Tesseract.js 是不同来源；第三方声明和来源记录在 licenses/ocr/，本仓库未附带其预编译 WASM 和语言数据包。

保留版权、许可、免责和来源声明，并显著标记修改日期。修改版交互界面须提供清晰可访问的法律声明，说明原开发者、修改版本及许可入口。代码许可不授予上游商标使用权。

原 Windows 应用涉及 Qt、CEF/Chromium、VLC、Boost、ICU、字体、字典和 OCR 等依赖。本次源码仓库未包含对应运行时二进制，也不声称依赖源码已全部闭合。再次分发应用前仍须逐项核对实际所用组件、对应源码和适用条件。

2026-10-22 新增依赖开发补丁：UnicodeConverter 的两个解码入口调整 UTF-16 输出容量，以修复所测 UTF-32 补充平面字符往返失败。原开发者为 Ascensio System SIA，本修改由氢量办公社区项目维护；完整修改文件位于 dependency-sources/，差异与身份位于 dependency-patches/ 和 dependencies.lock.json。该修改遵循原程序适用许可，独立于原 win.22 冻结源码清单。本仓库未分发新构建的 ICU 或 UnicodeConverter 二进制。

2026-10-22 新增内核开发补丁：XML 编码声明接受单/双引号，DOM 在首次读取失败时不再创建节点。原开发者为 Ascensio System SIA，本修改由氢量办公社区项目维护；完整修改文件、原许可和修改日期保留于 kernel-sources/，差异与身份位于 kernel-patches/ 和 kernel.inputs.lock.json。内核还编入上游所附 zlib/libxml2，输入清单保留其许可文件；各自声明继续适用。本阶段未发布新内核二进制或应用安装包。

2026-10-22 云端回归新增 ZIP 文件名修复：OfficeUtils 的目录、单文件及内存写入统一使用 UTF-8 标记，相关读取按标记解码，并保留无标记条目的 OEM 回退。完整修改文件位于 kernel-sources/core/OfficeUtils/src/ZipUtilsCP.cpp，独立补丁与来源身份见 kernel-patches/zip-unicode-names.patch 和内核清单；原许可及修改日期保留。
2026-10-22 TXT/DOCX 转换阶段：完整修改文件与差异位于 docx-sources/、docx-patches/，固定输入见 docx.inputs.lock.json。XLS 相对包含路径、TXT XML 写入和表格文本转换的原开发者为 Ascensio System SIA，社区修改日期及原声明继续保留；表格修复另继承原冻结修改，未改写 sources/。Gumbo 的 unsigned-char 适配来自固定 ONLYOFFICE 获取脚本，保留 Google 原作者及 Apache 2.0 声明。新增原生适配入口与 Python 包装器适用本项目主程序许可。Gumbo、md4c 的原许可正文分别保留于 licenses/docx/gumbo/、licenses/docx/md4c/；Katana 许可沿用原固定图形归档。各第三方许可独立适用。本阶段仍只发布源码，不发布 DLL、转换器二进制或应用安装包。
