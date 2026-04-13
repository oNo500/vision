# ScriptSegment 字段重构设计

## Goal

将 `ScriptSegment.text` 拆分为职责清晰的三个字段，让主播在编辑脚本时一眼看懂每个字段的用途，同时让 AI 获得更结构化的上下文。

## Background

现有 `text` 字段承担了两种完全不同的职责：

1. `must_say=False` 时 — AI 的行动指令（"这段讲什么"）
2. `must_say=True` 时 — 需要逐字说出的台词

两种内容混在一个字段里，主播填写时容易困惑，AI 读取时也缺乏结构。

## New Data Model

```python
@dataclass
class ScriptSegment:
    id: str
    title: str             # 阶段名，如"产品介绍"、"限时促单"
    goal: str              # AI 指令：这段做什么、怎么和观众互动
    duration: int          # 阶段时长（秒）
    cue: list[str] = []    # 锚点话术：AI 在合适时机自然融入，自行安排节奏
    must_say: bool = False  # True = cue 必须全部说完；False = 尽量说但可跳过
    keywords: list[str] = []  # 话题关键词，保留不变
```

### 字段语义

| 字段 | 谁写 | 用途 |
|------|------|------|
| `title` | 主播填写 / AI 自动生成 | UI 展示阶段名，也出现在日志和控场面板 |
| `goal` | 主播填写 | 告诉 AI 这段的方向和任务，AI 以此为基础自由发挥 |
| `duration` | 主播填写 | 计时器时长，时间到自动进入下一段 |
| `cue` | 主播填写（可选） | 本段必须出现的话术锚点，可多条；AI 自行决定何时、如何融入 |
| `must_say` | 主播填写（可选） | 控制 `cue` 的完成要求：True = 全部必须说完，False = 尽量覆盖 |
| `keywords` | 主播填写（可选） | 话题提示，辅助 AI 联想相关内容 |

### 典型配置示例

**长段（自由发挥）**
```json
{
  "title": "产品介绍",
  "goal": "重点讲解益生菌修护屏障和72小时补水效果，结合观众皮肤问题互动，引导点购物车",
  "duration": 1200,
  "cue": [
    "2000亿活性益生菌，专门修护皮肤屏障",
    "72小时持续补水，上脸不黏腻",
    "0酒精0香精，敏感肌亲测可用"
  ],
  "must_say": false,
  "keywords": ["益生菌", "屏障", "敏感肌", "购物车"]
}
```

**短段（锚点必须全部说完）**
```json
{
  "title": "限时促单",
  "goal": "制造紧迫感，引导立即下单",
  "duration": 300,
  "cue": [
    "直播间专属价299，原价399",
    "买正装送同款旅行小样",
    "库存不多了，家人们冲"
  ],
  "must_say": true,
  "keywords": ["299", "限时", "库存", "小样"]
}
```

## AI Prompt 变化

当前 prompt 中的脚本段落部分：

```
=== 当前脚本段落 ===
段落ID：s2
参考原文：重点讲解益生菌...（goal + cue 混在一起）
关键词：益生菌, 屏障
剩余时间：1180s
必须贴近原文：否
```

重构后：

```
=== 当前脚本段落 ===
阶段：产品介绍
目标：重点讲解益生菌修护屏障和72小时补水效果，结合观众皮肤问题互动，引导点购物车
锚点话术（请在合适时机自然融入，尽量覆盖）：
  - 2000亿活性益生菌，专门修护皮肤屏障
  - 72小时持续补水，上脸不黏腻
  - 0酒精0香精，敏感肌亲测可用
关键词：益生菌, 屏障, 敏感肌, 购物车
剩余时间：1180s
```

`must_say=True` 时锚点说明改为"以下话术必须全部逐字说出"。

## Migration

旧数据（`text` 字段）迁移规则：
- `text` → `goal`
- `title` → `"段落N"`（按索引自动生成）
- `cue` → `[]`
- `must_say` 保持不变（旧字段含义收窄为仅控制 `cue` 完成要求）

迁移在 `PlanStore.get()` 读取时做一次性 normalize，不需要数据库 migration。

## UI Changes

脚本编辑器每个 segment 卡片从现在的：
```
[textarea: 脚本内容]
[时长] [必须贴近原文 checkbox]
[关键词 TagInput]
```

改为：
```
[drag handle ⠿]  [input: 阶段名称]           placeholder: "如：产品介绍、限时促单"
[textarea: AI 指令]         placeholder: "告诉 AI 这段做什么，比如：重点介绍益生菌成分，引导观众点购物车"
[TagInput: 锚点话术]        placeholder: "回车添加，AI 会在合适时机自然说出"
[必须全部说完 checkbox]     label: "锚点话术必须全部说完"
[时长] [关键词 TagInput]
```

现有的 up/down 按钮移除，改为拖拽排序。

## Drag and Drop

使用 `@atlaskit/pragmatic-drag-and-drop` 实现 segment 列表拖拽排序。

选型理由：用户指定，该库由 Atlassian 维护，无依赖、体积小、性能好，专为列表排序设计。

**实现要点：**
- 每个 segment 卡片左侧放 drag handle（`⠿` 图标），只有拖 handle 才触发拖拽，避免与卡片内输入框冲突
- 拖拽结束后调用 `savePlan` 持久化新顺序
- 拖拽中显示半透明占位符，提示插入位置
- 安装：`pnpm add @atlaskit/pragmatic-drag-and-drop` （仅 `apps/web`）

## Scope

- `src/live/schema.py` — `ScriptSegment` 字段变更
- `src/live/director_agent.py` — `build_director_prompt` 使用新字段
- `src/live/session.py` — `_build_and_start` 中 segment 构造更新
- `src/live/plan_store.py` — `get()` 加 normalize 兼容旧数据
- `apps/web/src/features/live/hooks/use-plan.ts` — `Segment` 类型更新
- `apps/web/src/app/(dashboard)/live/plans/[id]/page.tsx` — 编辑器 UI 更新（新字段 + 拖拽，移除 up/down 按钮）
- `scripts/seed_plans.py` — 示例方案更新为新字段结构
