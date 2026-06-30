# 下载 / Releases

当前正式版本：[v0.5.4](https://github.com/kadevin/ilab-gpt-conjure/releases/tag/v0.5.4)

## 版本说明

当前版本：`v0.5.4`。这个版本提供 Windows x64、macOS Apple Silicon、macOS Intel 三种免安装一键包；下载对应平台的 zip 后解压即可启动本地 WebUI，并可手动运行包内更新脚本升级到后续版本。

本版重点：这个版本集中优化 WebUI 的任务栏、历史库和状态同步体验。生成页侧栏更紧凑，任务筛选并入搜索框，任务卡信息层级重新整理；历史库修复多选删除、深色主题复选框和多选详情状态；同时增强任务超时、中断和服务重启后的实时状态更新，减少“刷新后才变成失败”的情况。

本版详情：

- 任务栏筛选并入搜索条，支持筛选条件数量提示和一键清空，减少侧栏额外占用。
- 任务卡改为更紧凑的三行结构：状态 / 计数与耗时作为固定扫描锚点，标题独占一行，尺寸、供应商和完成时间放到底部信息行。
- 去掉任务卡常驻状态圆点和“查看中”胶囊，选中态不再造成卡片位移；失败任务用浅色填充区分，不再用描边避免和选中态混淆。
- 图片数量计数改成最多 4 个小方块，普通完成 / 失败任务不再重复显示“1 张、成功、失败”等冗余文字。
- 运行中 / 等待中任务组支持折叠，并补齐展开 / 收起过渡，避免任务过多时挤掉“今天 / 昨天 / 最近 7 天”分组。
- 优化图生图任务缩略图：参考图和结果图保持原比例缩小，不再统一裁成正方形，也禁用原生图片拖拽，减少批量圈选误触。
- 侧栏宽度拖拽路径做性能约束，拖拽时不触发整页样式失效、任务列表重绘、预览高度重算或本地存储写入。
- 历史库任务卡补充供应商名称，Codex / Responses / OpenAI-compatible 供应商显示更清楚。
- 修复历史库多选删除只删除部分任务的问题；多选时右侧详情改为批量选择摘要和批量操作，不再显示单任务详情造成状态混淆。
- 深色主题下历史库复选框提高可识别度，同时避免额外底色破坏卡片视觉。
- 修复 API 中转站超时、请求中断或服务重启后，任务可能长时间停留在运行 / 等待计时的问题；队列实时事件会携带已结束任务状态，孤儿运行槽位会规范标记为失败。
- 优化 1512px 左右桌面宽度下的响应式布局，避免满屏时图像输入区、按钮组和预览列错位。
- 预览区和错误提示去除多余描边，用背景填充表达层级，减少“套了多层容器”的视觉噪音。

## 免安装一键包

| 平台 | 适用设备 | 下载 | SHA256 |
| --- | --- | --- | --- |
| Windows x64 | Windows 10/11 x64 | [ilab-gpt-conjure_windows_portable_x64_0.5.4.zip](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.4/ilab-gpt-conjure_windows_portable_x64_0.5.4.zip) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.4/ilab-gpt-conjure_windows_portable_x64_0.5.4.zip.sha256.txt) |
| macOS Apple Silicon | M1/M2/M3/M4 | [ilab-gpt-conjure_macos_portable_arm64_0.5.4.zip](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.4/ilab-gpt-conjure_macos_portable_arm64_0.5.4.zip) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.4/ilab-gpt-conjure_macos_portable_arm64_0.5.4.zip.sha256.txt) |
| macOS Intel | Intel x64 | [ilab-gpt-conjure_macos_portable_x64_0.5.4.zip](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.4/ilab-gpt-conjure_macos_portable_x64_0.5.4.zip) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.4/ilab-gpt-conjure_macos_portable_x64_0.5.4.zip.sha256.txt) |

使用方式：

1. 下载对应平台的 zip。
2. 解压到普通用户目录，不要放在系统保护目录。
3. Windows 双击 `Start WebUI Portable.bat`；macOS 双击
   `Start WebUI Portable.command`。
4. 如果浏览器没有自动打开，访问 `http://127.0.0.1:8787/`。

更新已经解压的一键包时，先关闭 WebUI 服务窗口，然后运行 Windows 的
`Update WebUI Portable.bat` 或 macOS 的 `Update WebUI Portable.command`。
启动脚本不会访问 GitHub，也不会自动更新文件。更新脚本会下载当前平台对应的最新
GitHub Release 资产，执行前显示所选资产和 SHA256 文件，校验 SHA256，只替换一键包目录内由程序管理的文件，保留本地 `data/`，并把被替换文件备份到 `.backup/`。

macOS 包是未签名的 portable zip，不是已签名 `.app` 或 notarized DMG。
启动脚本会尝试在启动前移除当前解压目录内的 quarantine 标记。如果 macOS
仍然拦截启动脚本，可以右键或 Control-click `Start WebUI Portable.command`，
选择 Open，并在系统安全提示中再次确认。也可以对解压目录执行：

```bash
xattr -dr com.apple.quarantine /path/to/ilab-gpt-conjure_macos_portable_arm64
# 或：
xattr -dr com.apple.quarantine /path/to/ilab-gpt-conjure_macos_portable_x64
```

一键包内的 `data/` 目录会保存本地设置、公用图库、输入图、输出图、任务数据库和日志。
不要把这些本地数据、API key 或 OAuth 文件提交到 Git。
