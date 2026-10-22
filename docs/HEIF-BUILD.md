# HEIF 编解码前置库

本阶段按固定 ONLYOFFICE `build_tools` 的 Windows HEVC 静态库配置，从源码构建 x265、libde265 和 libheif，不复用原 Office 基线二进制。源码清单为 `heif.inputs.lock.json`，包含三个官方归档的 SHA256 和全部 994 个文件身份；来源、适配和修改后字节均可核对。

| 库 | 固定源码 | C/C++ 编译单元 |
| --- | --- | --- |
| x265 4.1 分支 | `32e25ffcf810c5fe284901859b369270824c4596` | 52 |
| libde265 1.0.16 | `7ba65889d3d6d8a0d99b5360b028243ba843be3a` | 61 |
| libheif 1.18.2 | `bf35e9eb25af8f2b7917996ad9ba849d922f8d15` | 39 |

单元数来自 CMake File API 的 Release 编译模型，按源文件去重，不含 Windows 资源文件。采用 Visual Studio 2022 x64、Release、动态 MSVC 运行时 `/MD`，需要 CMake **>=3.21、<4**；优先使用 VS2022 自带 CMake，当前本机版本为 3.31.6。静态库的默认运行库指令已在本机核对为 MSVCRT。

## 来源和两份独立补丁

上游脚本选择的是 x265 `Release_4.1` 分支，并非同名标签。本仓库锁定该分支的具体提交，保留归档自带 `x265Version.txt` 原文；其中嵌入的显示版本不是源码提交身份。`heif-patches/x265-version.patch` 复现上游已有适配，让版本文件优先于 Git 状态。完整文件位于 `heif-sources/`。

本批新增 `libheif-ycbcr-preservation.patch`：上游对已解码的 YCbCr 图像，即使调用者也请求 YCbCr，仍先转 RGB 再转回，导致样本像素丢失。补丁让该路径保留原 YCbCr 平面；RGB 输出、缩略图及透明图像仍执行相应路径。完整 `context.cc` 保留原作者、LGPL 声明和修改日期。

上游脚本中的 `heifio` 替换在固定 libheif 1.18.2 上没有对应目录，按实际源码记录为空操作；文档生成通过 CMake 的 `CMAKE_DISABLE_FIND_PACKAGE_Doxygen=ON` 禁用，避免改写控制块。没有以删掉图形功能的方式处理构建缺项。

## 构建命令

```powershell
python tools/build_heif.py verify
python tools/build_heif.py build --work-dir D:\CodexCache\qingliang-community-publish\dependency-build
```

需要 Python 3.11+、Git、带 Windows SDK 和 CMake 工具的 VS2022。可通过 `--cmake` 指定符合范围的 CMake，`--source-cache` 只读复用固定 core 文件，`--archive-cache` 只读复用归档；均核对哈希，不自动安装工具。

沿用同一依赖工作树：源码位于 `sources/core/Common/3dParty/heif/` 下，CMake 输出在各组件的 `build/win_64/release`，与上游 `heif.pri` 布局相符。公共 `.build.lock` 防止同时构建。现有未知修改、不同项目的 CMake 工作目录以及未检查的测试现场均保留并停止。测试现场非空时需先检查，不能直接覆盖；不需要复制整个源码树重试。

## 实际验证

16 项原生场景覆盖版本、静态 HEVC 编码器/解码器、x265 选择、图像平面创建、无损编码、写入失败传播、HEIC 容器写读、尺寸/主图、YCbCr 全部字节、EXIF/XMP、透明度、缩略图、上游 1280×854 HEIC、截断输入、非法 box 大小和缺少 AV1 解码器时的失败状态。

首次为 14/16：一项断言错误地要求编码中的 handle 立即反映元数据列表，改为检查写入失败传播；元数据仍在序列化后逐字节核对。另一项确为 YCbCr 像素损失。直接 libde265 解码及 FFmpeg 独立解码均与输入相同，定位到 libheif 中间颜色转换后修复；最终本机 16/16。另用本机 FFmpeg 8.1 核对自生成的 96×80 无损 HEIC，全部 11520 字节与输入及新库解码结果相同。该独立 FFmpeg 比对是本机额外证据，未作为云端工具安装或测试承诺。

日志和结果位于工作目录的 `heif-build.log`、`heif-build-report.json`、`heif-test-result.json`；图像及原始平面在 `heif-fixtures/`，首次失败现场另行保留。输入只使用人工生成图像和固定官方样本，不读取用户图片。

本配置保留上游 `release-noplugins` 选择和其 AOM 禁用项：提供 HEVC 编解码，不提供该库的 AV1/AVIF 解码器；测试明确检查失败状态。尚未验收所有 HEIC 变体、HDR/10-bit、完整图形库链接或应用图片导入。不能把本批静态库测试当作完整 Office 或 GUI 验收。

x265、libde265、libheif 及其子组件各自保留原许可，正文列入归档清单；修改不改变第三方原许可。本阶段只公开源码、补丁与工具，不分发新静态库或安装包。
