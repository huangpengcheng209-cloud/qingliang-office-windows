# 第一批工作台功能、视觉与动效改进

2026-10-23：直接修改原桌面起始页，不另建演示产品。原 win.22 的 96 个冻结文件和五份补丁保持原字节；新增完整文件位于 `ui-sources/`，相对冻结父版本的差异在 `ui-patches/`，输入在 `ui.inputs.lock.json`。

## 实现内容

- 最近文件增加文件名/位置的文字搜索，支持 Unicode 规范化、大小写及字面特殊字符，避免原过滤函数的正则异常和状态问题。
- 增加文档、表格、演示、PDF、置顶筛选及结果数量；搜索与筛选可组合，后来加载的历史数据继续遵守当前条件。无匹配与从未打开文件分开显示，可一键清除条件。
- 最近文件默认显示四项，展开/收起与搜索结果协调；置顶仍通过原 `recent:pinned` 命令写入宿主，筛选不改变历史文件顺序或内容。
- 支持 Ctrl/Cmd+F 定位搜索、Escape 清空、ArrowDown 聚焦文件、Enter/Space 打开；文件按钮、置顶及更多操作增加语义与标签。新建四类文件及打开已有文件继续使用原生命令。
- 修复渲染模板剥掉模型文件扩展名的问题；修复重复路径让 40 条批次提前停止、以及异步旧历史批次污染新列表的问题。
- 统一工作台、卡片、列表、搜索框和侧栏的配色、间距、圆角与焦点；完善浅色/深色及窄窗口布局，修正文件操作图标被挤成极小尺寸的问题。
- 卡片悬停/按下与内容出现使用短过渡；`prefers-reduced-motion` 禁用页面动画与过渡。没有增加自动播放、外部字体或下载图片。

## 从固定源码构建实际页面

```powershell
python tools/build_workbench.py verify
python tools/build_workbench.py build --work-dir D:\CodexCache\qingliang-community-build
```

需要 Python 3.11 以上、Git、Node.js/npm。固定 desktop-apps 提交与主锁一致，归档核对 SHA256，仅准备 545 个首页/许可输入，再应用冻结源码与六份质量覆盖。构建复用同一依赖目录和 `.build.lock`，执行原项目的 npm 锁定依赖安装、SVG/PNG sprite、LESS、Terser 和 Grunt 打包，生成真实 `sources/desktop-apps/common/loginpage/deploy/index.html`。默认 `npm ci --ignore-scripts`，不依赖旧应用或旧生成资源；`--skip-install` 仅用于复用此目录中已经安装的工具链。

准备阶段预检归档路径、选中项重名/链接和逐文件哈希；未参与构建的其他平台链接不创建。未知本地源码修改保留并报错。成功构建记录输入锁、Node 版本、npm 锁、输出哈希和 sprite 生成差异；下一次只允许明确记录的旧版本源码升级。

## 浏览器验收

在单独的 D 盘验证环境安装 `playwright==1.55.0`，使用已安装的 Edge：

```powershell
python tests/run_workbench_tests.py --work-dir D:\CodexCache\qingliang-community-build --evidence-dir D:\CodexWorkspaces\workbench-evidence
```

测试通过本机回环 HTTP 服务加载完整构建 HTML。所有生产控制器、模型、DOM、CSS 和图标均为实际构建输出；`tests/ui/native_bridge_fixture.js` 只替代浏览器中不可用的 CEF 原生接口，记录命令并使用自行编写的测试历史。适配器和测试历史不进入生产 HTML，不修改用户最近文件。

本机 37/37 检查通过，四类新建及打开/置顶核对原生命令边界；包含特殊字符/中文/Unicode 搜索、类型组合、键盘、重复路径批次、旧批次取消、后续批次过滤、窄窗口、深色及减少动效。查看浅色、深色和紧凑截图，修正布局与图标后重跑。本机工具检查 123 项中 122 通过、1 项因 Windows 符号链接权限跳过。CI 的 Workbench quality 作业独立构建和运行同一浏览器检查。

这些结果证明首页浏览器层行为，不能证明文件选择对话框、桌面编辑/保存、放映或安装成功。整体验收范围仍见 [PRODUCT-QUALITY-PLAN.md](PRODUCT-QUALITY-PLAN.md)，目标尚未完成。
