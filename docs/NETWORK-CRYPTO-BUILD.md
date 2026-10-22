# Windows 网络与加密支持库

本阶段从固定 core 源码构建 `kernel_network.dll` 和 `CryptoPPLib.lib`，继续补齐 x2t 直接依赖。网络采用上游默认 Windows URLMon/WinINet 后端；未选择可选 `support_web_socket` 配置。加密采用上游 `CRYPTOPP_DISABLE_ASM` 配置，并保留工程内的 OfficeCryptReader 两个编译单元。

## 构建入口

需要 Python 3.11+、Git、7-Zip、带 Windows SDK 的 Visual Studio 2022 C++ Build Tools 和网络：

```powershell
python tools/build_transport.py verify
python tools/build_transport.py build --work-dir D:\CodexCache\qingliang-community-dependencies
```

复用 ICU/内核阶段的同一目录。首次运行准备已有依赖和内核，已有匹配成功报告及产物时复用；随后准备本批 427 个锁定源码/头文件/工程/许可输入，编译网络 4 个单元与加密 181 个单元。上游加密工程列了 182 项，其中 `eprecomp.cpp` 重复一次；清单合并该重复项，没有移除算法或 Office 包装代码。

输入身份及实际宏定义、包含路径见 `transport.inputs.lock.json`。可选 `--archive-cache`、`--source-cache` 是只读缓存，读取内容仍须匹配哈希。所有构建输出写入显式工作目录，使用公共构建锁；未知源码修改、错误身份和未检查的失败测试现场会导致停止。这里不需要 Qt 工具或运行时，原 Office 支持库和应用文件没有被替换。

## 运行验收

20 项本机测试通过，包括：

- 确认内核和网络 DLL 从本批输出目录实际加载。
- CryptoPP 的 SHA1/SHA256/SHA512、HMAC-SHA256、PBKDF2-HMAC-SHA256、AES128-ECB、AES256-CBC 与 Windows CNG 独立实现逐字节比对，以及非法 AES 密钥拒绝。
- 调用 OfficeCryptReader 的 ECMA 加密包装器，对 9001 字节测试数据完成加密/解密、完整性比对、错误密码拒绝和篡改检测。测试密码是公开的固定测试值，未使用账户凭据；没有打开实际 Office 文档，也没有进行 Microsoft Office 跨软件验收。
- 下载纯文本、含零字节的二进制、600000 字节数据、重定向、中文/emoji 目标路径、空 HTTP 响应，以及 HTTP 404 失败。下载内容再用 CryptoPP/Windows CNG 比对哈希。
- 未实现的 Windows 内存/文件上传返回失败，文件输入保留。

HTTP 服务由测试驱动创建，仅监听 `127.0.0.1` 随机端口，路由只返回人工生成的数据，不提供用户目录。测试不向外部服务上传内容。驱动对原生进程设置 180 秒上限，保存本机请求记录。未测试 HTTPS 证书链、真实代理、WebSocket 或外部站点可用性。

首次运行 18/20：空 HTTP 响应成功但目标文件未生成；Windows 上传接口仍是返回成功的桩函数。本批一份独立补丁让上传明确返回 `E_NOTIMPL`；空响应仅在再次确认 HTTP 成功状态且 `Content-Length=0` 后创建空文件，写入失败仍报失败。URLMon 回调同时请求获取新内容并不写持久下载缓存。本批未实现上传传输，也未把默认后端改成其他协议实现。

补丁、完整修改源码、修改日期和前后身份见 `transport-patches/`、`transport-sources/` 和清单，保留原许可并独立于原 win.22 冻结的 96 文件。准备时先核对公开上游原文，再应用补丁并核对完整结果。

## 输出与剩余工作

产物位于工作目录的 `bin/kernel_network.dll`、`bin/kernel_network.lib`、`lib/CryptoPPLib.lib`。日志、测试结果和请求证据位于 `transport-build.log`、`transport-test-result.json`、`transport-http-evidence.json`、`transport-build-report.json`。成功场景清理自己创建的文件；失败现场保留供检查。

构建/源码工具共 50 项测试，本机 49 项通过、符号链接检查因权限跳过。GitHub Windows 作业在同一工作目录顺序构建依赖、内核、前置库和本批网络/加密库，实际状态见 Actions。

完整图形库尚未构建。`graphics.prerequisites.json` 记录了缺失的 HarfBuzz 生成工程输入、其上游固定提交和下游补丁入口，以及 HEIF 所需的 x265/libde265/libheif。qmake 预处理返回 0 但明确报告缺失 include，不能作为构建就绪证据；当时观察到的 434 项也不是完整编译规模。后续须补齐这些来源和构建步骤，保持现有图形功能。

完整 x2t 可执行文件、编辑器和安装包仍未构建，也未进行本批 DLL 的应用 GUI 验收。本阶段仅发布源码。

工具链范围：本机使用 Visual Studio 2022；首次云端 windows-latest 使用 Visual Studio 2026/MSVC 14.51，在 CryptoPPLib 编译阶段失败，尚未运行本批测试。当前完整依赖 CI 固定为 windows-2022/Visual Studio 2022，网络/加密入口默认也选择 17.x 工具链。Visual Studio 2026 的兼容问题尚未结案；其他版本可显式指定 --vs-root，但不属于本批已验证范围。构建失败输出现在同时保留前八条编译错误和末尾诊断，避免首条错误被模板实例化提示淹没。
