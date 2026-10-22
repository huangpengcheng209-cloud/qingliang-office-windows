# 固定依赖与 UnicodeConverter 构建

这是 Boost/ICU 源码准备，以及 ICU 74.2 和 UnicodeConverter 的独立编译流程，不是完整编辑器或安装包构建。

## 固定输入

`dependencies.lock.json` 固定以下公开输入：

| 输入 | 版本/来源 | 用途 |
| --- | --- | --- |
| Boost | 官方 1.72.0 `.7z` 源码归档及 SHA256 | 准备头文件/源码，并编译运行算法测试；本批未编译 Boost 的全部二进制库 |
| ICU | unicode-org/icu 官方 74.2 Windows 源码 ZIP 及 SHA256 | MSBuild 编译 ICU common、i18n 及 genccode 依赖 |
| ICU 数据 | 同一源码归档自带 `icudt74l.dat` | 由 genccode 生成对象并链接数据 DLL；未重新生成上游全部 Unicode 数据 |
| UnicodeConverter | 主源码锁定的 ONLYOFFICE/core 提交中的四个文件 | MSVC 编译 DLL 与导入库 |
| UTF-32 容量修复 | `dependency-patches/` 的单独补丁及 SHA256 | 修复含补充平面字符时解码缓冲区不足；完整修改文件见 `dependency-sources/` |

依赖归档从官方地址获取，校验后解压。第三方原始源码和许可随原归档保留在工作目录中。本流程不复制旧机 Office DLL，不替换原应用运行库。

## 执行

需要 Windows x64、Python 3.11+、Git、7-Zip，以及带 Windows SDK 的 MSVC C++ Build Tools。MSVC/MSBuild 通过 vswhere 自动定位；本工具不安装软件或更改全局环境。

```powershell
python tools/build_dependencies.py verify
python tools/build_dependencies.py build --work-dir D:\CodexCache\qingliang-community-dependencies
```

已有归档时，可以指定只读缓存以避免重复下载：

```powershell
python tools/build_dependencies.py build --work-dir D:\CodexCache\qingliang-community-dependencies --archive-cache D:\YourArchives
```

工作目录固定复用，仅保留一套 Boost 和 ICU 提取源码及增量构建结果。专属标记和构建锁拒绝未知非空目录及并发构建。解压前检查路径和链接；校验失败不会覆盖现有输入。编译器/测试日志写入 `dependency-build.log`，结果和哈希写入 `dependency-build-report.json`，来源写入 `source-preparation-report.json`。

脚本只构建 ICU solution 中 genccode 所需的依赖，不构建完整办公应用。然后使用该归档自带的数据生成新的 `icudt74.dll`，编译 `UnicodeConverter.dll` 和 `.lib`，并执行 14 项原生测试。包括 UTF-8、中文 GBK、日文 Shift-JIS、Windows-1251/1252、UTF-16/32 大小端、emoji、空字符串、SASLprep 数据与 Boost 头文件算法。

## 本批发现与修复

第一次独立测试 12/14 通过；UTF-32LE/BE 的 emoji 往返失败。上游代码用输入字节数除以最小编码字节数作为 UTF-16 输出容量，UTF-32 的非 BMP 字符却需要两个 UTF-16 单元，导致容量不足。

2026-10-22 的单独补丁将两个解码入口改为使用输入字节数作为所测编码的保守 UTF-16 容量。补丁、原始文件哈希、修改结果哈希和完整修改源码均公开，且与原 win.22 的 96 文件冻结清单分开。修复后本机 14/14 通过；旧失败日志仍保留。该组件有代码变化，不能沿用原安装版的历史验收作为当前完整应用通过的证据。

## 与完整引擎的关系

新工作目录提供 Boost 头文件、ICU 头文件以及源构建的 UnicodeConverter 导入库，可在输入审计中单独列出：

```powershell
python tools/build_windows.py engine-audit --source-root D:\CodexCache\qingliang-community-source\upstream\DesktopEditors --dependency-work-dir D:\CodexCache\qingliang-community-dependencies --report D:\CodexCache\qingliang-community-engine-audit.json
```

这不会把依赖自动写回旧源码树，也没有完成完整 qmake 工程路径接线。Qt、CEF、其他原生支持库、完整 desktop 构建编排、VLC 历史补丁/静态依赖对应、应用 GUI 与安装验收仍未完成。新 DLL 仅作为开发验证输出，暂不发布应用安装包。

官方来源：[Boost 1.72.0 归档](https://archives.boost.io/release/1.72.0/source/)、[ICU 74.2 Release](https://github.com/unicode-org/icu/releases/tag/release-74-2)、[ICU Windows 构建说明](https://unicode-org.github.io/icu/userguide/icu4c/build.html)。
