# 氢量办公社区版 · 开发预览

基于 ONLYOFFICE Desktop Editors 9.4.0.129 修改的 Windows 办公项目，当前公开源码基线为 **9.4.0.129-win.22**（修改版日期 2026-10-16；社区仓库整理日期 2026-10-22）。原软件由 **Ascensio System SIA** 开发；本项目是独立维护的修改版，并非 ONLYOFFICE 官方发行，也未获得上游背书。

本仓库以“固定上游版本 + 累计补丁 + 完整修改文件”的方式提供源码。`sources/` 中可直接浏览本项目修改的 **96 个程序源码文件**；未经修改的上游源码通过 `upstream.lock.json` 锁定到公开 Git 提交。这里没有包含另一条正在开发的自研闭源路线。

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
| [docs/STATUS.md](docs/STATUS.md) | 已有验收范围与已知问题 |
| [NOTICE.md](NOTICE.md) | 来源、版权、许可证及第三方说明 |

## 获取及检查源码

需要 Python 3.11+ 和 Git。下载本仓库后运行：

```powershell
python tools/verify_sources.py
python tools/prepare_sources.py --target D:\CodexCache\qingliang-community-source
```

第二条命令下载锁定的九个公开上游版本，并应用五份累计补丁，逐一核对 96 个修改文件的 SHA256。只写入明确指定的工作目录，不安装软件、不编译、不启动办公程序。目标内已有不同来源、不同提交或无法识别的修改时会停止。该命令尚未在全新联网环境完成端到端验证；本地已验证的内容见 `docs/STATUS.md`。

## 版本范围

已有本机 Windows 样本的编辑、保存重开、转换及安装升级验收记录，包含表格、合并单元格和脚注分页修复。仍有复杂排版差异，跨机、真实打印和长期混合使用尚未充分验证。这里不承诺全面兼容 WPS 或 Microsoft Office。

本次发布仅提供源码开发预览。**暂无本项目的公开安装包或软件 Release。** VLC 等现有二进制组件的历史补丁和静态依赖尚未完全对应；不能将本仓库理解为已完成整套依赖的离线重建或正式分发审核。

## 许可证与贡献

主程序及其衍生修改遵循所附 [LICENSE](LICENSE)（GNU AGPLv3 及上游附加条款）；第三方代码和非代码资源保留各自许可。上游许可要求的来源、修改声明及界面法律声明应继续保留。ONLYOFFICE is a trademark of Ascensio System SIA.

欢迎通过 Issues 报告能够复现的问题。提交时请提供版本、系统和脱敏的最小示例，请勿上传私人业务文件、密码或密钥。贡献约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。
