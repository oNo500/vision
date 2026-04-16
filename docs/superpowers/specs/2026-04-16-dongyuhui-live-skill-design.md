# dongyuhui-live Skill · 设计文档

> 面向滋补养生/食品品类、接地气版董宇辉风格的长直播（2h 带货）口播稿助手。
> 三件一体：生成器 / 检索器 / 审查员。个人使用，不外发。

---

## 1. 背景与目标

### 1.1 背景

- 用户是新手直播从业者，定位**食品 / 滋补养生**带货，单场时长约 2h
- 追求**接地气版董宇辉风格**：保留文学化比喻、人文叙事、知识种草、真诚自嘲与浅层文化味（常见诗词 / 成语 / 节气食养），**过滤冷僻古文**（《尚书》《道德经》类深典）
- 一次性生成 2h 完整稿不可持续（时间长、难改动、难迭代），需按场景按需产出
- 用户需要一个长期在侧的"风格教练"审查员，帮助快速内化风格

### 1.2 目标

构建一个 skill，满足三类使用方式的无缝切换：

1. **生成器**：按场景（`opening` / `product_story` / `qa_live` / `hard_push` 等 9 种）生成口播片段，句式单元级细颗粒
2. **检索器**：按类型 / 产品 / 场景 / 标签查询句式库，作为话术弹药
3. **审查员**：对用户贴入的稿件按 7 维度 + 合规检查给出 Top 3 建议与 1–2 处示范改写

### 1.3 非目标

- 不做一次性 2h 完整稿输出
- 不做 Web UI
- 不代替用户做创作决策（审查只提建议，不全稿重写）
- 不做多品类（医美、数码等）
- 不对接 vision 项目 `src/live/` 的 YAML ScriptRunner（用户明确：产出物是**长文 Markdown 口播稿**）
- 不外发（个人使用 → corpus 可含原话片段）

---

## 2. 设计原则（遵循项目 constitution）

- **Library-First**：Python 脚本仅用标准库 + `PyYAML`，不造轮子
- **MVP-First**：当下只做最小可用的三能力，多品类、自动化抓取、Web UI 均排除
- **TDD · NON-NEGOTIABLE**：`ingest_corpus.py` 先写测试再写实现
- **Functional First**：脚本主体纯函数 + 不可变数据
- **测试就近原则**：`scripts/ingest_corpus_test.py` 与实现同目录
- **无 emoji**：源码与注释无 emoji
- **合规优先**：滋补养生品类对广告法/食药监敏感，skill 内建合规过滤

---

## 3. Skill 身份与目录

### 3.1 身份

- **名称**：`dongyuhui-live`
- **位置**：`~/.claude/skills/dongyuhui-live/`（全局 skill，**不放在 vision 项目内**）
- **自包含**：skill 不依赖 vision 项目目录下的任何文件

### 3.2 目录结构

```
~/.claude/skills/dongyuhui-live/
├── SKILL.md                          # 入口 + 意图路由
├── references/                       # 方法论（相对稳定）
│   ├── style-principles.md           # 风格内核 + 红线
│   ├── phrase-library.md             # 打底句式（~80 条抽象仿写）
│   ├── review-checklist.md           # 审查 7 维度 + 合规
│   ├── scene-templates.md            # 9 场景 + 2h 骨架示例
│   └── category-knowledge.md         # 滋补养生品类常识（中医食养/节气/功效边界）
├── products/                         # 产品事实底座
│   ├── README.md                     # 产品档案录入规范
│   ├── _defaults/
│   │   └── compliance-tonic-health.md       # 滋补养生通用合规打底清单
│   └── <product-slug>/               # 每产品一个目录（初始为空，用户陆续补）
│       ├── profile.md
│       └── assets/
├── corpus/                           # 风格弹药（动态扩张）
│   ├── README.md                     # 语料录入规范（frontmatter）
│   ├── index.md                      # 索引文件（ingest 脚本维护）
│   ├── seed/                         # 用户手动录入
│   └── ingested/                     # 脚本批量导入
└── scripts/
    ├── ingest_corpus.py              # 语料注入器
    └── ingest_corpus_test.py         # 就近测试
```

### 3.3 职责分层

