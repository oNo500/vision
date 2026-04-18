# RAG 话术库设计 — DirectorAgent 实时检索接入

## 背景

直播生成内容想"跟产品走、符合我的风格",当前 DirectorAgent 只有 plan
里的 product/persona/cue 三样固定上下文,无法利用更大的话术沉淀
(脚本、爆款片段、产品手册、社群问答)。

需要一个本地 RAG,给每次 LLM 调用注入 3-5 条最相关的话术片段。

## 目标

- DirectorAgent 每次 fire 时,以当前 segment goal + 最近弹幕为 query,
  检索话术库,塞进 prompt
- 检索延迟 p95 < 150ms,不影响句间无空隙
- 检索失败时静默降级,不阻塞生成
- 数据层与索引独立,方便重建 / 增量更新
- 不引入 LangChain / LlamaIndex,保持与 SessionMemory 同一风格的自研

## 非目标(MVP 不做)

- Rerank(先看 base 召回够不够,不够再加)
- Hybrid search(向量 + BM25)
- 跨场记忆(MVP 只做 plan 级索引)
- Query rewriting(LLM 改写 query 再检索)
- Web UI 上传/编辑话术(MVP 靠 CLI 工具 + 文件)
- 句级索引(MVP 只做段级,将来再加一层)

---

## 架构

```
data/talk_points/<plan_id>/           ← 用户放原始文档(markdown/txt)
    scripts/                          ← B: 自己写的脚本
    competitor_clips/                 ← C: 爆款话术
    product_manual/                   ← D: 产品文档
    qa_log/                           ← E: 社群问答

                    │
                    │  cli: uv run python -m src.live.rag build <plan_id>
                    ▼
.rag/<plan_id>/chroma.sqlite          ← 持久化索引,跟 vision.db 同级
.rag/<plan_id>/meta.json              ← 索引元数据(build_time, chunk_count, 源文件 hash)

                    │
                    │  runtime
                    ▼
SessionManager.start()
    └── load_plan 时尝试打开 .rag/<plan_id>/
        └── TalkPointRAG(collection, embedder)
            └── 传入 DirectorAgent

DirectorAgent._fire():
    1. 拿 segment_state + events
    2. rag.query(segment.goal, [e.text for e in events if e.type=="danmaku"][-3:])
       → list[TalkPoint] 或 []  (miss 时)
    3. build_director_prompt(..., talk_points=...)
       → RAG 段渲染到 prompt
    4. LLM 调用
    5. 若 talk_points 为空,publish EventBus 事件 {"type": "rag_miss"}
       前端可选展示
```

## 数据模型

### 原始文档

- 格式:Markdown 或纯文本(`.md` / `.txt`)
- 结构:按 `data/talk_points/<plan_id>/<category>/*.md` 放置
- 约定:一个 `.md` 文件就是一个"文档",可任意长度
- 类别:`scripts` / `competitor_clips` / `product_manual` / `qa_log`
  四个目录,其他目录忽略

### Chunk

```python
@dataclass
class TalkPoint:
    id: str             # sha256(source_path + chunk_index)[:16]
    text: str           # chunk 内容(目标 ~500 字,见 chunking)
    source: str         # 源文件相对路径,e.g. "scripts/opening.md"
    category: str       # scripts / competitor_clips / product_manual / qa_log
    chunk_index: int    # 在源文件内的位置
```

### 索引元数据(`.rag/<plan_id>/meta.json`)

```json
{
  "build_time": "2026-04-18T12:00:00Z",
  "chunk_count": 312,
  "embedder": "BAAI/bge-base-zh-v1.5",
  "sources": {
    "scripts/opening.md": {"sha256": "abc...", "chunks": 4},
    "product_manual/spec.md": {"sha256": "def...", "chunks": 18}
  }
}
```

元数据用于 incremental rebuild(未变的文件跳过)。

---

## Chunking 策略

目标:按**段落**切,尽量保持语义完整,~500 字一块。

算法(纯函数 `chunk_markdown(text) -> list[str]`):

1. 按空行拆分 paragraph 列表
2. 连续拼接 paragraphs,遇到"拼完就超过 600 字"则在前一段末尾切
3. 单段超过 600 字 → 按句号/问号/感叹号拆成句子,再装填
4. 最终 chunk 长度在 200-600 字之间,平均 ~500 字

