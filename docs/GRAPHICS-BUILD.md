# Windows 完整绘图库源码构建

本阶段从固定 ONLYOFFICE core 提交构建 `graphics.dll` 的全部 **515 个 C/C++ 单元**，链接此前源码构建的 kernel、UnicodeConverter、Boost.Regex/DateTime 和 HEIF 静态库。保留字体、图片、SVG、WMF/EMF 和断字支持，不使用旧 Office 基线库。这里的“完整”指固定 Windows 绘图工程的 C/C++ 编译和链接范围；尚未生成 x2t、桌面应用或安装器。

## 输入与适配

`graphics.inputs.lock.json` 固定 1853 个 core 文件、260 个 Boost 输入、生成的 HEIF 版本头及 Katana/Hyphen 两个支持归档的 231 个文件。字体和 HEIF 依赖继续使用各自输入清单，其清单 SHA256 也被锁定。原 win.22 的 96 个修改文件保持原始字节，绘图使用其中的 `agg_basics.h`，并核对其冻结清单身份。

Windows x64 Release 源文件、宏、包含目录及系统库来自固定上游 qmake 工程展开结果。早期展开的 509 单元并不完整：Katana 源目录不存在时，`$$files()` 会静默返回空值。补齐固定 Katana 后确认 515 单元；Hyphen 的 C 实现由字体模块直接包含，不另算单独编译单元。两个同名 `CPath.cpp` 使用不同对象目录，避免覆盖。清单采用 Git 中的真实大小写，包含上游工程大小写不同的 `cwmfinterpretator.cpp`。

- Katana：`jasenhuang/katana-parser@be6df458d4540eee375c513958dcb862a391cdd1`，版本来自固定 core 的获取脚本；复现原脚本的 tokenizer、parser、foundation 适配，差异与完整文件独立公开。
- Hyphen：`hunspell/hyphen@c299444629416f90625a2e56fdfc4efdca131ecc`。固定 build_tools 的脚本原本克隆浮动 HEAD，本阶段将取得的源码固定到该提交及归档 SHA256，未将其宣称为 2.8.8 标签。算法未修改。
- HEIF 图形适配：读取辅助 Alpha 平面，修复透明度被统一写成 255。
- SVG：实现原来总是失败的内存加载入口，与文件加载共用既有编码转换与解析路径。

后两项修复位于 `graphics-patches/`、`graphics-sources/core/`，Katana 适配位于同目录的独立补丁及 `graphics-sources/katana/`。Katana MIT 原文和 Hyphen 的许可及例外说明见 `licenses/graphics/`；各自许可继续适用。

## 构建

需要 Python 3.11+、Git、带 Windows SDK 的 **VS2022 x64 C++ Build Tools**，HEIF 阶段还需要 CMake 3.x。使用一个稳定的工作目录，先按 DEPENDENCY-BUILD、KERNEL-BUILD、X2T-DEPENDENCIES、NETWORK-CRYPTO-BUILD、FONT-BUILD、HEIF-BUILD 顺序完成前置构建；网络和加密供后续转换器使用，绘图 DLL 不直接链接它们。然后执行：

```powershell
python tools/build_graphics.py verify
python tools/build_graphics.py build --work-dir D:\CodexCache\qingliang-community-publish\dependency-build
```

可用 `--archive-cache` 指定只读归档缓存，`--source-cache` 指定固定 core 源码缓存。编译直接使用 MSVC，不要求安装 Qt。qmake 仅用于整理阶段读取原工程配置。构建使用 `/MD`，运行需要 MSVC 动态运行时；没有 Qt DLL 导入。工具拒绝未知非空工作目录、未知源码修改和并行占用，保留已有测试输出供检查。

编译器 `/sourceDependencies` 为每个单元生成实际读取清单，覆盖范围须与 515 单元集合完全一致。所有项目、归档及 Boost 头文件重新核对 SHA256，其余头文件须位于已定位的 MSVC 或 Windows SDK 目录。本机核对 1438 个锁定头文件和 332 个工具链头文件；后者数量可随 SDK 版本变化。链接后通过 `dumpbin /DEPENDENTS` 检查 DLL 导入和新输出的依赖身份。

## 21 项原生运行检查

测试实际加载新绘图 DLL，覆盖工厂/BGRA 目标、矩形/描边、透明混合、仿射变换和奇偶填充；PNG 中文/emoji 文件路径与逐像素读回、JPEG 有界误差、BMP、缩放、内存 PNG、坏图片拒绝和格式检测；官方 HEIC 样本导入及自生成 HEIC 的每像素 Alpha；固定 Latin 字体、通过绘图 DLL 的 HarfBuzz RTL 字形与位置桥接并栅格输出阿拉伯文；SVG CSS 样式解析、Windows GDI 生成的 EMF 解析、精确蓝色像素及白色背景核对，以及 Hyphen 内存词典和断字。

首轮 13/20，既有接口坐标、颜色及行方向断言不准确，也暴露上述两个实际缺陷；校正接口断言并修复缺陷后，增加桥接/断字覆盖，最终 21/21。失败输出单独保留。人工查看过绘图和文字输出，未据此宣称 Office 文档排版或应用 GUI 验收通过。

检查样本还发现测试调用 EMF 绘制时遗漏 `SetSwapRGB(false)`，未采用产品自身栅格导出的颜色设置，蓝色被写成红色。按原有调用约定配置后，增加蓝色像素及白色背景断言，21 项重新通过；没有为此修改厂商绘图代码。

工作目录内保留 `graphics-build.log`、`graphics-build-report.json`、`graphics-compiler-inputs.json`、`graphics-runtime-imports.json`、`graphics-test-result.json`、原生输出和生成样本。GitHub Actions 在同一 Windows-2022 工作目录顺序构建全部前置库及绘图 DLL，并执行相同 21 项场景。

## 范围

本批不分发 DLL 或安装包，不代表全部第三方版本、安全性、所有 SVG/HEIC/WMF 变体或真实 Office 文档兼容性已经验收。AV1、HDR/10-bit 和 WOFF2 的既有未测范围保留。下一阶段继续闭合格式解析/转换库，编译 x2t 并使用实际文档验证，再推进桌面应用和安装器。
