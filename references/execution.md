# 客户端执行参考

## 连接与官方能力

优先使用宿主已注册的 ChatCut Desktop 本地 MCP。静态预检只能发现文件、进程和配置，实际通过当前工具调用的项目摘要、窗口及连接状态才证明可操作。

若工具目录可用，一次查找本阶段工具并保留相关 schema；不要每条操作重新列全目录。官方指南入口可能是 `list_skills/load_skill`，旧本地 MCP 的入口曾是 `manage_skill`。先读当前 schema 再调用；按需要加载转写、口播、字幕、音频与视觉检查指南，不依赖另装的同名 Skill。

若 WorkBuddy 看不到已配置的本地 MCP，但官方本地包装器确实存在且当前宿主允许运行，可用本包 `scripts/chatcut_mcp.py` 建立同样的 stdio 连接。先运行 `list-tools` 获取当前目录，使用文件传入参数；`batch` 在一次连接中顺序执行已经规划好的调用，出错立即停止，禁止自动重试。它不安装、授权、修改配置或绕过任何权限；如果宿主拒绝操作就暂停。Windows 必须使用确认支持 stdio 的实际启动命令，不假定无扩展名包装器可执行。

```sh
python3 <Skill目录>/scripts/chatcut_mcp.py list-tools
python3 <Skill目录>/scripts/chatcut_mcp.py call --tool get_active_project --args-file <任务目录>/project-read.json
python3 <Skill目录>/scripts/chatcut_mcp.py batch --calls-file <任务目录>/planned-calls.json
```

`project-read.json` 为工具真实要求的 JSON 对象，不能猜项目 ID。`planned-calls.json` 为数组，每项包含 `name` 和 `arguments`。只合并已拿到所有 ID、互不需要新结果的调用；有新 ID、revision 或异步作业依赖时分开。包装器默认拒绝名称含 export 的操作；预览文件可加 `--preview-export`，正式导出必须加 `--state-dir` 与 `--revision` 通过当前预览确认门。预览选项不能拿来导出正式文件。

启动二进制默认从本机 ChatCut 应用支持目录发现；也可用 `--command-json <命令数组文件>` 提供已确认的官方命令和参数，禁止拼 shell 字符串。只在已明确允许的本地连接上使用。

## 批量提交与验证

- 优先工具支持的相关修改合并提交；`validateOnly` 仅在当前 schema 有该字段且对这次操作有价值时使用。
- 不并发修改同一工程。依赖工具返回的新 ID 或新 revision 必须顺序执行。
- 任何字幕、转写或脚本读写的**第一次调用前**，先用 `get_active_project` 确认当前活动工程就是本任务工程。桌面端用户可随时切走工程；在错误工程上操作会得到 `The active Timeline has no caption model` 一类假故障，据此“修复”会误伤无关项目。发现被切走就用 `target_project` 切回，再继续本阶段。
- 四类阶段结果集中检查：主轨清理与提速、视觉编排、字幕、音频/总检。期间遇到越界、异步未终态或不确定写入回执仍立即读回。
- 检查 MCP JSON-RPC error、`isError`、业务 `success:false` 及明确的错误正文；进程返回码 0 不代表编辑成功。错误文本可能嵌在 `content[].text` 中，不能只依赖异常捕获。
- 异步 `pending/running` 不是失败；按工具建议间隔追踪同一作业，不重复启动。遇到明确失败进入一次修复流程。

## 主口播和画中画

已放在主轨且转写完成后，可使用当前 `clean_script` 一类原生机械清理处理固定口误与长停顿。它不理解论据和叙事，不替代语义判断；不要对尚未放入时间线的媒体库素材调用后声称已剪好。

语义剪辑优先 Script 路径：读脚本一次 → 集中编辑可恢复副本 → 按当前契约预检（如支持） → 应用一次 → 读回时长与内容。刚写完的 Script 不再调用会重物化脚本的读操作，否则可能清掉未提交修改。若 stale、revision 冲突或编辑工具报告成功但文本未变，先确定实际状态，仅允许一次针对性恢复；不“换 Python 绕过沙箱”。

改速时同时保持消耗的源范围正确，不能仅改倍率而让片段越过源尾。源消耗 = 时间线片段秒数 × playbackRate。集中更新后收紧，不把批量改速与未经验证的 ripple 混用。

B-Roll 语义时间必须从清理后的主轨映射，不能直接用原视频绝对秒数除以倍率：删除内容会改变偏移。对于主轨片段：

`source_time = source_start + (timeline_frame - item_from_frame) / fps * playback_rate`

跨主轨片段分别计算。真人副本在每个主轨边界切开，主轨源起点和倍率保持一致，严格静音；B-Roll 使用实际已支持的静音字段。`-60dB` 只是很小的音量，能真静音则优先静音，不宣称它等于关闭音频。

横屏素材按当前原生 cover 适配；带旋转元数据素材先看实际显示方向。只有确认解码兼容性问题后，才把必要源文件转成独立兼容副本，不覆盖原素材，不为所有源素材预先转码。

## 能力与来源边界

以下公开说明核对于 2026-09-28；功能以运行时客户端版本和 MCP schema 为准：

- [官方 WorkBuddy 指南](https://chatcut.io/workbuddy)：ChatCut 操作指南通过 MCP 提供，按需读取；WorkBuddy 配置路径与云端 OAuth 流程不等于 Desktop 本地连接。
- [客户端说明](https://chatcut.io/docs/desktop-app)：支持读取本地素材、本地导出，部分服务仍需网络；本地 MCP 与云端插件是不同连接。客户端已有后台更新机制，不再沿用“永不自动更新”的旧结论。
- [口播剪辑](https://chatcut.io/docs/talking-head-edit)：支持基于转写清理口播，清理后应检查内容连续性。

读取指南不会自动把推理交给内置 ChatCut Agent。本 Skill 不自动触发图片、视频、音乐、音效、配音生成，不声称任何 AI 生成是免费的。
