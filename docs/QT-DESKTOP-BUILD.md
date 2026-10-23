# Windows Qt 桌面集成开发预览

本阶段将真实工作台接入新编译的 Qt 主程序和 CEF 原生宿主。它包含桌面窗口、起始页和原生接口的检查；完整编辑区资源、实际文档编辑保存、媒体播放和安装验收仍待完成。

## 构建

先按 [HOST-BUILD.md](HOST-BUILD.md) 在同一个有标记的稳定目录完成原生宿主，再构建 [WORKBENCH-QUALITY.md](WORKBENCH-QUALITY.md) 的真实工作台。安装与锁匹配的官方 Qt 5.15.2 `msvc2019_64` SDK，继续使用 VS 2022 与 Windows SDK：

```powershell
python tools/build_qt.py verify
python tools/build_qt.py build --rebuild --work-dir D:\CodexCache\qingliang-community-build --qt-dir D:\Qt\5.15.2\msvc2019_64
python tools/launch_qt_preview.py --work-dir D:\CodexCache\qingliang-community-build --qt-dir D:\Qt\5.15.2\msvc2019_64 --gui
```

`--archive-cache` 可指定已有官方下载缓存。使用原 staging 的源文件、对象和依赖目录；`--rebuild` 在该目录重编译对象，不创建新的完整源码副本。已有未知源文件修改会被保留并拒绝继续。不要在预览窗口仍运行时重建或覆盖它所加载的 DLL。

构建顺序是播放器 23 单元、Qt 包装 10 单元、浏览器助手 1 单元、主程序 69 单元，共 103 单元。`qt.inputs.lock.json` 锁定额外桌面源码、VLC 源码/运行包、Qt SDK 文件及编译器实际使用的输入；Qt 生成的 moc/rcc 输入单独记录哈希。输出与审计在 `qt-build-report.json`。原生宿主 280 单元的结果另见 `host-build-report.json`。

Qt SDK 和 VLC/CEF 运行库使用固定预编译官方材料；本阶段没有重新编译 Qt、VLC 或 Chromium，也不宣称它们所有静态依赖、下游补丁和分发源码材料已闭合。Qt 完整对应版本源码归档的身份见锁文件。VLC 后端保持启用，从 VLC 3.0.21 源码中的 `lib/libvlc.sym`、`src/libvlccore.sym` 生成 MSVC 导入库；没有从旧 Office DLL 的导出表生成导入库，也没有链接源码包夹带的旧 VLC `build/win_64` 材料。播放器构建成功不代表播放、音视频同步或放映验收通过。

## 独立配置和窗口通信

`qt-sources/`、`qt-patches/` 的四份后续修改独立于冻结的 96 文件和五份累计补丁：

- 显式绝对路径 `QINGLIANG_SETTINGS_FILE` 将用户 QSettings 写入指定 INI；未设置或为相对路径时沿用原配置位置。
- 该独立配置路径也区分单实例互斥量和消息接收窗口，避免验收进程向普通实例投递消息。
- `OFFICE_USER_DATA_ROOT` 与设置路径使用 Windows Unicode 环境变量读取。
- 重复启动通过 `FindWindowExW(HWND_MESSAGE, …)` 找到真实消息窗口，并检查限时投递和接收结果；避免原 `FindWindow` 无法找到消息窗口的问题。

另有 `host-patches/native-bridge-reinit.patch` 修复真实主题切换时重复初始化桥接属性导致的 `Cannot redefine property: CryptoMode`：复用既有访问器，保留其不可重新配置属性，不放宽描述符权限。

启动工具校验当前主程序、宿主 DLL 和真实首页构建报告，将 CEF DLL 和资源放在同一运行布局，再以 D: 下独立数据、缓存、设置和临时目录启动。第一次运行发现的 CEF 早期退出来自资源与模块目录不一致，调整运行布局后再做窗口检查。浏览器助手、宿主和工作台均是本次构建，首页原生接口没有注入测试替身。

## 验证与剩余工作

在独立预览窗口仍运行时安装 `playwright==1.55.0`，用验证环境运行：

```powershell
python tests/run_qt_desktop_tests.py --work-dir D:\CodexCache\qingliang-community-build --qt-dir D:\Qt\5.15.2\msvc2019_64 --evidence-dir D:\CodexWorkspaces\qt-desktop-evidence
```

本机 16/16 检查通过，包括真实原生函数调用、原生最近列表、快捷键、筛选、减少动效、真实明暗主题和 INI 持久化、重复启动的消息投递，以及桥接重复初始化。Qt 实际读取的 543 个固定输入、479 个工具链头文件及 40 个生成输入分开审计。结果 JSON 记录主程序/首页哈希、运行进程、浏览器版本和截图。界面截图是实际嵌入式 CEF 页面，不代表所有原生对话框或编辑区已验收。

接下来需准备完整桌面 SDKJS/web-apps、空文档模板、词典、插件及其他运行资源，逐项验证 DOCX/XLSX/PPTX/PDF 的新建、打开、输入、保存、重开与失败恢复，再完善编辑区、原生窗口、设置及状态动效。完整范围见 [PRODUCT-QUALITY-PLAN.md](PRODUCT-QUALITY-PLAN.md)。没有发布可安装应用，也不能把此开发预览当作完成的软件。
