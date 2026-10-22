# x2t 第一组前置库

本阶段构建 x2t 直接需要的 `CompoundFileLib`，以及 Boost.Regex 和 Boost.DateTime。它们分别提供 OLE 复合存储、正则表达式和日期时间能力。固定的 x2t 工程声明了 13 个静态库和 17 个动态库直接依赖；本批只完成其中一组前置库，不是完整转换器。

## 构建

需要 Python 3.11+、Git、7-Zip、带 Windows SDK 的 MSVC C++ Build Tools 和网络：

```powershell
python tools/build_x2t_dependencies.py verify
python tools/build_x2t_dependencies.py build --work-dir D:\CodexCache\qingliang-community-dependencies
```

使用与 ICU/内核阶段相同的工作目录。首次运行会先准备并构建已有依赖与内核；已有同版本成功报告和匹配产物时复用，不再构建 ICU/内核。随后只下载这组库需要的 49 个固定 core 文件，核对 Boost 源码输入，编译 17 个 Regex、3 个 DateTime 和 13 个 CompoundFileLib 单元。源码/工程/许可身份见 `x2t.inputs.lock.json`，Boost 官方归档来源沿用 `dependencies.lock.json`。

可选 `--archive-cache` 和 `--source-cache` 指定只读缓存，每个输入仍须核对 SHA256。工具只写显式工作目录，遇到未知修改、不同源文件哈希、并发锁或未检查的失败测试现场时停止；不改动原应用或旧源码树。

这里直接以 MSVC 编译上游 Jamfile/qmake 所列源文件，使用 x64、Release、`/MD`，关闭 Boost 自动链接。输出为 `lib/boost_regex.lib`、`lib/boost_date_time.lib` 和 `lib/CompoundFileLib.lib`，测试程序显式链接这些路径。不会把当前 MSVC 产物改名为旧 `vc142` 文件；完整 x2t 构建仍须配置对应链接路径并独立验收。Regex 的可选 ICU 扩展没有启用，本批不声明 `boost::u32regex` 可用；宽字符串测试使用 `boost::wregex`。

## 原生测试及修复

21 项测试包括 Regex 捕获/替换/非法表达式/中文宽字符，闰日/跨日/非法日期，复合流的 63、4095、4096、100000 字节边界、空流、中文/emoji 嵌套存储、缩短和覆盖、重命名/删除、更新提交、非法签名、只读提交拒绝及文件字节保留。

另以 Windows 自带的 `IStorage`/`IStream` 交叉验证：Windows 读取库生成的 v3 小流/大流和 v4 文件；库读取 Windows 生成的中文命名流；更新提交后的内容同时由双方核对。样本流是测试字节，不是实际 DOC/XLS/PPT 文档，不能据此宣称这些格式已完成转换。

首轮 10/21，通过的 Windows 读取检查帮助区分写入和读取问题。单独修复后 20/21，最后定位更新提交遗漏扇区。两份补丁覆盖三个问题：

- `GetData` 把 `reserve` 改为实际设置缓冲区长度的 `resize`，修复读取结果为空。
- 跨扇区读取使用累计已读字节作为目标偏移，补齐尾段索引边界检查，避免中间块覆盖。
- `Commit` 遍历实际扇区数，替代扇区分组数，写回全部修改扇区。

修改日期和原许可保留。补丁、完整修改源码及前后哈希分别见 `x2t-patches/`、`x2t-sources/` 和清单，独立于 win.22 的原 96 文件冻结身份。准备时先核对固定上游原文，再实际应用补丁并核对结果。空流通过新建空流测试；`SetData` 的非空输入前提保持原有行为。

## 证据与后续

本机 21/21 原生测试通过。构建/源码工具共 42 项测试，本机 41 项通过，符号链接检查因 Windows 权限跳过；Linux CI 可执行该项。GitHub Windows 作业顺序构建依赖、内核和本批前置库，实际状态见 Actions。

日志和结果位于工作目录的 `x2t-dependencies-build.log`、`x2t-dependencies-test-result.json` 和 `x2t-dependencies-build-report.json`。成功场景清理自己创建的文件，失败现场保留，重试前须先检查并归档。

尚需继续构建图形、网络、格式解析/渲染和其他支持库，并接入完整 x2t 工程。新增三个静态库没有替换原应用文件。本阶段只发布源码，未构建 x2t 可执行文件、整套编辑器或安装包，也未完成真实办公文档的转换或 GUI 验收。
