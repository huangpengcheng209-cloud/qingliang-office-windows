# 可移植构建：首个原生组件

目前能够独立编译并运行的是公开源码中的 Windows 保存事务组件，不是整套办公应用。

## 需要什么

- Windows x64。
- Python 3.11+、Git。
- Visual Studio C++ Build Tools（包含 MSVC x64/x86 工具及 Windows SDK）。

不需要旧电脑的 Office 基线包、Qt、CEF、VLC、Boost 或 ICU。MSVC 环境通过微软的 vswhere 自动定位，也可用 `--vs-root` 明确选择已安装的 Visual Studio 根目录。脚本不安装工具、不下载编译器、不更改全局环境。

## 编译并运行

在仓库根目录运行：

```powershell
python tools/build_windows.py save-transaction --work-dir D:\CodexCache\qingliang-community-native
```

该命令校验公开源码，编译 `sources/desktop-sdk/ChromiumBasedEditors/lib/src/windows_save_transaction.h` 和 `tests/native/save_transaction_test.cpp`，随后执行 14 个原生测试。输出与临时文件全部写入指定目录；该目录需为空或带有此工具的专属标记，避免覆盖未知文件。构建锁会拒绝在同一目录并发执行。

结果记录在 `native-build-report.json`、`native-test-result.json` 和 `native-build.log`。报告含源码、测试及可执行文件的 SHA256。测试通过后仅清理本次创建的临时测试文件，保留构建输出；失败时保留现场，不自动覆盖未清理的测试目录。

14 个场景包括覆盖、新建 Unicode 路径、空内容、同文件/缺失输入、只读、硬链接和占用目标，以及读失败、写失败、刷新失败、替换失败、竞争创建与备份回滚。故障场景通过组件的测试接口注入；不代表真的制造磁盘故障或完成应用 GUI 验收。

GitHub Actions 的 `Windows native save component` 作业在新的托管 Windows 环境执行同一命令。这证明该独立组件可以脱离原基线编译运行，不代表完整编辑器可以一键构建，也不代表生成了安装包。

## 完整引擎仍缺什么

准备上游后，可以执行只读输入检查：

```powershell
python tools/build_windows.py engine-audit --source-root D:\CodexCache\qingliang-community-source\upstream\DesktopEditors --report D:\CodexCache\qingliang-community-engine-audit.json
```

也可以直接检查原冻结归档而不解压：

```powershell
python tools/build_windows.py engine-audit --source-archive D:\YourSources\Office-Windows-pinned-sources.zip --report D:\CodexCache\qingliang-community-archive-audit.json
```

这只是对八项已知输入的存在性检查，不是完整依赖解析器。即使八项都存在，也不会将完整应用标为可构建，因为历史构建编排、支持库来源与 VLC 对应源码仍有缺口。

原 win.22 冻结源码包含 kernel/shell 项目、zlib/libxml2 源码及 CEF 生成选择，但缺少 Boost 头文件、ICU 头文件和 UnicodeConverter 导入库。旧工作目录中的文件存在不代表归档包含它们。接下来需要把这些依赖从固定公开来源准备起来，并继续建立完整引擎的编译链；不得仅复制旧机支持库后称为完整源码构建。
