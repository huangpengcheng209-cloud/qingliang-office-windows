# VBA 与文本格式前置库

本阶段构建固定 Windows 工程的 `VbaFormatLib`（4 个 C++ 单元）和 `TxtXmlFormatLib`（7 个单元），另编译 POLE 与 Unicode 工具两个支持单元，共 13 个单元。两个完整静态库均已生成；原生程序实际链接并运行底层 VBA 流解析和文本读写接口。

**完整 VBA 转 XML 和 TXT↔DOCX 尚未链接验收。** 前者仍依赖路径、命名空间、ActiveX 等 OOXML 支持，后者依赖 DOCX 格式库。本阶段不执行宏，不将静态库生成等同于完整 x2t 或应用构建。

## 固定输入

`formats.inputs.lock.json` 锁定 core 提交、561 个源码/头文件/工程输入和 872 个 Boost 1.72.0 输入。源文件、宏来自固定工程展开结果；直接使用 MSVC x64 `/MD` 编译，不依赖 Qt 运行库或旧 Office 支持库。

选定输入中的 6 个原 win.22 修改文件使用 `sources/` 的冻结字节：POLE 实现、`agg_basics.h`、DOCX→TXT 的源码与头文件、文本 File 实现和 TxtXmlFile。新修复独立放在 `format-sources/` 与 `format-patches/`，不改写原 96 文件清单。

POLE 和 Unicode 支持实现原本列在 DOCX 工程中，测试为其单独生成支持静态库，后续链接完整 DOCX 库时须避免重复定义。POLE 原作者和许可正文保留于源文件；本批未修改其冻结版本，也未将其许可改成主程序许可。

## 修复与运行检查

首轮 32 个隔离子进程场景为 21 通过、11 失败；零对齐和截断 VBA 头分别产生整数除零、访问异常，原始退出码与样本保留。新增两份补丁、三个完整修改文件：

- `vba-stream-bounds.patch`：先定位模块偏移再读取压缩标记；限制块、复制令牌及输出范围，完整解码成功才交付结果，临时数据使用自动释放的容器；允许恰好读至末尾，避免跳过、回退和对齐运算溢出，处理零对齐。
- `text-io.patch`：空读和失败读取前重置行数，大端写入使用独立字节缓冲，不再改动传入的常量字符串。

解压实现核对 Microsoft 的 [MS-OVBA 块头](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ovba/ec1bc788-27de-47d9-8db4-6be2b5cff52b)、[块解压流程](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ovba/3d5ea4df-e8a5-4079-a454-9595b840525f)及[复制令牌位宽](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ovba/220bde4c-02b5-41ef-9f9a-8608718ce913)。这不是完整 VBA 文件格式一致性认证；非法签名或不完整的压缩块会返回空结果，旧代码对部分坏数据的恢复行为不作兼容承诺。

修复后原 32 场景通过，再增加位宽变化、解压块上限、越界模块偏移及末尾块读取四个场景，最终 **36/36**：16 个文本场景覆盖 UTF-8 BOM/无 BOM、UTF-16LE/BE、GBK、中文/emoji、空行和混合换行、重复/空/缺失读取、写入字节、输入保留、无效输出路径；20 个 VBA 场景覆盖 Windows IStorage 生成的复合流、原始流、字面量与重叠复制、4096 字节原始块、多块、模块偏移、游标、异常块和缺失文件。每个场景独立进程并设置超时，崩溃或只有成功退出码都不能冒充通过。

编译器实际读取报告覆盖全部 13 单元。本机核对 1063 个锁定头文件和 304 个 MSVC/SDK 头文件；工具链数量可随 SDK 变化。VBA 测试样本由 Windows 系统复合存储 API 创建，未加载私人文档或执行宏代码。

## 重建与证据

需要 Python 3.11+、Git、VS2022 x64 C++ Build Tools 和 Windows SDK；在同一稳定工作目录先完成 ICU/UnicodeConverter 和 kernel。然后运行：

```powershell
python tools/build_formats.py verify
python tools/build_formats.py build --work-dir D:\CodexCache\qingliang-community-publish\dependency-build
```

可通过 `--archive-cache`、`--source-cache` 指定只读缓存。工作目录保护、源码哈希、并发锁和已有证据保留规则与其他组件一致。产物和证据位于该目录的 `lib/`、`format-build.log`、`format-build-report.json`、`format-compiler-inputs.json`、`format-native-cases.json`、`format-test-result.json`、`format-fixtures/`。GitHub Windows-2022 作业在原有单一依赖工作目录末尾执行同一构建和测试。

下一步继续构建 DOCX 路径、命名空间及文档模型等支持，完成真实 TXT↔DOCX 转换，再接入完整 x2t。桌面应用、GUI 和安装器仍未生成。
