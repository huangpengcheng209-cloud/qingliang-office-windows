# 氢量办公社区版 · 开发预览

[![源码自动检查](https://github.com/huangpengcheng209-cloud/qingliang-office-windows/actions/workflows/source-checks.yml/badge.svg)](https://github.com/huangpengcheng209-cloud/qingliang-office-windows/actions/workflows/source-checks.yml)

基于 ONLYOFFICE Desktop Editors 9.4.0.129 修改的 Windows 办公项目，当前公开源码基线为 **9.4.0.129-win.22**（修改版日期 2026-10-16；社区仓库整理日期 2026-10-22）。原软件由 **Ascensio System SIA** 开发；本项目是独立维护的修改版，并非 ONLYOFFICE 官方发行，也未获得上游背书。

本仓库以“固定上游版本 + 累计补丁 + 完整修改文件”的方式提供源码。`sources/` 中可直接浏览本项目修改的 **96 个程序源码文件**；未经修改的上游源码通过 `upstream.lock.json` 锁定到公开 Git 提交。这里没有包含另一条正在开发的自研闭源路线。

后续依赖开发另含一份 UnicodeConverter UTF-32 修复，完整文件见 `dependency-sources/`，身份与补丁见 `dependencies.lock.json`；它不改写上述 win.22 冻结基线。

后续内核开发的两份 XML 修复和一份 ZIP 文件名修复见 `kernel-sources/` 和 `kernel-patches/`；`kernel.inputs.lock.json` 锁定 47 个编译单元及 213 个输入，同样独立于冻结基线。

x2t 前置库阶段新增两份复合存储修复，完整文件和差异见 `x2t-sources/`、`x2t-patches/`，输入由 `x2t.inputs.lock.json` 锁定；完整转换器的后续结果见下文。

网络/加密阶段另有一份 Windows 传输结果修复，完整文件和差异见 `transport-sources/`、`transport-patches/`，输入由 `transport.inputs.lock.json` 锁定；图形库后续构建状态见 `graphics.prerequisites.json`。

字体阶段公开了 HarfBuzz 的固定 ONLYOFFICE 适配和生成工程输入，见 `font-sources/`、`font-patches/`、`fonts.inputs.lock.json`；FreeType、Brotli 和 HarfBuzz 的构建与验证见下表。

HEIF 阶段增加 x265/libde265/libheif 固定源码构建，以及单独的 YCbCr 像素保留修复；输入与完整修改文件见 `heif.inputs.lock.json`、`heif-patches/`、`heif-sources/`。

绘图阶段已编译并链接固定 Windows 工程全部 515 个 C/C++ 单元，修复 HEIF 透明度和 SVG 内存加载问题，21 项原生运行检查本机通过。输入、补丁与完整修改文件见 `graphics.inputs.lock.json`、`graphics-patches/`、`graphics-sources/`；[构建说明](docs/GRAPHICS-BUILD.md)记录范围与命令。

VBA/文本前置阶段已生成 4+7 单元静态库及两个 POLE/Unicode 支持单元，37 项底层流解析和文本读写场景本机通过。修复与固定输入见 `format-patches/`、`format-sources/`、`formats.inputs.lock.json`；完整 VBA XML 导出仍待验证。

TXT↔DOCX 阶段已补齐并构建 217 个格式支持单元，可通过命令行生成真实 DOCX 和提取正文/表格。23 项实际文件测试及本机 5 项 python-docx 独立交叉检查通过；修复特殊字符、制表符和表格空列问题。命令、输入限制和验证范围见 [DOCX-BUILD.md](docs/DOCX-BUILD.md)。

2026-10-23 已从固定源码构建完整 **x2t 转换器**，补齐 721 次格式/渲染编译、V8、OpenSSL 和四套 SDKJS 脚本。本机 25 项实际文件检查通过，覆盖 TXT↔DOCX、CSV/XLSX、ODT/ODS/ODP 往返及 DOCX/XLSX/PPTX→PDF；使用独立库读取结果。另修复 XLSX 相邻文本单元格丢失和 ODS 选区属性问题。入口与边界见 [CONVERTER-BUILD.md](docs/CONVERTER-BUILD.md)；桌面编辑资源及实际文档验收进展见下文。

## 当前内容

演示编辑继续推进：**47 项真实 PPTX 检查通过**，覆盖文字/格式、形状移动、页面增加与撤销、保存重开、放映及 PDF 输出。右侧常驻“开始放映”，功能搜索区分当前页和首页放映；修复预览正常退出后被误判仍在运行的问题。截图、命令及范围见 [PRESENTATION-QUALITY.md](docs/PRESENTATION-QUALITY.md)。多媒体、对象动画和复杂演示仍需扩展。

表格与编辑区质量继续推进：**50 项真实 XLSX 检查、40 项 DOCX 回归通过**，覆盖基础多表/公式/排序/格式、保存重开与新建另存。修复快捷排序错误禁用、完整工具栏遮挡返回按钮及菜单键盘焦点，补齐快捷栏和文件菜单的明暗主题、短动效与减少动效。真实窗口截图、构建命令及未覆盖范围见 [EDITOR-QUALITY.md](docs/EDITOR-QUALITY.md)。图表视觉、完整筛选/剪贴板、PDF 表单、恢复和安装仍需完善。

新桌面已接通实际编辑区：四套桌面 SDKJS、五类编辑器界面、空模板、词典及 17,215 次运行资源复制有固定来源记录。本机 **39 项真实 DOCX 编辑保存、正常退出重开、新建另存和 PDF 导出检查通过**；另修复 60 个缺失中文字符串和大写保存后缀重复追加问题。命令与具体范围见 [EDITOR-BUILD.md](docs/EDITOR-BUILD.md)。表格、演示、PDF 表单、插件、媒体、完整视觉/动效和安装仍需继续完善。

新 Qt 主程序已接入真实工作台，103 个 Qt 单元构建和实际输入审计通过；本机 16 项真实窗口检查以最新主程序重跑通过，修复主题切换脚本错误及重复启动消息投递。五份配置/Unicode/单实例/保存后缀修改独立公开，原 96 文件保持不变。[Qt 桌面构建说明](docs/QT-DESKTOP-BUILD.md)记录命令与边界。

原生编辑宿主 DLL 已完成全部 280 单元编译/链接，22 项接口与文件系统检查本机通过，另修复大写/混合大小写保存扩展名识别。[HOST-BUILD.md](docs/HOST-BUILD.md)提供独立构建入口和来源说明；CEF 运行库使用固定官方 SDK，实际文档编辑保存范围见上述编辑器验收。

功能与界面完善正在推进：[工作台首批改进](docs/WORKBENCH-QUALITY.md)包含真实首页的搜索、类型/置顶筛选、键盘操作、明暗主题和短过渡，本机 37 项浏览器检查通过。测试的原生接口为独立边界适配器，尚未代表桌面编辑保存成功；完整范围与剩余工作见[质量清单](docs/PRODUCT-QUALITY-PLAN.md)。

2026-10-23 桌面前置继续推进：已从固定源码构建 Hunspell 拼写检查 DLL，22 项真实词典操作本机通过，并记录 Qt/CEF 材料身份和桌面宿主剩余依赖。入口与范围见 [DESKTOP-BUILD.md](docs/DESKTOP-BUILD.md)；安装包仍待构建验收。

| 路径 | 用途 |
| --- | --- |
| [sources/](sources/) | 五个上游模块中全部 96 个修改文件，保留原始字节 |
| [patches/](patches/) | 对固定提交应用的五份累计补丁 |
| [upstream.lock.json](upstream.lock.json) | 九个上游仓库的 URL 与提交 |
| [source-manifest.json](source-manifest.json) | 修改前后文件的 SHA256 与原始源码快照身份 |
| [tools/](tools/) | 源码检查与准备工具 |
| [historical-build/](historical-build/) | 冻结快照中的相关构建脚本，仅作为原环境参考 |
| [docs/BUILD.md](docs/BUILD.md) | 获取源码、构建边界与依赖说明 |
| [docs/PORTABLE-BUILD.md](docs/PORTABLE-BUILD.md) | Windows 原生保存组件的独立编译与 14 项运行测试 |
| [docs/DEPENDENCY-BUILD.md](docs/DEPENDENCY-BUILD.md) | Boost/ICU 固定源码准备、ICU/UnicodeConverter 源码编译和编码测试 |
| [docs/KERNEL-BUILD.md](docs/KERNEL-BUILD.md) | 内核源码构建与新依赖链接、22 项文件/ZIP/XML 运行测试 |
| [docs/X2T-DEPENDENCIES.md](docs/X2T-DEPENDENCIES.md) | Boost.Regex/DateTime、CompoundFileLib 构建及 21 项运行/Windows OLE 互操作测试 |
| [docs/NETWORK-CRYPTO-BUILD.md](docs/NETWORK-CRYPTO-BUILD.md) | 网络/CryptoPPLib 源码构建、20 项本机 HTTP/Windows CNG 运行测试和图形库缺项 |
| [docs/FONT-BUILD.md](docs/FONT-BUILD.md) | FreeType/Brotli/HarfBuzz 源码构建、上游字形/位置预期比对和 32 项运行测试 |
| [docs/HEIF-BUILD.md](docs/HEIF-BUILD.md) | x265/libde265/libheif 源码构建、16 项 HEIC 像素/元数据/错误场景与本机独立解码比对 |
| [docs/GRAPHICS-BUILD.md](docs/GRAPHICS-BUILD.md) | 完整绘图 DLL 源码构建、编译器实际输入审计及 21 项原生渲染检查 |
| [docs/FORMAT-BUILD.md](docs/FORMAT-BUILD.md) | VBA/文本静态库、37 项隔离解析和文本读写检查及完整转换边界 |
| [docs/DOCX-BUILD.md](docs/DOCX-BUILD.md) | TXT↔DOCX 命令行预览、217 单元格式依赖和 23 项实际文件检查 |
| [docs/CONVERTER-BUILD.md](docs/CONVERTER-BUILD.md) | 完整 x2t、V8、SDKJS 源码构建和 25 项真实文件检查 |
| [docs/EDITOR-BUILD.md](docs/EDITOR-BUILD.md) | 桌面编辑资源构建、中文/保存后缀修复和 39 项真实 DOCX/PDF 检查 |
| [docs/EDITOR-QUALITY.md](docs/EDITOR-QUALITY.md) | 50 项真实表格流程、40 项文档回归与编辑区主题/焦点/动效修复 |
| [docs/PRESENTATION-QUALITY.md](docs/PRESENTATION-QUALITY.md) | 47 项真实演示编辑、保存重开、放映与 PDF 导出检查 |
| [docs/STATUS.md](docs/STATUS.md) | 已有验收范围与已知问题 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 从源码预览到可安装 Beta 的交付顺序 |
| [CHANGELOG.md](CHANGELOG.md) | 源码版本及固定标签说明 |
| [NOTICE.md](NOTICE.md) | 来源、版权、许可证及第三方说明 |

## 获取及检查源码

需要 Python 3.11+ 和 Git。下载本仓库后运行：

```powershell
python tools/verify_sources.py
python -m unittest discover -s tests -v
python tools/verify_patches.py --cache D:\CodexCache\qingliang-community-patch-bases
python tools/prepare_sources.py --target D:\CodexCache\qingliang-community-source
```

补丁检查命令仅下载受修改文件对应的固定上游原文，并验证五份补丁的应用结果，无需复制完整上游。最后一条命令下载锁定的九个公开上游版本，并应用五份累计补丁，逐一核对 96 个修改文件的 SHA256。只写入明确指定的工作目录，不安装软件、不编译、不启动办公程序。目标内已有不同来源、不同提交或无法识别的修改时会停止。完整九仓库准备命令尚未在全新联网环境完成端到端验证；检查范围见 `docs/STATUS.md`。

GitHub Actions 在 Windows 和 Linux 上自动执行源码、补丁及保护行为检查；Windows 作业编译保存事务组件和 ICU/UnicodeConverter，各运行 14 个原生场景，并继续编译内核、执行 22 个联合场景，再构建 x2t 首组前置库、运行 21 个场景，以及网络/加密库的 20 个场景、字体库的 32 个场景、HEIF 库的 16 个场景和绘图 DLL 的 21 个场景及 VBA/文本的 36 个场景。这不包含完整应用编译或 GUI 验收。最初固定源码版本见 [win22-source-preview](https://github.com/huangpengcheng209-cloud/qingliang-office-windows/tree/win22-source-preview)，构建入口见[保存组件说明](docs/PORTABLE-BUILD.md)、[依赖构建说明](docs/DEPENDENCY-BUILD.md)与[内核构建说明](docs/KERNEL-BUILD.md)。

Windows 开发者可先验证不依赖原机 Office 支持库的原生组件：

```powershell
python tools/build_windows.py save-transaction --work-dir D:\CodexCache\qingliang-community-native
```

需要 Python、Git 和带 Windows SDK 的 MSVC C++ Build Tools。命令不会安装工具或生成办公应用安装包。

## 版本范围

已有本机 Windows 样本的编辑、保存重开、转换及安装升级验收记录，包含表格、合并单元格和脚注分页修复。仍有复杂排版差异，跨机、真实打印和长期混合使用尚未充分验证。这里不承诺全面兼容 WPS 或 Microsoft Office。

本次发布仅提供源码开发预览。**暂无本项目的公开安装包或软件 Release。** VLC 等现有二进制组件的历史补丁和静态依赖尚未完全对应；不能将本仓库理解为已完成整套依赖的离线重建或正式分发审核。

## 许可证与贡献

主程序及其衍生修改遵循所附 [LICENSE](LICENSE)（GNU AGPLv3 及上游附加条款）；第三方代码和非代码资源保留各自许可。上游许可要求的来源、修改声明及界面法律声明应继续保留。ONLYOFFICE is a trademark of Ascensio System SIA.

欢迎通过 Issues 报告能够复现的问题。提交时请提供版本、系统和脱敏的最小示例，请勿上传私人业务文件、密码或密钥。贡献约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。
