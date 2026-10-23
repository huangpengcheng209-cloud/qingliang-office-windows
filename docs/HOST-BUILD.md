# Windows 原生编辑宿主 DLL

2026-10-23：已编译并链接 `ascdocumentscore.dll` 的全部 280 个原生单元，另源码构建 Boost.Filesystem 10 单元与 Boost.System 的原固定兼容导出单元。22 项原生接口/文件系统检查通过；实际 CEF 浏览器初始化、Qt 界面、文档编辑保存和安装均未据此验收。

## 构建入口

先完成 [CONVERTER-BUILD.md](CONVERTER-BUILD.md) 的支持库和完整 x2t 构建，在同一个有标记的目录继续：

```powershell
python tools/build_host.py verify
python tools/build_host.py build --work-dir D:\CodexCache\qingliang-community-build
```

需要 Windows x64、Python 3.11 以上、Git、Visual Studio 2022 C++ Build Tools 和 Windows SDK。此入口直接调用 MSVC，不要求本机安装 Qt；工程选择来自固定 qmake 项目及 CEF 工程清单，已锁定在 `host.inputs.lock.json`。`--archive-cache` 可指定只读下载缓存，`--vs-root` 可指定 VS 根目录。

构建复用原依赖目录和 `.build.lock`，不创建新的完整源码副本。先核对已构建的转换器支持 DLL，再准备固定宿主源码；自动确保 Hunspell 原生组件可用，随后编译 Boost、宿主 DLL、实际输入审计及原生测试。输出在 `bin/`、`lib/`、`host-build/` 和 `host-boost-build/`，报告为 `host-build-report.json`、`host-compiler-inputs.json`、`host-test-result.json` 及对应日志；失败不会保留本轮成功报告。

## 来源与修改

- desktop-sdk 提交与主上游锁相同，保留冻结覆盖；匹配 CEF 为 150.0.22 / Chromium 150.0.7871.256。179 个 CEF wrapper 单元、78 个 client 工具单元与其余 23 个宿主/支持单元全部编入，不通过删减保护、签名、插件、打印或渲染功能绕过依赖。
- 使用固定官方 CEF Windows SDK 的真实 `libcef.lib` 和运行库；CEF wrapper/client 源码由本次编译。**Chromium/CEF 运行库没有从源码重建**，也未宣称其全部对应源码/构建依赖已闭合。
- 其他 Office 支持 DLL 来自前序社区源码构建，没有复制旧 Office DLL，也未用旧 Office 的 DLL 导出表制造导入库。完整转换器报告的支持库哈希在构建前重新核对。
- 新增 `host-sources/`、`host-patches/` 独立于原 96 文件和五份累计补丁。CEF client 构造适配保持原历史适配行为，避免在基类构造中访问尚未构造的 Office self delegate；这不是本次新发现的缺陷。
- 本次新修复 `GetFileFormatByExtentionForSave` 对大小写敏感的问题。原 DLL 下新增的两项 `.DOCX/.XLSX/.PPTX` 和 `.PdF` 检查失败，修复后全部通过；仅规范化用于判断的扩展名，不改写用户文件名和路径。完整修改基于冻结父版本，保留原版权、许可、BOM 和换行。
- 初次编译发现此前转换器准备目录未包含词典索引 `records.h`；该文件与生成脚本原本就在固定 core 归档中，现按原始字节准备，没有用空索引替代。

## 验证范围

本机宿主实际编译读取的 1,524 个固定源码/头文件输入已核对；工具链头文件单独记录。Boost 新使用的源码/头文件与固定 Boost 归档核对，ICU 头文件与固定源码 ZIP 核对。源文件路径、归档哈希、额外 core 输入、Boost/ICU 输入及独立修改均记录在锁中。

原生测试真正加载新 DLL、CEF 运行库及新绘图/PDF 依赖，调用导出的配置、DPI 计算和格式识别接口，并执行 Windows/Boost 中文与 Emoji 路径的创建、复制、遍历、缺失源错误和删除副本保留原文件。它验证 DLL 加载和接口边界，**没有启动 CEF 浏览器或 Qt 窗口**；125%/150% 检查是计算接口检查，不能作为桌面实际缩放验收。

本机 22/22 原生场景通过；工具检查 128 项中 127 通过、1 项因 Windows 符号链接权限跳过。云端完整支持链后的宿主重建以对应提交 Actions 结果为准。

## 接下来的桌面集成

后续 Qt 集成已构建 `editors_helper.exe`、Qt 包装、保留 VLC 后端的播放器与 `DesktopEditors.exe`，并将真实工作台接入宿主；16 项实际窗口检查通过，另修复主题切换时桥接属性的重复定义。见 [QT-DESKTOP-BUILD.md](QT-DESKTOP-BUILD.md)。桌面 SDKJS/web-apps、词典、插件等完整载荷和编辑保存仍待完成；播放器还未做实际播放回归。

Qt/CEF/VLC 对应材料及分发条件、实际编辑保存、播放/放映、打印、安装卸载与文档保留仍待完成。完整目标见 [PRODUCT-QUALITY-PLAN.md](PRODUCT-QUALITY-PLAN.md)。本批仅发布源码和构建工具，没有发布应用安装包。
