# 更新日志

本技能按语义化版本演进。**对外分发的版本以仓库 `main` 分支及同名 tag 为准**，桌面的 zip 只是某一版的快照。

---

## v2.5.1 (2026-10-15)

**字幕平台规避词留白：**
- 用户指定或高置信的品牌、同行、产品专名只在字幕显示层留白，原始口播、源转写和主轨剪辑保持不变
- 按真实 token 边界把目标词单独分卡，再删除该字幕卡；不改写成“某 AI 工具”等替代台词
- 当前 Agent/MCP 没有单卡删除 action 时，定位目标卡并请用户在 Desktop Content 面板执行删除，禁止用空字符串、空格或零宽字符模拟
- 总检增加目标词全文搜索，以及留白前、中、后三处画面与连续音频检查

**合并说明：**

- 本版由分发包（桌面包）在仓库 v2.5.0 之后新增的字幕留白规则合并而来，以仓库基座为准
- 分发包内 `CHANGELOG.md` / `README.md` / `使用说明.md` 版本信息滞后（README/使用说明停在 v2.2.0），本次以仓库版本为基座补齐
- 分发包 `SKILL.md` 再次带回仓库 v2.5.0 已修的两处问题（5 处中文开引号误写为右引号、字幕坐标示例越出自定安全区），合并时按仓库版本保留修正

---

## v2.5.0 (2026-10-11)

第二轮实战（济南国庆沙龙 A-Roll）踩坑回填，全部是执行侧硬约束。

**新增注意事项：**

- **`playbackRate` 的语义不是「总时长缩短 10%」**：ChatCut 的实际行为是「时间线占位不变、读源更快、`sourceOut` 自动扩大 1.1 倍」。批量设完倍速后必须读 timeline，逐段校验相邻 item `sourceOut ≤ 下一个 sourceIn`；当总源需求（时间线总帧数 ÷ 30 × 倍速）超出素材时长时，ChatCut 会靠相邻 item 源范围重叠来「借」内容，接缝处音频叠字（实测听到「带大家看带大家看」）。发现重叠就把每个 item 的 `sourceIn` 对齐到前一个 item 的 `sourceOut`，不要靠改倍速重试；仍超出时优先多删 2–3 秒水词，或降回 1.0x 并告知用户
- **V1 参数变化后必须同步 V3 小窗副本**：V3 轨真人小窗是 `fromItemId` 复制 V1 主口播 item 的副本，V1 的 `sourceIn` / `sourceOut` / `playbackRate` / 时间位置变化后 V3 不会自动跟随，会出现小窗嘴型与主口播声音错位。每次调完 V1 都要把 V3 对应段的 `sourceIn`、`playbackRate` 逐段对齐；同时 V2、V3 的 `audioVolume` 必须为 0，保证全片人声唯一来源是 V1
- **`edit_captions enable` 后立刻隐藏非主轨字幕**：enable 会同时给 V1 / V2 / V3 三条视频轨生成字幕，V2 是现场杂音转写、V3 与 V1 重复。enable 后第一件事就是把 V2、V3 轨设 `visible:false`，只留 V1
- **「字幕只出现在 A-roll」的正确理解**：指字幕源取 A-roll 音频，**不是**「B-roll 全屏期间隐藏主口播字幕」。B-roll 覆盖时主口播仍在说话，字幕必须正常显示主口播内容；不要为了「B-roll 干净」去隐藏 V1 卡或清空卡文字
- **禁止用 `set_card_text text:""` 或 `" "` 删字**：置空会同时清空卡片的 words token 绑定，之后填回原文会报 `Caption text could not be mapped to its source tokens`，卡片变成无法恢复的「孤儿卡」。但把 `set_card_text` 改成**非空**的正确文本（如 `walk WorkBuddy` → `WorkBuddy`）是安全的，这是专名 / 水词修正的推荐路径——不要混淆「清空」与「改写」
- **ASR 修正改为「优先改显示、不要先动源」**：`manage_transcript fix` 的 `wordIdx` 是**字级索引**而非词级，盲猜极易偏一位，连续 fix 还会把源转写改乱；更关键的是 fix 改了源转写后 `apply_script` 会立刻报 `Script row changes spoken words`，必须 refreshCache → 重写 timeline.md → 重新 apply，一步错步步错。推荐路径：先按源转写原样写 timeline 并 apply，字幕 enable 后用 `set_card_text` 逐卡改显示文本（专名 / 水词 / 口癖）；只有 ASR 错误严重到影响 item 切分边界时才用 `fix`，且必须先 refreshCache、读回 `library/*.md` 确认 wordIdx

**合并说明：**

- 本版由作者侧 2.5.0 分发包与仓库 v2.3.0 合并而成。分发包从 v2.2.0 附近的旧基线分叉，带回了两处仓库已修的问题，合并时按仓库版本保留修正：
  - `SKILL.md` 5 处中文开引号（分发包误写成右引号）
  - 字幕布局示例坐标（分发包写 `left=90, top=1468, width=900`，外框 x=90…990 越出自定安全区 x=108…972；保留仓库的 `left=108, top=1436, width=864, height=100`）
