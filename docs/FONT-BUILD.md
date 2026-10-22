# 字体塑形依赖构建

本阶段从固定源码构建三个静态库，使用 Visual Studio 2022 x64、Release、动态 MSVC 运行时 `/MD`。它们是完整图形库的前置依赖，尚未生成图形 DLL、x2t、编辑器或安装包。

| 组件 | 来源 | 编译单元 |
| --- | --- | --- |
| FreeType 2.10.4 与上游工程自带 zlib | core 固定提交中的 `DesktopEditor/freetype-2.10.4`、`OfficeUtils/src` | 40 + 11 |
| Brotli common/decoder | `a47d7475063eb223c87632eed806c0070e70da29` 官方源码归档 | 10 |
| HarfBuzz | `894a1f72ee93a1fd8dc1d9218cb3fd8f048be29a` 官方源码归档，并应用固定 ONLYOFFICE 适配 | 75 |

`fonts.inputs.lock.json` 固定两个归档 SHA256、536 个 core 输入、412 个 HarfBuzz 输入和 32 个 Brotli 输入，包含头文件、许可证和测试数据。源码按完整图形工程预期位置准备在同一工作树中；这里只提取选定输入，不创建额外的完整源码副本。HarfBuzz 归档中指向 `README.md` 的 `README` 文档符号链接会核对目标并跳过；其他链接、不安全路径、重复路径、现有未知修改均拒绝覆盖。

## 适配与工程生成

固定上游 `Common/3dParty/harfbuzz/make.py` 使用自己的标记补丁格式替换 `hb-ft.cc` 的单字形查询逻辑，增加字符映射回退。本仓库按该脚本保留原块的 `#if 0` 方式复现，差异见 `font-patches/onlyoffice-hb-ft.patch`，完整结果见 `font-sources/harfbuzz/src/hb-ft.cc`。这是上游已有适配的可审计再现，未将其标记为社区新算法。

`font-sources/core/Common/3dParty/harfbuzz/harfbuzz.pri` 按原生成器的筛选规则生成，保持相同的 75 个源码单元集合，以稳定排序输出；定义 `HAVE_FREETYPE`、`HB_NO_VISIBILITY`。FreeType 启用系统 zlib 和 Brotli 支持，与现有工程配置一致。本阶段没有关闭或删减完整图形工程的功能。

## 运行

需要 Python 3.11+、Git、带 Windows SDK 的 VS2022 C++ Build Tools。不会自动安装工具；VS2026 的兼容性尚未验证。

```powershell
python tools/build_fonts.py verify
python tools/build_fonts.py build --work-dir D:\CodexCache\qingliang-community-publish\dependency-build
```

可传 `--archive-cache` 只读复用两个固定归档，或 `--source-cache` 只读复用固定 core 文件；每个输入都会核对 SHA256。复用同一依赖工作目录，公共 `.build.lock` 防止同时构建；不需要重新构建 ICU 或此前阶段。输出位于工作目录的 `lib`、`bin`、`fonts-build.log`、`fonts-build-report.json` 和 `fonts-test-result.json`。

## 验证范围

原生测试共 32 项：

- 20 个预期结果直接来自同一固定 HarfBuzz 提交的 `.tests` 文件，逐字比较字形名、簇序号、偏移和步进；覆盖阿拉伯文归一化、希伯来文、孟加拉文连字/分解、韩文 Jamo 和默认忽略字符。不是用当前实现生成预期结果。
- 12 个集成场景检查 FreeType 版本、Unicode/缺失字形、内存字体、无效字体、HarfBuzz-FreeType 桥接、拉丁连字开关、阿拉伯文方向/连接、两种文字的实际栅格输出，以及 Brotli 空流、非空流和截断流。

测试字体和 Brotli 测试数据从固定官方归档选取，不使用用户字体或文档，也不把字体二进制上传到此仓库。栅格证据为 `fonts-raster.pgm`，逐项预期/实际结果为 `fonts-golden-results.json`。Brotli 解码通过不等于已验证 WOFF2 字体；当前没有 WOFF2 字体场景。

本机运行结果及 GitHub Actions 各自记录。字体组件测试不能代替真实 Office 文档排版、全套字体回退、完整图形工程链接或应用 GUI 验收。后续需补齐 HEIF 的 x265/libde265/libheif 构建闭包，再推进完整图形库。

FreeType 原 vendored 目录遗漏其引用的许可正文，已从官方 `VER-2-10-4` 对应提交补齐原文到 `licenses/fonts/freetype/` 并锁定来源与 SHA256。HarfBuzz、Brotli 的原始许可保留在选定输入中；各组件适用自己的许可。本阶段只公开源码与构建工具。
