# 直播控场 Agent 设计文档

**日期**：2026-04-12  
**状态**：已确认，待实现

---

## 目标

在抖音直播时，用一个 Agent 系统替代人工控场：

- 按直播脚本自动推进 TTS 播报内容
- 实时感知弹幕、进场、礼物等互动事件
- 在不打乱脚本节奏的前提下，适时与观众产生互动
- LLM 和 TTS 全部使用 Vertex AI，统一 GCP 账号

---

## 范围约定

**第一阶段（本 spec 范围）**：

- 弹幕采集使用 Mock 事件回放，不接真实平台
- TTS 开发阶段使用系统 TTS Mock，验证逻辑后再切 Vertex AI
- 不实现 UI 控制面板，通过命令行运行和日志观测

**后续阶段（不在本 spec 内）**：

- 接入真实弹幕源（抖音开放平台 WebSocket 或第三方聚合）
- 声音克隆、数字人驱动
- 多平台适配

---

## 架构

### 模块划分

```
scripts/live/
├── agent.py            # 入口：启动所有线程，协调生命周期
├── script_runner.py    # 脚本驱动器：按段落推进，维护当前进度状态
├── event_collector.py  # 事件采集：Mock 回放 / 后续替换为真实弹幕源
├── orchestrator.py     # 控场 Agent：两层决策核心
├── tts_player.py       # TTS 播报：异步队列消费，不阻塞决策层
├── llm_client.py       # LLM 封装：调用 Vertex AI Gemini，注入脚本上下文
└── schema.py           # 数据结构定义：Event、ScriptSegment、Decision
```

### 数据流

```
event_collector
      │ EventQueue
      ▼
  orchestrator ◄── script_runner（当前段落状态）
      │
      ├── 规则层：直接决策（P0/P1 事件）
      │
      └── LLM 层：Vertex AI Gemini 2.5 Flash（模糊地带）
                │
                ▼
           TTSQueue
                │
                ▼
          tts_player（独立线程，异步消费）
                │
                ▼
         Vertex AI Gemini-2.5-TTS → 系统音频输出
```

---

## 脚本格式

采用 YAML，支持段落级控制。

```yaml
# example_script.yaml
meta:
  title: "产品介绍直播"
  total_duration: 3600  # 总时长（秒）

segments:
  - id: "opening"
    duration: 120          # 预计时长（秒）
    interruptible: true    # 允许互动打断
    text: |
      大家好，欢迎来到今天的直播间...
    keywords: ["欢迎", "开场"]

  - id: "product_core"
    duration: 300
    interruptible: false   # 核心讲解，不允许打断
    text: |
      接下来给大家详细介绍这款产品的核心功能...

  - id: "qa_open"
    duration: 180
    interruptible: true
    text: |
      好，现在开放提问环节，有什么问题都可以在弹幕区问...
    keywords: ["提问", "互动"]
```

**字段说明**：

| 字段 | 含义 |
|------|------|
| `id` | 段落唯一标识 |
| `duration` | 预计时长（秒），控场 Agent 据此判断时间压力 |
| `interruptible` | `false` 时规则层直接拦截互动，不进 LLM |
| `text` | TTS 播报文本 |
| `keywords` | 辅助上下文，供 LLM 理解当前段落主题 |

---

## 控场 Agent：两层决策

### 第一层：规则过滤（毫秒级）

按优先级分级处理所有进入事件：

| 优先级 | 事件类型 | 条件 | 动作 |
|--------|---------|------|------|
| P0 | 礼物 | 价值 ≥ 50 元 | 立即生成感谢词 → TTS 队列 |
| P1 | 用户进场 | 是粉丝/关注者 | 生成欢迎词 → TTS 队列 |
| P2 | 弹幕 | 含问号或疑问词 | 交 LLM 判断 |
| P3 | 其他弹幕 | - | 写入 buffer，攒批处理 |

> [!IMPORTANT]
> 当前脚本段落 `interruptible: false` 时，所有事件降级为 P3（写 buffer），不触发任何 TTS 输出。

### 第二层：LLM 决策（模糊地带）

**触发条件**（满足其一）：

- buffer 积累 ≥ 5 条弹幕
- 距上次 LLM 调用已过 10 秒，且 buffer 非空

**LLM 输入上下文**：