重叠:**不做**。段级索引里重叠收益小,且双倍消耗检索预算(chunk 数翻倍)。

Markdown 特殊处理:

- 标题(`#` / `##` / `###`)作为"硬分隔",chunk 不跨标题
- 代码块(` ``` `)整体保留为一个 chunk,不拆
- 列表项(`- ` / `1. `)保持在同一 chunk 内(不从列表中间切)

---

## Embedding

- **模型**:`BAAI/bge-base-zh-v1.5`(HuggingFace 加载,~400MB)
- **运行**:`sentence-transformers` 库,CPU 推理(M 系列 ~100ms)
- **输出**:768 维 float32
- **加载时机**:进程首次 build 或首次 query 时 lazy load,全进程共享一个 model 实例
- **缓存**:无额外缓存(SentenceTransformer 自带 HF disk cache)

### 为什么 bge-base 不 small?

Q4 对齐结论:允许 150ms 预算,换 +5-10 分召回质量。bge-small 30ms
但中文质量明显弱,作为后置降级方案(改配置即可切换)。

### query 构造

```python
def _build_query(segment_goal: str, recent_danmaku: list[str]) -> str:
    danmaku_part = " ".join(recent_danmaku[-3:])
    return f"{segment_goal} {danmaku_part}".strip()
```

不做 query rewriting。

---

## 向量库

- **选型**:ChromaDB `PersistentClient`
- **路径**:`.rag/<plan_id>/chroma.sqlite`(随 vision.db 一起备份)
- **Collection**:每个 plan 一个,名为 `talkpoints_<plan_id>`
- **Distance metric**:`cosine`(bge 推荐)
- **where 过滤**:预留 `category` 字段,MVP 不用
- **容量**:十几个文档 → 几百 chunks。ChromaDB 承受百万级,远超需求

### 为什么 ChromaDB 不 sqlite-vec / numpy?

- ChromaDB 零配置、API 简单、社区活跃、中文 embedding 生态好
- sqlite-vec 更轻但 Python binding 不成熟
- numpy 手写对几百 chunk 够用但不好支持增量 add/delete
- 权衡后 ChromaDB 最合适

---

## 检索

```python
class TalkPointRAG:
    def __init__(self, collection, embedder, min_score: float = 0.5):
        self._collection = collection
        self._embedder = embedder
        self._min_score = min_score   # cosine similarity 阈值

    def query(
        self,
        segment_goal: str,
        recent_danmaku: list[str],
        k: int = 5,
    ) -> list[TalkPoint]:
        query_text = _build_query(segment_goal, recent_danmaku)
        embedding = self._embedder.encode(query_text)
        results = self._collection.query(
            query_embeddings=[embedding.tolist()],
            n_results=k,
        )
        # Chroma 返回 distance(cosine),转成 similarity = 1 - distance
        points = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = 1 - dist
            if similarity < self._min_score:
                continue
            points.append(TalkPoint(
                id=meta["id"],
                text=doc,
                source=meta["source"],
                category=meta["category"],
                chunk_index=meta["chunk_index"],
            ))
        return points
```

阈值 `min_score = 0.5`:cosine sim < 0.5 的 chunk 视为不相关,过滤掉。
宁少勿错 — 直播场景错的比没有更伤。

---

## DirectorAgent 集成

### prompt 新增段

```
=== 相关话术参考(可自然化用,非必读)===
  [scripts/opening.md] 大家好欢迎来到直播间,今天给大家带来新款超能面膜…
  [product_manual/spec.md] 这款面膜的核心成分是纯植物萃取,72 小时锁水…
  [competitor_clips/viral.md] 姐妹们这个真的不一样,我用完之后…
```

原则:

- 显式告诉 LLM "可自然化用,非必读",避免照抄
- 标注来源(方括号前缀),便于调试追溯
- 每条截断到前 200 字,避免 prompt 爆炸
- 最多 5 条,避免 LLM 被参考淹没

### build_director_prompt 改动

签名增加 `talk_points: list[TalkPoint] | None = None`:

```python
def build_director_prompt(
    script_state, knowledge_ctx, recent_events,
    memory=None, persona_ctx="",
    talk_points=None,       # 新增
) -> str:
    ...
    rag_section = ""
    if talk_points:
        lines = []
        for tp in talk_points[:5]:
            snippet = tp.text[:200]
            lines.append(f"  [{tp.source}] {snippet}")
        rag_section = "=== 相关话术参考(可自然化用,非必读)===\n" + "\n".join(lines) + "\n\n"
    ...
```

### DirectorAgent._fire 改动

```python
def _fire(self, script_state, recent_events):
    ...
    talk_points = []
    if self._rag is not None:
        try:
            danmaku_texts = [
                e.text for e in all_events
                if e.type == "danmaku" and e.text
            ]
            talk_points = self._rag.query(
                segment_goal=script_state.get("goal", ""),
                recent_danmaku=danmaku_texts,
                k=5,
            )
        except Exception as e:
            logger.warning("RAG query failed: %s", e)   # 降级,继续走
        if not talk_points:
            self._bus_publish({"type": "rag_miss", ...})   # 通过 callback

    prompt = build_director_prompt(
        ..., talk_points=talk_points,
    )
    ...
```

注意:

- RAG 异常/空返回都走降级,**不阻塞 LLM 调用**
- `rag_miss` 事件通过 SessionManager 注入的 callback 发出,保持
  DirectorAgent 与 EventBus 解耦(沿用现有约定)

### SessionManager 装配

```python
from src.live.rag import TalkPointRAG, load_rag_for_plan

def _build_and_start(...):
    ...
    rag = None
    if active_plan:
        try:
            rag = load_rag_for_plan(active_plan["id"])
        except Exception as e:
            logger.warning("RAG unavailable for plan %s: %s", active_plan["id"], e)

    director = DirectorAgent(
        ...,
        memory=memory,
        rag=rag,                          # 新增
        on_rag_miss=self._on_rag_miss,    # 新增,发 EventBus
    )
```

`load_rag_for_plan` 找不到索引(用户还没 build)→ 返回 None,
DirectorAgent 接收 `rag=None` 相当于关闭 RAG,一切照旧。

---

## CLI 工具

`src/live/rag_cli.py`,入口 `python -m src.live.rag_cli`:

```bash
# 构建索引
uv run python -m src.live.rag_cli build <plan_id>

# 查询测试(开发用)
uv run python -m src.live.rag_cli query <plan_id> "产品介绍"

# 查看元数据
uv run python -m src.live.rag_cli info <plan_id>

# 清除
uv run python -m src.live.rag_cli clear <plan_id>
```

`build` 逻辑:

1. 扫描 `data/talk_points/<plan_id>/` 四个子目录下所有 `.md` / `.txt`
2. 对比 meta.json 里的 sha256,未变文件跳过(增量 build)
3. 变化文件:删除旧 chunks → chunk_markdown → embed → add 到 collection
4. 写回 meta.json

---

## 延迟预算

| 阶段 | 预算 | 备注 |
|---|---|---|
| embedding(bge-base CPU) | 100-150ms | M 系列 Mac 实测 |
| ChromaDB query(k=5, ~几百 chunk) | 5-20ms | 小规模下可忽略 |
| 阈值过滤 + 对象构造 | <5ms | Python dict 操作 |
| **合计 p95** | **~170ms** | 余量 30ms |

加到 DirectorAgent 链路:

```
tick → state + events → RAG 170ms → build_prompt → LLM 1-3s → 入队
```

RAG 远小于 LLM call,**不成为瓶颈**。

---

## 测试

### `src/live/rag_chunking_test.py`

纯函数 `chunk_markdown`:

- 短文档(<200 字)→ 1 chunk
- 多段落拼接 → 达到 ~500 字切
- 单段超长 → 按句号切
- 标题作为硬分隔
- 代码块不拆
- 列表保持完整

### `src/live/rag_test.py`

TalkPointRAG 行为(embedder mock 掉,返回固定向量):

- query 返回相似度高于阈值的结果
- 低于阈值的过滤掉
- 空 collection → 返回空 list
- embedder 抛异常 → 传递给 caller(由 DirectorAgent 兜底)

### `src/live/rag_integration_test.py`

真实 bge-base + ChromaDB,慢测试(`pytest.mark.slow`):

- build 一个临时 plan,加几篇 md
- query 能返回预期 top-k
- 增量 build(改一个文件,其他跳过)

### DirectorAgent 集成

`director_agent_rag_test.py`:

- mock rag.query 返回固定 TalkPoints
- 断言 prompt 包含 "=== 相关话术参考 ==="
- 断言话术按 `[source]` 格式渲染
- mock rag.query 抛异常 → LLM 仍被调用(降级生效)
- rag=None → prompt 不含 RAG 段

---

## 依赖

新增:

```
chromadb >= 0.5.0        # ~10MB
sentence-transformers >= 3.0.0    # ~20MB + transformers
```

`sentence-transformers` 会拖入 `torch`(CPU 版 ~200MB)+ `transformers`。

**镜像体积影响**:
- 之前:~80MB(litellm 拉了 tiktoken/tokenizers)
- 加 RAG 后:~500MB(torch CPU 占大头)

如果体积是硬约束,后续可以切换到 `onnxruntime` + bge-base ONNX 版,
torch 不再需要,缩到 ~150MB。MVP 不做这个优化。

---

## 影响面

| 文件 | 改动 | 估算 |
|---|---|---|
| `src/live/rag.py` | 新建 — TalkPointRAG, load_rag_for_plan, _build_query | ~150 行 |
| `src/live/rag_chunking.py` | 新建 — chunk_markdown 纯函数 | ~80 行 |
| `src/live/rag_cli.py` | 新建 — CLI build/query/info/clear | ~100 行 |
| `src/live/rag_*_test.py` | 新建 — 三个测试文件 | ~300 行 |
| `src/live/director_agent.py` | `_fire` 加 RAG 查询 + build_prompt 加参数 | +30 行 |
| `src/live/director_agent_rag_test.py` | 新建集成测试 | ~80 行 |
| `src/live/session.py` | `_build_and_start` 加载 RAG,注入 DirectorAgent | +20 行 |
| `pyproject.toml` | + chromadb, sentence-transformers | +2 行 |

合计 ~750 行(含测试 ~400 行)。

---

## 风险

| 风险 | 对策 |
|---|---|
| bge-base 在低质数据上召回差 | 阈值过滤 + 日志 rag_miss;数据不够补数据,不调阈值 |
| ChromaDB 首次 query 冷启动慢(加载 sqlite) | SessionManager.start 时 load_rag_for_plan 预热一次 query |
| Embedder 初始化慢(HF 下载模型) | 首次启动提示用户"首次使用下载模型中";后续走 HF 缓存 |
| LLM 被参考话术误导,照抄 | prompt 明说"非必读,自然化用";输出 cue_hits 校验仍走 SessionMemory |
| 数据格式不一致(md 混 txt) | chunk_markdown 同样处理 txt(空行分段规则相同) |
| 并发 build 损坏索引 | MVP 不支持并发 build;CLI 工具拿 flock 锁 `.rag/<plan_id>/.lock` |

---

## 实施步骤

按 TDD + 可 review 提交单位:

1. **chunking 纯函数** + 测试(不依赖外部库,独立可跑)
2. **TalkPointRAG 核心**(embedder + collection 注入式,测试用 mock)
3. **CLI build/query/info/clear**(端到端手工验证)
4. **DirectorAgent 集成**(rag 参数 + prompt 渲染 + 降级路径)
5. **SessionManager 装配**(load_rag_for_plan + on_rag_miss callback)
6. **集成测试**(真模型,mark slow)
7. **dependency lockfile 更新** + README 补说明

---

## 后置工作(不在本 spec 范围)

- Rerank 层:检索 top-20 → LLM reader 精排到 top-5(参考 MemPalace hybrid v4)
- Hybrid search:向量 + BM25(jieba 分词)
- 句级索引:将段级 chunk 进一步拆到 30-80 字短句
- 前端 UI:方案编辑器里直接上传/编辑话术文件
- 话术库跨 plan 共享(产品相同,不同直播复用)
- ONNX 切换省 torch 体积
- 异步预热 embedding:segment 切换时后台算
