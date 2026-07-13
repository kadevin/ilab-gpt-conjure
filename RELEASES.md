# 下载 / Releases

当前正式版本：[v0.6.2](https://github.com/kadevin/ilab-gpt-conjure/releases/tag/v0.6.2)

## 版本说明

当前版本：`v0.6.2`。本版进一步完善生成工作台的弹性响应式布局，修复部分窗口尺寸下的溢出、留白、错位和缩放卡顿；同时为 macOS 标准版加入用户确认后的一键覆盖更新能力。强烈建议所有用户尽快更新，尤其是经常调整窗口尺寸、使用笔记本短屏或高分辨率屏幕，以及使用 macOS 标准版的用户。

本版重点：0.6.2 重点完善不同宽度和高度下的连续自适应布局，减少刷新、窗口缩放和锁定状态切换时的跳变与延迟；macOS 标准 App 首次加入安全的一键覆盖更新助手。

本版详情：

### 升级必读

- `v0.6.1` 及更早的 macOS 标准 App 尚未包含更新助手，需要从 Release 页面手动下载并覆盖安装 `v0.6.2` 一次；完成这次引导升级后，后续版本即可从菜单栏“检查更新”一键安装。
- Windows 标准 ZIP 仍需下载后手动替换；portable 包继续使用现有的用户确认式自动更新。
- `v0.5.4` 及更早 portable 用户首次升级到 `0.5.5` 或更新版本时，建议手动下载完整标准包或完整 portable 包；旧 updater 只保证升级 WebUI/依赖，不保证安装新的小兔子启动器、标准 `.app` / `.exe` 入口和迁移助手。
- 新用户建议优先下载标准包。标准包把用户数据写入系统应用数据目录；portable 包继续把数据写在同级 `data/`，用于老用户过渡、调试和临时工作流。
- 本次更新不改变任务数据库、输出目录和用户设置的数据结构，无需迁移现有任务或图片。
- macOS 一键更新只会在用户主动确认后执行，不会后台静默下载或安装；用户数据保存在应用包外，不参与程序替换。
- macOS 标准 DMG 和 portable zip 都暂未签名、未 notarize，首次启动可能需要右键或 Control-click 选择 Open。

### 性能与响应式修复

- 优化生成工作台在刷新、连续调整窗口尺寸和切换输出参数锁定状态时的布局稳定性，减少卡顿、跳变与延迟。
- 修复不同宽高组合下输出设置底部溢出、异常留白，以及控制区与预览区底部无法对齐的问题。
- 参考输入、提示词和输出设置会按真实可用空间连续调整，不再因单一高度阈值突然切换成不协调的排版。
- 短屏和笔记本分辨率下继续保留双栏工作区，同时避免板块标题、最近上传、公共图库入口和顶部工具组重叠。
- 大尺寸屏幕下工作区能够自然扩展，不再出现局部高度锁死、内容过度缩小或预览区域单独拉长的问题。

### macOS 标准版一键更新

- 包含更新助手的 macOS 标准 App 可从菜单栏“检查更新”安装后续版本。
- 用户确认后，独立 helper 会校验 signed `latest.json` 和 DMG SHA256，退出当前 App，带回滚保护地替换旧版本，并在成功后自动重新启动。
- 替换失败时会恢复旧 App；任务、图片和设置等用户数据不会被修改。
- 缺少更新助手的旧版 macOS App 会安全回退到打开 DMG 下载，不会进入无法完成的安装流程。
- Windows 标准 ZIP 继续下载后手动替换；portable 包继续使用原有的签名校验和自动替换更新器。

### 安装包与发布工作流

- 继续提供 Windows x64、macOS Apple Silicon、macOS Intel 三种 portable zip，以及 macOS 双架构 DMG 和 Windows 标准 App ZIP。
- Release workflow 同时构建并上传 macOS Apple Silicon DMG、macOS Intel DMG、Windows 标准 App ZIP、Windows x64 portable、macOS Apple Silicon portable、macOS Intel portable、所有 `.sha256.txt` 和 signed `latest.json`。
- `latest.json` 同时服务 portable 自动更新与 macOS 标准 App 一键更新；两类更新都需要用户主动确认，并校验签名和下载文件完整性。

### 文档与维护

- 同步更新标准包、portable 包和更新器说明，明确首次引导升级、用户确认、回滚保护与数据保留边界。
- 补充响应式布局和发布流程的维护约束，降低后续新增功能再次引入溢出、错位或性能回归的风险。

## 推荐下载

| 平台 | 推荐给 | 下载 | SHA256 |
| --- | --- | --- | --- |
| macOS Apple Silicon | 新用户，M1/M2/M3/M4 | [iLab-GPT-CONJURE-macos-arm64-0.6.2.dmg](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/iLab-GPT-CONJURE-macos-arm64-0.6.2.dmg) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/iLab-GPT-CONJURE-macos-arm64-0.6.2.dmg.sha256.txt) |
| macOS Intel | 新用户，Intel x64 | [iLab-GPT-CONJURE-macos-x64-0.6.2.dmg](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/iLab-GPT-CONJURE-macos-x64-0.6.2.dmg) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/iLab-GPT-CONJURE-macos-x64-0.6.2.dmg.sha256.txt) |
| Windows x64 | 新用户，Windows 10/11 x64 | [iLab-GPT-CONJURE-windows-x64_0.6.2.zip](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/iLab-GPT-CONJURE-windows-x64_0.6.2.zip) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/iLab-GPT-CONJURE-windows-x64_0.6.2.zip.sha256.txt) |

