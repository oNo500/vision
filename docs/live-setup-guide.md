# 直播控场 Agent 使用指南

如何准备自己的产品知识和直播脚本，让 Agent 帮你主持直播。

## 准备两个文件

| 文件 | 作用 |
|------|------|
| 产品知识 YAML | 告诉 LLM 你卖什么、怎么卖、不能说什么 |
| 直播脚本 YAML | 告诉 Agent 每个阶段讲什么、多久、能不能被打断 |

---

## 产品知识文件

路径：`scripts/live/data/product.yaml`（或自定义路径，用 `--product` 指定）

```yaml
product:
  name: "产品名称"
  tagline: "一句话卖点"
  price: 99              # 直播价
  original_price: 199    # 划线价

  selling_points:
    - "卖点一，具体、可感知"
    - "卖点二，解决用户痛点"
    - "卖点三，限时/稀缺感"

  faqs:
    - q: "常见问题一？"
      a: "回答，简短口语化"
    - q: "常见问题二？"
      a: "回答"

rules:
  banned_words:           # 违规词，LLM 生成时会避开
    - "最好"
    - "第一名"
    - "治疗"
    - "医美级"
    - "绝对"

  must_mention_per_segment:   # 某个段落必须提到的关键词
    product_core:
      - "纯植物"
      - "买二送一"
    closing:
      - "购物车"
      - "限时"
```

**写好产品知识的要点：**

- `selling_points` 写 3-5 条，越具体越好，LLM 会把它改写成自然的口播
- `faqs` 覆盖观众最常问的问题，答案口语化（不要像说明书）
- `banned_words` 参考平台违规词表，写进去后 LLM 会主动回避
- `must_mention_per_segment` 可以不填，填了之后 LLM 会在对应段落强调这些词

---

## 直播脚本文件

路径：`scripts/live/example_script.yaml`（或自定义路径，用 `--script` 指定）

```yaml
meta:
  title: "直播标题（仅备注用）"
  total_duration: 3600    # 总时长秒数，仅参考

segments:
  - id: "opening"
    duration: 120          # 这个段落持续多少秒
    interruptible: true    # 能否被互动打断
    text: |
      大家好，欢迎来到直播间！今天给大家带来……
      先点个关注再走哦，等会有福利～
    keywords: ["欢迎", "开场", "关注"]

  - id: "product_core"
    duration: 300
    interruptible: false   # 核心讲品段落，不被打断
    text: |
      接下来重点说说这款产品的三大优势……
    keywords: ["产品", "功能", "卖点"]

  - id: "qa_open"
    duration: 180
    interruptible: true
    text: |
      好，现在开放提问！弹幕区有任何问题都可以问……
    keywords: ["提问", "互动", "答疑"]

  - id: "closing"
    duration: 60
    interruptible: true
    text: |
      最后提醒大家，今天的价格只到今晚零点……
      点关注不迷路，下次直播见！
    keywords: ["结尾", "限时", "关注"]
```

**写好脚本的要点：**

- `text` 是参考原文，LLM 会改写成更自然的口播，**不会一字不差地念**
- `interruptible: false` 用于核心卖点讲解段落，此期间互动事件只缓冲不打断
- `duration` 控制段落时长，到时间自动切下一段
- `keywords` 帮助 LLM 知道这段重点是什么

---

## 启动方式

```bash
# 用自己的脚本和产品文件
PYTHONPATH=. uv run scripts/live/agent.py \
  --script scripts/live/data/my_script.yaml \
  --product scripts/live/data/my_product.yaml

# 加速测试（3倍速回放模拟弹幕）
PYTHONPATH=. uv run scripts/live/agent.py \
  --script scripts/live/data/my_script.yaml \
  --product scripts/live/data/my_product.yaml \
  --speed 3

# 接真实抖音弹幕
PYTHONPATH=. uv run scripts/live/agent.py \
  --script scripts/live/data/my_script.yaml \
  --product scripts/live/data/my_product.yaml \
  --douyin
```

> [!NOTE]
> 需要设置 `GOOGLE_CLOUD_PROJECT` 环境变量（或写在 `.env` 文件里）才能使用 Gemini TTS 和 LLM。

---

## 调整 LLM 行为

如果 LLM 输出的台词风格不对，在 `scripts/live/llm_client.py` 的 `_SYSTEM_PROMPT` 里调整：

- **人设**：把"经验丰富的带货主播"改成你想要的风格（知识型、亲切型、专业型等）
- **字数限制**：默认每句不超过 30 字，可以改
- **禁用规则**：比如"不提竞品"、"不承诺疗效"

如果某段话术必须原文播出（比如活动规则、免责声明），在脚本里加 `must_say: true`：

```yaml
  - id: "disclaimer"
    duration: 30
    interruptible: false
    must_say: true          # LLM 必须贴近原文，不自由发挥
    text: |
      本产品不能替代药物治疗，购买前请先咨询医生。
    keywords: []
```
