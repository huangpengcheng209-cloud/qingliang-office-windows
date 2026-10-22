# Windows 内核源码构建

本阶段构建固定 ONLYOFFICE core 提交的 `Common/kernel.pro` 所列 Windows Release 内核：47 个编译单元，包括文件、路径、线程、ZIP/zlib 和 XML/libxml2。`kernel.inputs.lock.json` 记录 213 个源码、头文件、工程参考和许可输入的 SHA256、编译宏、包含目录和系统链接库；不是完整办公引擎或 x2t 转换器。

需要 Python 3.11+、Git、7-Zip、带 Windows SDK 的 MSVC C++ Build Tools 和网络。新机器可直接运行：

```powershell
python tools/verify_sources.py
python tools/build_dependencies.py verify
python tools/build_kernel.py verify
python tools/build_kernel.py build --work-dir D:\CodexCache\qingliang-community-dependencies
```

最后一条命令先准备并构建锁定的 Boost/ICU/UnicodeConverter，再下载所需的 213 个内核输入；不克隆完整源码树。全部写入显式工作目录。已完成同版本依赖构建时，复用相同目录，核对依赖报告和产物哈希后构建内核；不要另开一份完整依赖构建树。

Boost/ICU 的来源与构建方式见 [DEPENDENCY-BUILD.md](DEPENDENCY-BUILD.md)。可选 `--archive-cache` 指定只读的归档缓存，`--source-cache` 指定只读的固定 core 源码缓存；每个被读取文件仍须匹配清单。工具不会修改缓存或旧应用，不会自动安装工具。遇到无法识别的已有源码修改、链接到工作目录外的路径或并发构建锁时停止。

编译直接使用 MSVC 与 Windows SDK。内核链接的是同一工作目录新生成的 `UnicodeConverter.lib`；测试确认 kernel、UnicodeConverter、ICU common/data DLL 实际从新输出目录加载。此步骤不需要 Qt 工具或运行时，也没有使用原 Office 基线 DLL；清单中保留上游 qmake 的宏和工程文件用于追溯。

## 原生验收与本批修复

22 项运行测试包括二进制文件、中文/emoji UTF-8、路径名、内存压缩、ZIP 创建/中文条目/解压、XML 文本/属性/实体、GBK 单双引号声明、UTF-16 BOM、缺失文件、空 XML、初次解析即失败的 XML，以及编码→文件→ZIP→XML 的同进程调用链。

首次 16 项测试中，GBK 单引号编码声明和损坏 XML 拒绝检查失败。调查发现两个上游问题，修复独立于冻结的 win.22 源码：

- `xmllight_private.h` 的编码识别只寻找双引号；改为匹配声明实际使用的单引号或双引号。
- `xmldom.cpp` 忽略首次读取失败，仍创建空名称节点；改为在首次读取失败时直接返回，不伪造根节点。

首次干净 Windows CI 中依赖构建通过，内核运行 17/18：中文 ZIP 条目读取失败。写入原先使用系统 OEM 代码页，无法表示的字符会丢失；读取也没有始终遵循 ZIP 的 UTF-8 标记。第三份独立修复让目录、单文件和内存写入统一使用 UTF-8 并设置 bit 11，读取按标记解码，无标记旧条目保留 OEM 回退。回归增加 emoji 文件名、外部 UTF-8/无标记样本、单文件和内存回调写读，本机最终 22/22。无标记旧条目仍依赖原有 OEM 代码页，不承诺跨语言恢复所有历史文件名。

完整修改文件、补丁及前后身份见 `kernel-sources/`、`kernel-patches/` 和清单。准备时先核对公开上游原文，再实际应用补丁，并逐一核对结果。原始 96 文件和五份累计补丁保持冻结身份。

XML API 仍不等同于严格格式校验器：读到部分节点后发生的错误，可能留下部分 DOM；本批没有宣称解决全部损坏 XML 的处理。

## 证据与边界

工作目录中生成 `kernel-build.log`、`kernel-test-result.json`、`kernel-build-report.json` 和 `kernel-imports.txt`，DLL、导入库和测试程序位于 `bin/`。成功场景清理自己新建的测试文件；失败时保留现场，下次运行拒绝覆盖非空测试目录，须先检查并归档证据。

GitHub Actions 的依赖作业在同一工作目录顺序构建依赖和内核，避免重复 ICU 构建；实际运行状态见 Actions。本机 Windows 22/22 通过。工具测试共 36 项，本机 35 项通过，符号链接创建检查因 Windows 权限跳过；Linux CI 可执行该项。

这证明内核基础库与新依赖的编译和所列原生场景。尚未构建 x2t、整套编辑器或安装包，未对新 DLL 执行应用 GUI 验收；原 Windows 应用的历史结果不能代替这些检查。本阶段仅发布源码。
