# 桌面构建前置：原生拼写检查

2026-10-23：已源码构建桌面宿主所需的 `hunspell.dll` 和真实导入库，10 个原生编译单元全部保留，22 项实际词典操作通过。当前没有生成新的 `ascdocumentscore.dll`、Qt 界面或安装包。

## 构建命令

需要 Windows x64、Visual Studio 2022 C++ Build Tools、Windows SDK、Git 和 Python 3.11 以上。复用此前依赖构建目录，不需要旧版 Office、Qt、CEF、预制导入定义或应用 DLL；也可从一个空的明确指定目录独立运行本阶段。

```powershell
python tools/build_desktop.py verify
python tools/build_desktop.py build --work-dir D:\CodexCache\qingliang-community-build
```

`--archive-cache` 可指定只读 ZIP 缓存；不存在时从固定 URL 下载并核对 SHA256。构建目录必须为空或具有前序社区依赖构建标记，全程持有同一 `.build.lock`。源码、对象、词典夹具和临时文件均位于指定目录，未知已有源码修改会被拒绝并保留。

输出为 `bin/hunspell.dll`、`bin/hunspell.lib`、`bin/desktop-spelling-test.exe`，以及 `desktop-build-report.json`、`desktop-compiler-inputs.json`、`desktop-test-result.json`、`desktop-build.log` 和导入表。脚本失败不会留下本轮成功报告。

## 固定输入与适配

`desktop.inputs.lock.json` 固定 core 的 `HEAD`、`before.py` 和两份 qmake 项目；Hunspell 提交为 `8a2fdfe5a6bb1cbafc04b0c8486abcefd17ad903`，36 个源码、头文件和声明输入按文件哈希锁定。编译源列表与上游 `qt/hunspell.pri` 逐项对照。

`desktop-sources/hunspell/` 和 `desktop-patches/` 单独公开固定 `before.py` 的三项既有适配：WASM 内存流条件成员、可配置建议词超时，以及保留进程级 Unicode 表的生命周期处理。本次移植日期为 2026-10-23；这些是上游已有行为，并非本次新发现或新修复的问题。Unicode 表适配保留其原有进程生命周期占用，本阶段未做并发或长时间内存压力验收。原冻结 96 文件及五份累计补丁不变。

MSVC `/sourceDependencies` JSON 审计实际读入的 28 个固定源码/头文件，另外记录编译器和 Windows SDK 的头文件数量。任何来源不在清单或工具链目录内的第三方头文件均使构建失败；中文与英文编译器界面使用同一审计方式。

Hunspell 原作者及许可声明保持不变；固定归档包含 `COPYING`、`COPYING.LESSER`、`COPYING.MPL`、`license.hunspell`，仓库的 `licenses/hunspell/` 提供这些声明的原始字节副本。不得将其声明为本项目原创。

## 实际测试范围

测试使用自行编写的微型 `.aff` 和 `.dic` 文件，经真实 DLL 的公开 C 接口加载。覆盖正常单词/错词、前后缀与交叉词缀、中文、重音字符及大写、禁止词、建议词内容与释放、词干、运行时增删/继承词缀、额外词典、多实例隔离、销毁另一个实例后继续检查、64 次 UTF-8 引擎创建销毁、单字节词典和编码隔离，以及重建后不保留运行时修改。

本机结果为 22/22；它不代表完整多语言词库已集成，也不代表桌面输入提示、线程安全或 GUI 已验收。CI 另有 Windows 原生拼写作业；以相应提交的 Actions 结果为准。

## Qt、CEF 复核与下一段

`desktop.prerequisites.json` 记录本次重新核对的材料身份：Qt 5.15.2 完整源码归档；CEF 150.0.22 / Chromium 150.0.7871.256 的最小 SDK 归档和匹配 CEF 源码归档。已重新计算哈希，并从 CEF SDK 的生成头文件核对版本和提交；没有据此宣称已重建 Qt/Chromium 或闭合 Chromium 全部源码依赖。

下一段按固定工程依赖先生成 `ascdocumentscore.dll` 及匹配的 CEF wrapper/client 工具，再处理 `qtascdocumentscore.dll`、原选定后端的播放器、`DesktopEditors.exe`、桌面 SDKJS/web-apps 资源及安装载荷。完整转换器的 SDKJS builder 脚本不能代替桌面编辑资源。桌面宿主还需要 PDF/XPS/DjVu、签名和渲染器等 DLL 的真实源码链接输出；不得用旧应用导出表制造导入库来掩盖缺项。

Qt 工具/模块与运行库对应、VLC x64 下游补丁/依赖版本及后端选择、插件/OCR/词典载荷仍需逐项核清。新桌面程序构建后，再独立执行编辑、保存重开、转换、安装卸载及文档保留验收。
