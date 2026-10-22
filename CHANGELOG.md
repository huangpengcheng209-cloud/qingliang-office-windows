# 源码版本记录

## win22-font-shaping-preview

- 固定 536 个 core 输入、两个官方归档及 444 个选定归档输入，从源码构建 FreeType/zlib、Brotli decoder、HarfBuzz，共 136 个编译单元。
- 将固定 ONLYOFFICE 的 HarfBuzz 字符映射适配转换为独立可审计补丁，提供完整修改文件和稳定生成的 75 单元 qmake 输入；保留原冻结 96 文件身份。
- 32 项本机原生测试通过，包括 20 个固定上游字形/位置预期和 12 个字体、桥接、栅格及 Brotli 场景。首轮阿拉伯文断言过窄，改用上下文字形替换和 RTL 簇顺序核对，没有因此修改厂商库算法。
- 工具检查共 58 项，本机 57 项通过、1 项因 Windows 符号链接权限跳过；CI 在同一 VS2022 工作树中顺序构建字体依赖。HEIF、完整图形库、x2t 和安装包仍未构建。

## win22-network-crypto-preview

- 固定 427 个输入，从源码构建 Windows kernel_network（4 单元）和完整上游 CryptoPPLib 工程（181 个去重单元）。
- 一份独立 Windows 传输补丁修复空 HTTP 目标文件缺失及未实现上传误报成功，并设置不写持久下载缓存。
- 本机 20 项运行测试通过，覆盖 Windows CNG 独立算法比对、Office ECMA 数据包装器和本机 HTTP 下载；工具测试增至 50 项。
- 记录完整图形库缺失的 HarfBuzz 生成工程输入及 HEIF 依赖，不以 qmake 的零返回码代替完整构建就绪证据。仍无完整 x2t 或应用安装包。

## win22-x2t-prerequisites-preview

- 源码构建 Boost.Regex（17 单元）、Boost.DateTime（3 单元）和 CompoundFileLib（13 单元），固定 49 个 core 输入及 Boost 源码/工程身份。
- 两份单独补丁修复复合流读取长度、跨扇区复制偏移和提交遗漏扇区的问题，保留原冻结版本身份。
- 本机 21 项原生场景通过，包含 Windows IStorage/IStream 双向互操作；样本不是实际 Office 文档。
- 工具测试共 42 项，本机 41 项通过、1 项因符号链接权限跳过；CI 加入顺序前置库构建，尚无完整 x2t 或应用安装包。

## win22-kernel-preview

- 按上游 Windows 内核工程固定 47 个编译单元和 213 个输入，直接使用 MSVC 编译，并链接新构建的 UnicodeConverter/ICU。
- 两份独立 XML 修复处理 GBK 单引号编码声明和首次读取失败仍生成节点的问题；完整修改源码和补丁可审计，原 96 文件冻结身份保留。
- 首次云端测试 17/18，发现中文 ZIP 文件名依赖 OEM 代码页；改为 UTF-8 写入并设置格式标记，读取遵循条目标记并保留旧 OEM 回退。
- 本机 22 项联合运行测试通过；工具测试共 36 项，本机 35 项通过、1 项因符号链接权限跳过。
- GitHub 依赖作业增加顺序内核构建，不重复创建完整依赖树；仍无整套应用或安装包发布。

## win22-unicode-deps-preview

- 固定 Boost 1.72.0、ICU 74.2 官方源码归档及四个上游 UnicodeConverter 文件的来源与 SHA256。
- 新增独立依赖准备/构建入口，源码构建 ICU 和 UnicodeConverter DLL/导入库，不使用旧 Office 基线 DLL。
- 原生测试首次 12/14；单独修复 UTF-32 emoji 输出容量后，本机 14/14。补丁与完整修改源码独立保留，原 win.22 的 96 文件清单不变。
- 工具测试共 28 项；新增 GitHub Windows 全新环境依赖构建作业。完整应用和安装包仍未构建验收。

## win22-native-save-preview

- 新增显式工作目录、自动 MSVC 定位和并发保护的 Windows 原生构建入口。
- 实际编译公开保存事务组件，新增 14 个原生文件测试；源码不改动。
- 新增目录/冻结归档的只读引擎输入审计，定位三项缺失输入；增加七个构建工具测试。
- CI 增加独立 Windows 编译运行作业；完整应用、GUI 和安装包仍未验收。

## win22-source-preview

源码基线：9.4.0.129-win.22；社区整理日期：2026-10-22。

- 公开五个模块中的 96 个完整修改文件、五份累计补丁、九个固定上游提交、许可和构建参考。
- 增加 Windows/Linux 自动源码哈希、补丁应用结果及文件保护检查。
- 提供源码版本标签，便于引用、下载和复核；不附带应用安装包。

原应用修改及验收范围见 docs/STATUS.md；后续计划见 docs/ROADMAP.md。