```
系统提示：
  你是一个直播控场助手，负责决定是否回应观众互动。
  人设约束：[后续填充]
  禁用词：[后续填充]

当前状态：
  脚本段落：{current_segment.id}（{current_segment.keywords}）
  段落剩余时间：{remaining_seconds}s
  TTS 队列状态：{is_speaking}

待处理互动：
  {buffer_events}
```

**LLM 输出（结构化 JSON）**：

```json
{
  "action": "respond" | "defer" | "skip",
  "content": "回复文案（action 为 respond 时必填）",
  "interrupt_script": false,
  "reason": "决策理由（调试用）"
}
```

**字段约束**：

- `interrupt_script` 仅在当前段落 `interruptible: true` 时可为 `true`
- `action: defer` 表示本次不处理，留到下一轮重新判断
- `action: skip` 表示丢弃 buffer，继续脚本

---

## TTS 播报层

- **独立线程**，消费 `TTSQueue`，播完才取下一条，顺序保证
- **状态暴露**：`tts_player.is_speaking: bool`，供 orchestrator 决策时读取
- **开发阶段 Mock**：使用 `pyttsx3` 或 macOS `say` 命令，不消耗 Vertex AI 配额
- **生产阶段**：切换为 Vertex AI `Gemini-2.5-TTS`，中文普通话音色

**音频输出路径**（待定，依赖直播软件）：

- 虚拟声卡注入（如 BlackHole），让 OBS 捕获
- 或直接系统扬声器输出（本地测试用）

---

## Mock 事件回放

`event_collector.py` 支持两种模式：

```python
MOCK_SCRIPT = [
    {"type": "enter",   "user": "用户A", "is_follower": True,  "t": 5},
    {"type": "danmaku", "user": "用户B", "text": "这个怎么买？",   "t": 30},
    {"type": "gift",    "user": "用户C", "gift": "小心心", "value": 1,   "t": 60},
    {"type": "danmaku", "user": "用户D", "text": "主播加油！",    "t": 75},
    {"type": "gift",    "user": "用户E", "gift": "火箭",   "value": 500, "t": 90},
]
# 按 t 字段时间轴回放，模拟真实直播流速度
```

切换到真实弹幕源时，只需替换 `event_collector.py` 的事件发射逻辑，其余模块不变。

---

## 技术选型

| 组件 | 选型 | 备注 |
|------|------|------|
| LLM | Vertex AI Gemini 2.5 Flash | 速度快、成本低，适合实时决策 |
| TTS（生产） | Vertex AI Gemini-2.5-TTS | 2026 GA，中文音质优秀 |
| TTS（开发） | `pyttsx3` / macOS `say` | 零成本 Mock |
| 弹幕采集（现阶段） | Mock 事件回放 | 验证 Agent 逻辑 |
| 弹幕采集（后续） | 抖音开放平台 WebSocket | 合规路径 |
| 并发模型 | Python `threading` + `queue.Queue` | 简单够用，无需 asyncio |
| 语言 | Python 3.11+ | 与项目现有脚本一致 |

---

## 可观测性

控制台实时日志格式：

```
[10:32:01] SCRIPT  → 推进到段落 opening（剩余 115s）
[10:32:05] EVENT   → P1 进场 用户A（粉丝）
[10:32:05] TTS     → 排队：「欢迎用户A关注直播间！」
[10:32:06] TTS     → 播报中...
[10:32:30] EVENT   → P2 弹幕 用户B「这个怎么买？」→ 交 LLM 判断
[10:32:31] LLM     → action=respond reason=含购买疑问，当前段落可打断
[10:32:31] TTS     → 排队：「购买方式在直播间左下角链接哦～」
[10:33:30] EVENT   → P0 礼物 用户E 火箭×1（500元）
[10:33:30] TTS     → 排队：「感谢用户E送出火箭！太感动了！」
```

---

## 风险提示

> [!WARNING]
> 接入真实弹幕源前，必须评估合规风险（详见 `docs/ai-integration-risks.md`）：
> - 优先走抖音开放平台官方 WebSocket API
> - TTS 播报 AI 生成内容须在直播间显著标注
> - 避免非官方逆向抓取

---

## 后续扩展点（不在当前 spec 内）

- 接入真实弹幕源
- 填充人设约束和知识库文档
- 控制面板 UI（实时查看队列状态、手动插入内容）
- 声音克隆（CosyVoice 3.0 本地部署）
- 多平台支持（B站、视频号）
