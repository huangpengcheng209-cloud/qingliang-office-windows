# 来源、修改及许可声明

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
