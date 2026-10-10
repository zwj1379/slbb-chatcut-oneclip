# 更新日志

本技能按语义化版本演进。**对外分发的版本以仓库 `main` 分支及同名 tag 为准**，桌面的 zip 只是某一版的快照。

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