- 分发包内 `CHANGELOG.md` / `README.md` / `使用说明.md` 的版本信息滞后（停在 v2.2.0–v2.3.0），本次以仓库版本为基座补齐
- `references/`、`scripts/`、`agents/`、`assets/` 两份完全一致，未做改动

---

## v2.3.0 (2026-10-10)

**新增实战注意事项（来自实际剪辑踩坑）：**

- **创建项目必须显式指定画布尺寸**：`create_project` 默认是横屏 1920×1080，竖屏口播必须传 `compositionWidth: 1080, compositionHeight: 1920`。建错方向后再改，所有片段都会带上下裁切，要手动清 crop
- **倍速碎片清理**：1.1x 之后会产生大量碎片行（单字、短停顿），清理时逐行确认，别误删句子中间的有效内容；误删可用「先删旧行 → 加 bare `[sN]` → 删开头多余词」恢复
- **素材跨项目不共享**：每个 ChatCut 项目的 assetId 独立，上一个项目用过的素材必须重新 `push_asset` 推到当前项目
- **轨道需要手动创建**：V2 B-Roll 轨、V3 画中画轨、A1 音频轨都要用 `edit_track create` 建；V1 主口播轨是默认的
- **横改竖后字幕不自动重排**：项目一开始建错画布方向再改竖屏，字幕位置不会自动重算，需逐个 `edit_captions set_card_layout` 调回底部安全区
- **`edit_captions` 没有 delete action**：不能删掉旧字幕卡重新生成，只能逐卡修正
- **`manage_transcript fix` 命令格式**：`FIX sN: wordIdx -> "newText"`（箭头两边要有空格）；格式试不对就直接用 `edit_captions set_card_text` 手动改字幕文本
- **BGM 通常比视频长**：添加后要手动裁到与主轨等长（`durationFrames` = 主轨总帧数），别让音乐超出视频结尾
- **`local_export` 可能不可用**：不可用时引导用户在 ChatCut Desktop 手动导出，不要反复调用不存在的接口

**优化：**

- 明确用户确认过的 BGM 音量基准（如 0.37）后续视频沿用，不必每次重调

**整理与修正：**

- 首次引入本 `CHANGELOG.md`，补齐 v1 → v2.2.0 的历史脉络
- 修正字幕布局示例坐标：原写 `left=90, width=900`，外框 x=90…990 越出自定安全区 x=108…972；改为贴合安全区的 `left=108, top=1436, width=864, height=100`
- 修正 `SKILL.md` 中 5 处被误写成右引号的开引号
- `使用说明.md` 与 `一键提示词.txt` 纳入仓库统一维护（此前只存在于分发 zip 里）

---

## v2.2.0 (2026-10-09)

字幕规则放宽：取消「同一时间严格一行」的硬限制，改为**单行优先、每卡最多两行**。

- 两行以**最长行**判宽，整卡完整外接框（含背景、描边、动画极值）仍须落在安全区内
- 动因：真实素材里个别长卡在 864px 安全区内天然超宽，强制单行会引发多轮无效修补（实测单次排障约 23 分钟）
- `maxLines` 写入禁令不变；`split_card` 降级为语义断句手段，不再是行数控制器
- 更正 `manage_transcript action=fix` 的索引基数：从 **0** 开始（原记录「从 1 开始」有误）

## v2.1.0 (2026-10-09)

固化字幕**破坏性操作禁令**与恢复流程。

- 明令禁止对字幕 item 写 `maxLines`（设 1 或设 2 都禁止），也禁止借一次批量样式重写顺手分卡——实测会清空全部字幕卡并连带删除素材转写
- `recovery-and-delivery.md` 新增「字幕卡清空 / 转写丢失」的分步恢复流程

## v2.0.0 (2026-10-09)

流程重写为 7 阶段优化版，替换 v1「一键出片」的口径。

- 阶段划分：预检 → 导入与转写 → A-Roll 清理与提速 → B-Roll 与同步画中画 → 字幕 → 音乐与总检 → 预览确认与导出
- 引入阶段账本 `scripts/run_state.py`（阶段计时、事件记录、预览版本门）
- 确立「剪完必须停下等用户确认预览，才能导出」的**确认门**与**版本门**
- 移除 `manifest.txt`、`references/install-chatcut.md`、`references/technical-guardrails.md` 与两个安装脚本；新增 `caption-quality.md`、`execution.md`、`recovery-and-delivery.md`、`validation.md` 以及 `chatcut_mcp.py`、`run_state.py`、`verify_export.py`

## v1.0.0 (2026-09-27)

从 `slbb-chatcut-oneshot` 派生单条版，收敛为「单条精品」路线。

- 上游：`github.com/zwj1379/slbb-chatcut-oneshot` @ `78031b0`
- 做法：本地 rsync 复制 + 定向改写（`SKILL.md` / `README.md` / `agents/openai.yaml` 三处去掉批量能力）
- 初版口径为「给 1 条主视频 → 全自动出片」，v2.0.0 起改为分阶段 + 人工确认
