# 桌面编辑运行资源与真实文档验收

后续表格与编辑区质量更新见 [EDITOR-QUALITY.md](EDITOR-QUALITY.md)：50 项 XLSX 检查和扩大为 40 项的 DOCX 回归通过，新增排序、主题、焦点和短动效修复；以下保留首批 DOCX 接通阶段的 39 项范围。

本阶段接通新编译的 Qt/CEF 宿主与实际桌面编辑区。本机已通过 39 项真实 DOCX 编辑、保存、关闭重开、新建另存和 PDF 导出检查；实际工作台另有 16 项窗口回归通过。表格、演示和 PDF 表单的完整编辑流程、插件、媒体、安装和整套视觉/动效仍需完善。

## 固定输入与构建

先在同一有标记的稳定目录完成 [CONVERTER-BUILD.md](CONVERTER-BUILD.md)、[HOST-BUILD.md](HOST-BUILD.md)、[WORKBENCH-QUALITY.md](WORKBENCH-QUALITY.md) 和 [QT-DESKTOP-BUILD.md](QT-DESKTOP-BUILD.md) 的构建。关闭该目录启动的预览窗口，再运行：

```powershell
python tools/build_editors.py verify
python tools/build_editors.py build --work-dir D:\CodexCache\qingliang-community-build --archive-cache D:\CodexCache\office-windows\downloads
```

需要 Windows、Python 3.11+、Git、Java 21、Node.js/npm；本机使用 Node.js 24.14.1。工具复用既有源码/依赖缓存，输出写入指定 staging，不复制另一套完整源码。首次安装按固定 `package-lock.json` 执行 `npm ci --ignore-scripts`，仅对三个固定图片构建工具执行所需安装步骤，并核对其可执行文件哈希。已安装且身份相同可加 `--skip-install`。未知源文件修改、额外输入或被修改的生成文件会保留并停止构建。

`editor.inputs.lock.json` 单独记录完整 web-apps 归档、30,130 个源码输入、四个桌面 SDKJS 配置、原生图片工具、模板、词典和额外桌面资源。web-apps/SDKJS/词典沿用原固定提交；空文档模板另外固定为 `ONLYOFFICE/document-templates@4175d3531074b6e6bd6ebe38a3dd2578e9ef9617`，未改写原九仓库锁或冻结 96 文件。

构建包含：

- Closure 编译桌面 word/cell/slide/visio SDKJS，分别为 438/398/385/354 个源文件；与转换器的 SDKJS 配置和输出分开。
- 构建 common 及 documenteditor、spreadsheeteditor、presentationeditor、pdfeditor、visioeditor 的桌面 main 界面，保留冻结 Desktop 控制器，并审计 RequireJS 实际读取的源码。移动端界面不属于该 Windows 运行布局。
- 执行固定上游翻译合并，再复制并压缩 locale；逐一比较部署 JSON 与合并后的源 JSON。196 个其他语言文件得到上游英文回退，206 个编辑器 locale 文件部署到运行目录。
- 将界面、固定 SDKJS 资源、空文档模板、词典、字体和新编译的转换器放入运行布局，记录 17,215 次文件复制及其来源/哈希。SDKJS 归档自带的 WASM 按身份复制，本阶段没有重编译这些 WASM。

输出包括 `desktop-sdk-build-report.json`、`editor-web-build-report.json`、`editor-runtime-layout.json` 和 `editor-build-report.json`。构建报告中的 `edit_save_tested:false` 只表示构建工具不执行 GUI 验收；实际结果由下述独立测试报告记录。完整默认插件、OCR 载荷和媒体验收尚未完成。

## 本阶段修复

五个编辑器的简体中文 locale 补齐 60 个缺失字符串，包括多页视图提示、功能名称和新版帮助；“New” 功能标记改为“新功能”。此前真实界面出现 `新建undefined`，并把与多页视图无关的协作警告当作提示正文。完整文件和相对固定上游的差异分别见 `editor-sources/`、`editor-patches/`，原冻结程序文件不变。

Qt 原生另存对话框此前会把用户输入的 `.DOCX` 再追加成 `.DOCX.docx`。`qt-patches/save-suffix-case.patch` 改为忽略大小写判断后缀，保留用户输入的拼写；完整文件和编译输入身份见 `qt-sources/`、`qt.inputs.lock.json`。文档保存和 PDF 导出均以实际系统对话框重新验证。

## 真实 Windows 验收

在独立 Python 验证环境安装 `tests/editor-requirements.txt`，关闭该 staging 的现有预览后执行：

```powershell
python -m pip install -r tests/editor-requirements.txt
python tests/run_editor_tests.py --work-dir D:\CodexCache\qingliang-community-build --qt-dir D:\Qt\5.15.2\msvc2019_64 --evidence-dir D:\CodexWorkspaces\qingliang-editor-evidence
```

证据目录须为空或由本测试标记；重跑前核对既有测试文件哈希，未知修改不覆盖。测试自行启动独立 INI/数据目录的 Qt 预览，使用真实 CEF 原生接口和 Chromium 输入事件，不注入宿主或保存替身。原生文件对话框按所属进程和 HWND 定位；不使用全局鼠标坐标操作其他窗口。每轮正常关闭后才启动下一轮，报告记录退出码，不强制结束进程。

本机 39/39 通过，范围为：

- 打开含中英文的 DOCX、输入、撤销/重做、选择段落及加粗；实际保存后用 python-docx 检查原文保留和加粗。
- 正常退出并由新进程重开，检查真实模型/工具栏状态和保存文件字节。
- 从空模板新建，经原生 Save As 保存为大写 `.DOCX`，检查实际文件、源路径和清洁状态。
- 检查真实中文多页视图提示，经文件菜单和原生对话框导出大写 `.PDF`；PyMuPDF 读取中英文正文并渲染目视检查，原 DOCX 字节和编辑上下文保留。
- 三次正常退出码均为 0，观察到的 JavaScript 异常为 0，原始输入 DOCX 保持不变。

`editor-test-result.json` 绑定主程序、宿主 DLL、构建/运行布局和测试源码哈希，另保存实际页面截图、DOCX 和 PDF 样本。本轮主程序 SHA256 为 `bca80775721c4c75444969d64c706f25dafda1bd3769b3787179af8ad1c4991f`，宿主 DLL 为 `8b530c8380c86e7000ea94eb209cf47cc2f4f2b24256c2a6d3def1a5f4a42cfa`。真实工作台以同一新程序重跑 16 项检查，保留真实最近历史，不擦除数据来制造空列表。

这只覆盖上述普通 DOCX 生命周期和 PDF 输出。Chromium 中文输入不等同于 Windows IME 候选窗、真实粘贴或跨软件互操作验收。复杂文档、图片/表格/脚注等编辑、保存失败与崩溃恢复、XLSX/PPTX/PDF 表单、插件、音视频、缩放、完整明暗主题和安装/升级/卸载仍需逐项验收。没有公开安装包，整体完善目标仍在进行；完整清单见 [PRODUCT-QUALITY-PLAN.md](PRODUCT-QUALITY-PLAN.md)。
