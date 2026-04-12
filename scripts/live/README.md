# live — 直播控场 Agent

实时读取直播脚本并按节奏驱动 TTS 播报，同时捕获弹幕/礼物/进场互动，由两层决策引擎（规则 + LLM）判断是否回应以及如何回应，不会打乱既定直播节奏。

## 架构

```
MockEventCollector ──▶ event_queue ──▶ Orchestrator ──▶ tts_queue ──▶ TTSPlayer
                                           │                              │
                                     ScriptRunner                  Gemini TTS (Sulafat)
                                     (get_state)                    或 macOS say
                                           │
                                       LLMClient
                                    (Gemini 2.5 Flash)
```

四个并发组件各跑一个后台线程，主循环每 0.5s 轮询一次：

| 模块 | 文件 | 职责 |
|------|------|------|
| `ScriptRunner` | `script_runner.py` | 按 YAML 脚本定时推进段落 |
| `MockEventCollector` | `event_collector.py` | 回放模拟弹幕/礼物时间线 |
| `Orchestrator` | `orchestrator.py` | 两层决策，输出 TTS 任务 |
| `TTSPlayer` | `tts_player.py` | 队列消费，调用 Gemini TTS 播音 |

## 决策引擎（Orchestrator）

**第一层：规则**（毫秒级响应）

| 优先级 | 触发条件 | 行为 |
|--------|----------|------|
| P0 | 礼物价值 ≥ 50 元 | 立即 TTS 致谢 |
| P1 | 粉丝进场 | 立即 TTS 欢迎 |
| P2 | 含问号的弹幕 | 缓冲 → LLM 判断 |
| P3 | 其他弹幕/低价礼物 | 缓冲 → LLM 判断 |

**第二层：LLM**（批量触发）

满足以下任一条件时调用 Gemini 2.5 Flash：

- 缓冲区达到 `llm_batch_size`（默认 5 条）
- 距上次调用超过 `llm_interval`（默认 10s）且缓冲区非空

LLM 返回三种决策：`respond` / `defer` / `skip`，`respond` 时同时生成 `content`（回复文案）和 `speech_prompt`（朗读风格）。

## TTS 语音风格

TTS 内容以 `"{speech_prompt}：{text}"` 形式传入 Gemini，语气和语速由场景驱动：

- **P0 大额礼物** → 真情流露的惊喜，语气先快后慢
- **P1 粉丝进场** → 轻快热情，像见到老朋友
- **LLM 回复** → LLM 按互动内容自行生成风格描述
- **默认兜底** → 带货主播真情流露，语气自然有情绪起伏

默认声音：**Sulafat**（Gemini TTS 内置，效果最接近自然带货口吻）

## 快速开始

### 环境准备

```bash
cp .env.example .env   # 填入 GOOGLE_CLOUD_PROJECT
gcloud auth application-default login
```

`.env` 示例：

```
GOOGLE_CLOUD_PROJECT=your-project-id
```

### Mock 模式（无需 GCP，本地开发）

```bash
uv run scripts/live/agent.py --mock
```

- LLM 用简单规则替代，检测问号触发回复
- TTS 只打印日志，不调用 API

### 生产模式（Vertex AI + Gemini TTS）

```bash
uv run scripts/live/agent.py --script scripts/live/example_script.yaml
```

需要 `GOOGLE_CLOUD_PROJECT` 已设置且项目开启了 Vertex AI API。

### 加速回放（开发调试）

```bash
uv run scripts/live/agent.py --mock --speed 5
```

`--speed 5` 将模拟事件时间线加速 5 倍播放。

## 直播脚本格式

```yaml
meta:
  title: "产品介绍直播示例"
  total_duration: 3600   # 总时长（秒），仅作参考

segments:
  - id: "opening"
    duration: 120          # 段落持续时长（秒）
    interruptible: true    # false = 禁止互动打断（适合核心卖点讲解）
    text: |
      大家好，欢迎来到直播间！…
    keywords: ["欢迎", "开场"]

  - id: "product_core"
    duration: 300
    interruptible: false
    text: |
      接下来重点介绍这款产品…
    keywords: ["产品", "功能"]
```

`interruptible: false` 期间，所有互动事件进入缓冲，段落结束后再批量处理。

## 试听声音

```bash
uv run scripts/live/try_voices.py
uv run scripts/live/try_voices.py --text "感谢大家的支持！" --voices Kore Sulafat Aoede
```

## 运行测试

```bash
uv run pytest tests/live/ -v
```

## 文件索引

```
scripts/live/
├── agent.py            入口，组装并启动所有组件
├── orchestrator.py     两层决策引擎
├── script_runner.py    脚本段落定时推进
├── event_collector.py  模拟事件回放（待替换为真实 WebSocket）
├── tts_player.py       TTS 队列消费，调用 Gemini TTS
├── llm_client.py       Vertex AI Gemini 封装，输出 Decision
├── schema.py           共享数据结构（Event / ScriptSegment / Decision）
├── try_voices.py       声音试听脚本
└── example_script.yaml 示例直播脚本
```