- **references/** = 怎么说（风格方法论）
- **products/** = 说什么（产品事实 + 合规边界）
- **corpus/** = 别人怎么说（董宇辉原文参考）

三层分离 · 互不污染 · 独立迭代。

---

## 4. 意图路由

### 4.1 路由表

| 用户话语特征 | 路由到 | 输入要求 |
|---|---|---|
| "帮我审一下 / 看看这段 / 挑毛病 / review" + 贴入文本 | **REVIEW** | 必填：待审文本；选填：场景、产品 |
| "写一段 / 来一段 / 生成 …… 的 Hook / 故事 / 段落" | **GENERATE** | 必填：场景 + 产品；选填：时长、情绪 |
| "有没有 / 查一下 / 找一句 …… 的比喻 / 金句 / Hook / 过渡" | **SEARCH** | 必填：句式类型或关键词 |
| 话语含糊（"帮我写直播稿"） | **反问澄清** | 多选反问，一次锁定 |

### 4.2 歧义处理

- 同一句话命中多意图 → 优先级 `REVIEW > SEARCH > GENERATE`
- 含糊时用多选反问（"A 审一下 B 写一段新的 C 查句式库"），**只问一次**

### 4.3 上下文延续

- 会话内首次指定的产品 / 场景 / 情绪在后续调用中默认沿用，除非用户改口
- 避免重复追问

---

## 5. 分支 1 · 生成器（GENERATE）

### 5.1 场景枚举（9 种）

| 场景 ID | 典型时长 | 用途 | 促单强度 |
|---|---|---|---|
| `opening` | 5–10 min | 开场暖场、建立人设、预告今晚品 | 无 |
| `product_story` | 10–15 min | 产品背后的人/地/工艺/节气 | 弱 |
| `product_detail` | 8–12 min | 成分、功效、食用方法 | 弱 |
| `metaphor_moment` | 2–5 min | 纯文学化比喻片段 | 无 |
| `qa_live` | 5–10 min | 应对弹幕问题 | 中 |
| `soft_push` | 3–5 min | 软性促单（故事收尾 + 福利铺垫） | 中 |
| `hard_push` | 2–3 min | 明确上链接催单（新手友好版） | 强 |
| `transition` | 30s–1min | 话题/品之间过渡 | 无 |
| `closing` | 5 min | 收尾金句 + 引导关注 | 无 |

2h 骨架示例（参考，非硬约束）：

```
opening(8) → product_story(12) → product_detail(10) → metaphor_moment(3) →
soft_push(4) → qa_live(8) → hard_push(3) → transition(1) →
[第二品循环] → closing(5)
```

### 5.2 句式单元（9 类）

`HOOK` / `METAPHOR` / `STORY` / `KNOWLEDGE` / `TRANSITION` / `SELF_TALK` / `GOLDEN` / `SOFT_CTA` / `HARD_CTA`

### 5.3 调用契约

用户："写一段阿胶糕的 `product_story`"

skill 内部：

1. 确认 scene + product（沿用会话上下文或反问一次）
2. 读 `references/style-principles.md` → 风格底色
3. 读 `products/<slug>/profile.md` → 事实 + `claims_forbidden` / `forbidden_words`
4. 查 `corpus/index.md` → 取 2–3 条同 scene / segment_type 锚点
5. 空库时降级到 `references/phrase-library.md` 打底
6. 按 `scene-templates.md` 对应模板组装
7. **输出前合规过滤**：命中 `forbidden_words` → 自动改写并在末尾 notes 中说明
8. 输出 Markdown，句前加 `<!-- TYPE -->` 注释：

```markdown
<!-- HOOK -->
你有没有留意过秋天最凉的那阵风？……
<!-- STORY -->
山东东阿那口井，老辈人说……
<!-- METAPHOR -->
这块糕放嘴里，像一整个冬天的阳光被压扁了……
<!-- GOLDEN -->
秋冬不是熬过去的，是补回来的。
```

### 5.4 落盘策略

- 默认**不落盘**，直接返回 Markdown
- 用户显式说"存一下 / 保存"才写盘
- 路径由**当前会话的工作目录**决定，不在 skill 内硬编码：
    - 如果当前在 vision 项目内（`cwd` 含 `code/vision`）→ 默认建议 `output/live/scripts/YYYY-MM-DD-<product>-<scene>.md`
    - 否则 → 默认建议 `./YYYY-MM-DD-<product>-<scene>.md` 并请求用户确认
- skill 本体无状态，不持有任何项目路径引用

---

## 6. 分支 2 · 检索器（SEARCH）

### 6.1 检索维度（全部可组合）

- 句式类型：9 种之一
- 产品 / 品类：具体 product slug 或上位类 `滋补养生`
- 场景：9 个场景 ID 之一
- 标签：`#画面感` / `#产地` / `#情感` / `#节气` / `#反套路` …

### 6.2 执行流程

1. 读 `corpus/index.md`（一行一条摘要，可扛 500+ 条）
2. 按条件 grep 命中候选
3. 按需打开具体片段文件读全文
4. 库空或零命中 → 坦白 + 降级询问："库里没有，要不要我现生成一条？"（一键跳 GENERATE）

### 6.3 返回格式

```markdown
## 候选 1（来自 phrase-library.md · HOOK · 画面感）
"秋分那天早上的风……"

## 候选 2（来自 corpus/seed/20240915-01.md · HOOK · 画面感）
"你有没有在凌晨 4 点的厨房……"
```

每条标明出处，用户自行判断是锚点参考还是可直接用。

---

## 7. 分支 3 · 审查员（REVIEW）

### 7.1 审查维度（7 + 1）

| # | 维度 | 评分 | 检查点 |
|---|---|---|---|
| 1 | 文学化程度 | 1–5 | 比喻密度 / 画面感 / 是否信息堆砌 |
| 2 | 故事性 | 1–5 | 有无带入人/地/事；故事具体度 |
| 3 | 接地气程度 | 1–5 | 有无深古文、书面语过重、新手人设冲突 |
| 4 | 节奏感 | 1–5 | 长短句交替、换气点 |
| 5 | 促单融入度 | 1–5 | 逼单自然还是生硬 |
| 6 | 金句可剪辑度 | 1–5 | 有无 1–2 句可截图传播 |
| 7 | 违和词检测 | ✅/⚠️ | 非董宇辉式表达（网感、保健品话术、直播口水） |
| + | **合规检查** | ✅/⚠️ | 踩中当前产品 `claims_forbidden` / `forbidden_words` |

### 7.2 输出模板

```markdown
## 审查报告

**总体印象**：<一句话定性>

**维度得分**
- 文学化 4/5：<简评>
- 故事性 2/5 ⚠️：<具体缺什么>
- 接地气 5/5
- 节奏感 3/5：<具体问题>
- 促单 2/5 ⚠️：<具体问题>
- 金句 3/5：<简评>
- 违和词：⚠️ <列出具体词>
- 合规：⚠️ <命中的禁用语>

**Top 3 修改建议**
1. [原文位置] → [改法概述] → [替代句示例]
2. ...
3. ...

**改后示例**（挑 1–2 处示范重写）
原文：... → 改后：...
```

### 7.3 学习闭环

- 审查员不代写全稿，只给 Top 3 + 1–2 示范
- 同一维度连续 3 次低分 → 主动指向 `references/` 对应章节

---

## 8. 产品档案（products/）

### 8.1 档案规范（`products/<slug>/profile.md`）

```markdown
---
slug: ejiao-gao
name: 东阿阿胶糕
category: [滋补养生, 食品]
sku: EJG-500G-2024
price: 299
origin: 山东东阿
maker: XX 品牌
cert: [SC12345, 检测报告-2024-08]
shelf_life: 12 个月
storage: 阴凉干燥处
target_audience: [久坐白领, 经期女性, 气血不足]

claims_allowed: [补气血（膳食补充角度）, 驱寒暖胃, 日常滋补]
claims_forbidden: [治疗贫血, 治愈, 药效替代]
forbidden_words: [根治, 替代药物, 立竿见影]
---

# 产品故事
<真实可考的产地/工艺素材，非文学创作>

# 成分与工艺
<驴皮来源 / 熬制工艺 / 关键成分>

# 食用方法
<每日份量 / 送服方式>

# 常见答疑
Q: 孕妇能吃吗？A: ...

# 促单节点参考
<满减 / 赠品 / 限时福利>
```

### 8.2 合规打底（`products/_defaults/compliance-tonic-health.md`）

- 基于广告法 / 食品安全法 / 保健食品禁用语
- 列出滋补养生品类通用禁用词与违规声称模式
- 新建产品时从此清单 copy 到 `claims_forbidden` / `forbidden_words`，再按产品微调

### 8.3 无档案降级

- 生成器 / 审查员检测不到对应 `profile.md` → 明确告知用户"无产品档案，仅用品类常识创作，不会引用具体产地/批次/价格"
- 不中断流程，只缩窄引用范围

---

## 9. 语料库（corpus/）

### 9.1 录入规范（frontmatter）

```markdown
---
id: 20240915-ejiao-story-01
source: 与辉同行 · 2024-09-15
source_url: https://...
segment_type: STORY
product_category: [滋补养生, 食品]
product: 阿胶糕
scene: product_story
tags: [产地, 情感, 画面感, 节气]
length_sec: 45
style_score:
  literary: 4
  story: 5
  grounded: 5
  rhythm: 4
notes: 典型产地故事，强画面感
---

<原文内容，不二次加工>
```

### 9.2 约束

- `segment_type`、`scene` 字段使用固定枚举
- 缺字段 → 入库前必须补齐
- 一条一文件，文件名 = `id`
- `seed/`（手录）与 `ingested/`（脚本导入）分目录

### 9.3 索引文件（`corpus/index.md`）

每次导入后由 `ingest_corpus.py` 自动维护，一行一条：

```markdown
- [20240915-ejiao-story-01](seed/20240915-ejiao-story-01.md) · STORY · 阿胶糕 · [产地, 情感] · "你有没有在凌晨 4 点的厨房……"
```

Claude 执行 SEARCH / GENERATE 时**只先读 index**，命中后再打开具体片段，避免上下文爆炸。

---

## 10. 语料注入脚本（`scripts/ingest_corpus.py`）

### 10.1 两条路径

#### 路径 A · 文本清洗（主路径 · 零外部依赖）

```bash
python ~/.claude/skills/dongyuhui-live/scripts/ingest_corpus.py \
  --from-text ./raw.txt \
  --source "与辉同行 2024-09-15" \
  --product 阿胶糕
```

- 输入：TXT / SRT / VTT
- 流程：按段切分 → 交互式提示，用户逐段选 `segment_type` / `scene` / `tags` → 写入 `corpus/ingested/` + 更新 `index.md`
- 交互**不走 LLM**，只做结构化录入

#### 路径 B · URL 全流程（次路径 · 可选）

```bash
python ingest_corpus.py --from-url <url> --source ... --product ...
```

- 依赖：`yt-dlp`、`faster-whisper`（或 `whisper.cpp`）、`ffmpeg`
- 依赖缺失 → 打印清晰安装指引后 exit（不自动装、不隐性失败）
- 成功转录后自动交给路径 A 继续

### 10.2 脚本原则

- 纯 Python 标准库 + `PyYAML`
- 单文件 ≤ 300 行
- 不联网（路径 B 的 yt-dlp 除外）
- 所有"风格判断"交人工确认，脚本只做结构化录入
- 重复 `id` 拒绝覆盖（需 `--force` 显式覆盖）

### 10.3 测试（TDD · 必做）

`scripts/ingest_corpus_test.py` 覆盖：

1. 路径 A · 按段切分正确（给定 mock SRT / TXT）
2. 路径 A · frontmatter 必填缺失 → 报错退出
3. 路径 A · 写入后 `index.md` 正确追加
4. 路径 A · 重复 `id` → 拒绝覆盖（无 `--force`）
5. 路径 B · 无 `yt-dlp` / `whisper` → 清晰错误退出（mock `shutil.which`）

**先写测试，再写实现**。

---

## 11. SKILL.md 骨架

```markdown
---
name: dongyuhui-live
description: Use for writing or reviewing Chinese 2h live带货 scripts in "Dong Yuhui 接地气版" style, for 滋补养生/食品 products. Triggers on: 写直播稿 / 帮我审一下 / 有没有……的 Hook / 来一段……故事 / review live script / 董宇辉风格.
---

# dongyuhui-live

滋补养生品类 · 接地气版董宇辉风格 · 长直播口播稿三件一体助手（生成 / 检索 / 审查）。

## 使用前置

- 推产品前确认 `products/<slug>/profile.md` 存在；无则走"无档案降级模式"
- 所有输出须通过 `claims_forbidden` + `forbidden_words` 过滤

## 意图路由
<4.1 表格全量嵌入，歧义优先级：REVIEW > SEARCH > GENERATE>

## 分支 1 · GENERATE
<5.3 步骤 1–8>

## 分支 2 · SEARCH
<6.2 步骤 + 6.3 返回格式>

## 分支 3 · REVIEW
<7.1 维度 + 7.2 模板 + 7.3 闭环>

## 降级
- 无产品档案 → 只用品类常识
- 空 corpus → 退回 phrase-library.md
- 同维度连续 3 次低分 → 主动指向 references 对应章节

## 不做的事
- 不一次性出完整 2h 脚本
- 不代替创作决策
- 不自动装 yt-dlp / whisper
- 不外发
```

---

## 12. 交付清单（MVP）

| # | 文件 | 状态 |
|---|---|---|
| 1 | `SKILL.md` | 新写 |
| 2 | `references/style-principles.md` | 新写（含红线） |
| 3 | `references/phrase-library.md` | 新写（~80 条抽象仿写打底） |
| 4 | `references/review-checklist.md` | 新写（7 维度 + 合规） |
| 5 | `references/scene-templates.md` | 新写（9 场景 + 骨架示例） |
| 6 | `references/category-knowledge.md` | 新写（滋补养生品类常识） |
| 7 | `products/README.md` | 新写（档案录入规范） |
| 8 | `products/_defaults/compliance-tonic-health.md` | 新写（合规打底清单） |
| 9 | `corpus/README.md` | 新写（frontmatter 规范） |
| 10 | `corpus/index.md` | 空壳（脚本维护） |
| 11 | `scripts/ingest_corpus.py` | 新写（≤ 300 行） |
| 12 | `scripts/ingest_corpus_test.py` | 新写（TDD 覆盖 5 场景） |

**不纳入 MVP**：
- 具体产品 `profile.md`（用户后续手录）
- `corpus/seed/*.md` 具体条目（用户后续手录）

---

## 13. 验收

### 13.1 自动化

`scripts/ingest_corpus_test.py` 全绿。

### 13.2 人工回放（3 场景）

1. **审查回放**：给一段含深古文 + 保健品口水的稿 → 审查员输出 7+1 维度 + Top 3 建议 + 命中禁用词
2. **生成回放**："写一段阿胶糕 `product_story`"（先手录一条 `products/ejiao-gao/profile.md`）→ 生成片段包含 profile 事实 + 文学化比喻 + 无 `forbidden_words`
3. **检索回放**："有没有适合开场的画面感 Hook" → 空库降级到 `phrase-library.md`，返回 3 条候选

---

## 14. 约束与风险

| 风险 | 缓解 |
|---|---|
| 语料库冷启动（空库） | `phrase-library.md` 80 条打底 + 降级提示 |
| 合规踩线（广告法） | 双重保险：产品级 `claims_forbidden` + 品类级 `_defaults/compliance-tonic-health.md` |
| 风格漂移（用多了像通用 AI 文案） | 审查员 Top 3 机制强制学习，`style-principles.md` 红线明确 |
| 语料版权 | 个人使用 · 不外发 · 不入公开仓库 |
| 脚本依赖缺失 | 路径 A 零依赖兜底，路径 B 仅清晰报错不自动装 |

---

## 15. 未来扩展（不在 MVP）

- 批量抓取（`ingest_corpus.py` 扩展多 URL / 频道订阅）
- 多品类扩展（医美 / 数码）：改 `category-knowledge.md` + `_defaults/`
- 接入 vision `src/live/` ScriptRunner：增加 YAML 导出模式
- 自动打标（LLM 辅助 `segment_type` / `tags` 预填 + 人工 confirm）

---

**Version**: 1.0.0 | **Date**: 2026-04-16 | **Owner**: xiu