标准包数据目录：

- macOS：`~/Library/Application Support/iLab GPT CONJURE/`
- Windows：`%APPDATA%\iLab GPT CONJURE\`

包含更新助手的 macOS 标准 App 会校验 signed `latest.json` 与 DMG SHA256，并在用户确认后自动覆盖、失败回滚和重新启动；旧版 macOS App 需要先手动安装 `v0.6.2`，Windows 标准 ZIP 仍手动替换。

## 免安装一键包

| 平台 | 适用设备 | 下载 | SHA256 |
| --- | --- | --- | --- |
| Windows x64 | Windows 10/11 x64 | [ilab-gpt-conjure_windows_portable_x64_0.6.2.zip](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/ilab-gpt-conjure_windows_portable_x64_0.6.2.zip) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/ilab-gpt-conjure_windows_portable_x64_0.6.2.zip.sha256.txt) |
| macOS Apple Silicon | M1/M2/M3/M4 | [ilab-gpt-conjure_macos_portable_arm64_0.6.2.zip](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/ilab-gpt-conjure_macos_portable_arm64_0.6.2.zip) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/ilab-gpt-conjure_macos_portable_arm64_0.6.2.zip.sha256.txt) |
| macOS Intel | Intel x64 | [ilab-gpt-conjure_macos_portable_x64_0.6.2.zip](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/ilab-gpt-conjure_macos_portable_x64_0.6.2.zip) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/ilab-gpt-conjure_macos_portable_x64_0.6.2.zip.sha256.txt) |

portable 自动更新 manifest：

- [latest.json](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.6.2/latest.json)

使用方式：

1. 下载对应平台的 zip。
2. 解压到普通用户目录，不要放在系统保护目录。
3. Windows 双击 `Start iLab GPT CONJURE.exe`；macOS 双击
   `Start iLab GPT CONJURE.app`。旧的 `Start WebUI Portable.bat` /
   `Start WebUI Portable.command` 仍保留，用于终端调试。
4. 如果浏览器没有自动打开，访问 `http://127.0.0.1:8787/`。

一键包启动器不会后台自动访问 GitHub。更新已经解压的一键包时，可在托盘 / 菜单栏
菜单选择检查更新，并在发现新版本后确认 `安装更新`；也可以退出启动器后手动运行
Windows 的 `Update WebUI Portable.bat` 或 macOS 的 `Update WebUI Portable.command`。
更新脚本会读取带签名的 `latest.json`
manifest，先用启动器内置公钥校验 Ed25519 签名，再下载当前平台对应的最新
GitHub Release 资产，执行前显示所选资产和 manifest SHA256，校验下载 zip 的
SHA256，只替换一键包目录内由程序管理的文件，保留本地 `data/`，并把被替换文件备份到 `.backup/`。

macOS 标准 DMG 和 portable zip 都暂未签名、未 notarize。如果 macOS
拦截启动，可以右键或 Control-click App，选择 Open，并在系统安全提示中再次确认。
portable zip 也可以对解压目录执行：

```bash
xattr -dr com.apple.quarantine /path/to/ilab-gpt-conjure_macos_portable_arm64
# 或：
xattr -dr com.apple.quarantine /path/to/ilab-gpt-conjure_macos_portable_x64
```

一键包内的 `data/` 目录会保存本地设置、公用图库、输入图、输出图、任务数据库和日志。
不要把这些本地数据、API key 或 OAuth 文件提交到 Git。
