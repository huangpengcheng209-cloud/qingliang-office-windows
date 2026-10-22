# 氢量办公社区版 · 开发预览

[![源码自动检查](https://github.com/huangpengcheng209-cloud/qingliang-office-windows/actions/workflows/source-checks.yml/badge.svg)](https://github.com/huangpengcheng209-cloud/qingliang-office-windows/actions/workflows/source-checks.yml)

基于 ONLYOFFICE Desktop Editors 9.4.0.129 修改的 Windows 办公项目，当前公开源码基线为 **9.4.0.129-win.22**（修改版日期 2026-10-16；社区仓库整理日期 2026-10-22）。原软件由 **Ascensio System SIA** 开发；本项目是独立维护的修改版，并非 ONLYOFFICE 官方发行，也未获得上游背书。

本仓库以“固定上游版本 + 累计补丁 + 完整修改文件”的方式提供源码。`sources/` 中可直接浏览本项目修改的 **96 个程序源码文件**；未经修改的上游源码通过 `upstream.lock.json` 锁定到公开 Git 提交。这里没有包含另一条正在开发的自研闭源路线。

后续依赖开发另含一份 UnicodeConverter UTF-32 修复，完整文件见 `dependency-sources/`，身份与补丁见 `dependencies.lock.json`；它不改写上述 win.22 冻结基线。

后续内核开发的两份 XML 修复和一份 ZIP 文件名修复见 `kernel-sources/` 和 `kernel-patches/`；`kernel.inputs.lock.json` 锁定 47 个编译单元及 213 个输入，同样独立于冻结基线。

x2t 前置库阶段新增两份复合存储修复，完整文件和差异见 `x2t-sources/`、`x2t-patches/`，输入由 `x2t.inputs.lock.json` 锁定；完整转换器仍在推进。

## 当前内容

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

GitHub Actions 在 Windows 和 Linux 上自动执行源码、补丁及保护行为检查；Windows 作业编译保存事务组件和 ICU/UnicodeConverter，各运行 14 个原生场景，并继续编译内核、执行 22 个联合场景，再构建 x2t 首组前置库、运行 21 个场景。这不包含完整应用编译或 GUI 验收。最初固定源码版本见 [win22-source-preview](https://github.com/huangpengcheng209-cloud/qingliang-office-windows/tree/win22-source-preview)，构建入口见[保存组件说明](docs/PORTABLE-BUILD.md)、[依赖构建说明](docs/DEPENDENCY-BUILD.md)与[内核构建说明](docs/KERNEL-BUILD.md)。

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
