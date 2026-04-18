# SessionMemory 设计 — 直播场内分层记忆

## 背景

当前 `DirectorAgent` 只维护 `last_said: str` 一条历史(director_agent.py:130)。
2 小时直播 ~1800 句场景下,会出现:

- **短期重复**:几句之内反复讲同一卖点
- **中期漏说**:必说 cue 没全部覆盖,或重复说
- **长期重复**:开场讲过的卖点 90 分钟后又讲一遍
- **重复答疑**:同一类问题被反复回答

DirectorAgent 0.5s tick + 句间无空隙的硬约束下,记忆查询必须 <5ms,
所以排除任何外部服务(Mem0/Zep/MemPalace),做进程内分层记忆。

## 目标

- 解决上述四类不连贯问题
- 单场 2h 内运行稳定,token 增量可控(<+150% input, 启用 prompt cache 后 <+50%)
- 与现有 `OrderedItemStore`/`EventBus` 风格一致,放在 `src/live/`
- 不引入外部依赖

## 非目标

- 跨场记忆(下一场知道上一场说过什么):后置
- 语义级去重(相似话术识别):后置,先用 topic_tag
- 弹幕 embedding 检索:后置(qa_log v1 用规则)

---

## 数据结构

### `SessionMemory`(主类)

文件:`src/live/session_memory.py`

```python
from collections import deque
from dataclasses import dataclass, field
from threading import RLock
import time

@dataclass
class TopicEntry:
    """LLM 自报的话题标签 + 时间戳。"""
    tag: str            # e.g. "成分:益生菌" / "FAQ:怎么吃" / "价格优势"
    ts: float           # monotonic seconds since session start
    utterance_id: str   # 关联的 TtsItem.id


@dataclass
class QAEntry:
    """已回答过的问题 → 答案摘要。"""
    question_fingerprint: str   # 规则生成的指纹(关键词 sorted join)
    question_raw: str           # 原始问题文本(用于 prompt 展示)
    ts: float
    answer: str                 # AI 当时的回答(<=30字)


class SessionMemory:
    """场内分层记忆。线程安全。

    四层:
        recent:    最近 N 句原文,防短期复读
        cue:       per-segment cue 命中标记,防漏防重
        topics:    全场 topic 时间线,防长期重复卖点
        qa:        已答问题列表,防重复答疑
    """

    def __init__(
        self,
        recent_window: int = 20,
        topic_lookback_seconds: float = 1800.0,   # 30 分钟内 topic 算"近期"
        qa_lookback_seconds: float = 600.0,       # 10 分钟内 QA 算"刚答过"
        qa_max_entries: int = 50,                 # qa_log 容量上限,FIFO
    ) -> None:
        self._recent: deque[str] = deque(maxlen=recent_window)
        self._cue: dict[str, set[str]] = {}       # segment_id → set[cue_text]
        self._topics: list[TopicEntry] = []
        self._qa: deque[QAEntry] = deque(maxlen=qa_max_entries)
        self._start_ts: float = time.monotonic()
        self._topic_lookback = topic_lookback_seconds
        self._qa_lookback = qa_lookback_seconds
        self._lock = RLock()

    # ---- write APIs ----

    def record_utterance(
        self,
        text: str,
        topic_tag: str | None,
        utterance_id: str,
        segment_id: str | None,
        cue_hits: list[str] | None = None,
    ) -> None:
        """每次 director 输出一句后调用。"""
        with self._lock:
            self._recent.append(text)
            if topic_tag:
                self._topics.append(TopicEntry(
                    tag=topic_tag,
                    ts=time.monotonic() - self._start_ts,
                    utterance_id=utterance_id,
                ))
            if segment_id and cue_hits:
                self._cue.setdefault(segment_id, set()).update(cue_hits)

    def record_qa(self, question: str, answer: str) -> None:
        """记录一次答疑。"""
        with self._lock:
            self._qa.append(QAEntry(
                question_fingerprint=_fingerprint(question),
                question_raw=question,
                ts=time.monotonic() - self._start_ts,
                answer=answer,
            ))

    # ---- read APIs(供 build_director_prompt 使用) ----

    def render_recent(self) -> str:
        """最近 N 句原文,渲染为 prompt 段。"""
        with self._lock:
            if not self._recent:
                return "(还没说过话)"
            return "\n".join(f"  - {t}" for t in self._recent)

    def render_topic_summary(self, now_ts: float | None = None) -> str:
        """全场 topic 摘要,带时间和重复次数。"""
        with self._lock:
            if not self._topics:
                return "(暂无)"
            now = now_ts or (time.monotonic() - self._start_ts)
            counts: dict[str, list[float]] = {}
            for entry in self._topics:
                counts.setdefault(entry.tag, []).append(entry.ts)

            lines = []
            for tag, ts_list in counts.items():
                last_ts = ts_list[-1]
                age = now - last_ts
                marker = "[近期]" if age < self._topic_lookback else "[较久]"
                lines.append(
                    f"  - {tag} {marker} 已讲 {len(ts_list)} 次,"
                    f"最近 {_fmt_age(age)} 前"
                )
            return "\n".join(lines)

    def render_cue_status(self, segment_id: str, all_cues: list[str]) -> str:
        """当前段落的 cue 命中清单。"""
        with self._lock:
            covered = self._cue.get(segment_id, set())
            if not all_cues:
                return ""
            lines = [
                f"  - {cue} {'✓ 已说' if cue in covered else '✗ 未说'}"
                for cue in all_cues
            ]
            return "\n".join(lines)

    def render_recent_qa(self, now_ts: float | None = None) -> str:
        """最近 N 分钟内的问答,防重复答疑。"""
        with self._lock:
            now = now_ts or (time.monotonic() - self._start_ts)
            recent = [q for q in self._qa if (now - q.ts) < self._qa_lookback]
            if not recent:
                return "(暂无)"
            return "\n".join(
                f"  - Q: {q.question_raw} → A: {q.answer} ({_fmt_age(now - q.ts)} 前)"
                for q in recent[-10:]   # 最多展示 10 条
            )

    def is_question_answered(self, question: str) -> QAEntry | None:
        """判断同类问题是否在 lookback 窗口内被答过。"""
        fp = _fingerprint(question)
        with self._lock:
            now = time.monotonic() - self._start_ts
            for entry in reversed(self._qa):
                if entry.question_fingerprint == fp and (now - entry.ts) < self._qa_lookback:
                    return entry
            return None


def _fingerprint(text: str) -> str:
    """规则指纹:取关键词集合排序后 join。简单粗暴,够 v1 用。"""
    import re
    tokens = re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]+", text.lower())
    # 去停用词(简化版)
    stopwords = {"的", "了", "吗", "呢", "啊", "是", "我", "你"}
    keywords = sorted(set(tokens) - stopwords)
    return "|".join(keywords)


def _fmt_age(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}秒"
    if seconds < 3600:
        return f"{int(seconds / 60)}分"
    return f"{seconds / 3600:.1f}时"
```

---

## 与 DirectorAgent 集成

### prompt 改动

`build_director_prompt` 增加四个段:

```
=== 最近说过(防复读) ===
  - 这款益生菌是新西兰原装进口的
  - 价格只要 99,买二送一
  - 我家闺女天天喝
  ...(最近 20 句)

=== 全场已讲话题(避免重复) ===
  - 成分:益生菌 [近期] 已讲 3 次,最近 2分 前
  - 价格优势 [较久] 已讲 1 次,最近 25分 前
  - FAQ:怎么吃 [近期] 已讲 2 次,最近 4分 前

=== 当前段落锚点话术(必须覆盖) ===
  - 新西兰原装进口 ✓ 已说
  - 6 个月以上宝宝可吃 ✗ 未说
  - 限时买二送一 ✗ 未说

=== 最近 10 分钟问答(避免重复回答) ===
  - Q: 这个怎么吃 → A: 每天饭后温水冲一包 (3分 前)
  - Q: 多大可以吃 → A: 6 个月以上就可以 (5分 前)
```

### LLM 输出新增字段

```json
{
  "content": "下一句台词(≤30字)",
  "speech_prompt": "朗读风格描述",
  "source": "script | interaction | knowledge",
  "topic_tag": "成分:益生菌",          // 新增,LLM 自报话题标签
  "cue_hits": ["新西兰原装进口"],       // 新增,本句覆盖了哪些 cue
  "is_qa_answer": false,               // 新增,是否在回答某个问题
  "answered_question": null,           // 新增,如果是回答,原始问题
  "reason": "..."
}
```

### system prompt 改动

追加规则:

```
- 优先讲未覆盖的锚点话术(标记 ✗ 的)
- 避免在 5 分钟内重复同一 topic_tag
- 如果"最近问答"里有相似问题,不要重复回答,可以引申到下一卖点
- topic_tag 用"类别:具体内容"格式,如"成分:益生菌"、"FAQ:怎么吃"
- cue_hits 列出本句实际覆盖的锚点话术原文(必须是 cue 列表中的字符串)
```

### DirectorAgent._fire 改动

```python
def _fire(self, script_state, recent_events):
    ...
    prompt = build_director_prompt(
        script_state=script_state,
        knowledge_ctx=self._knowledge_ctx,
        recent_events=all_events,
        memory=self._memory,        # 新增
        persona_ctx=self._persona_ctx,
    )
    raw = self._llm_generate(prompt)
    output = parse_director_response(raw)
    ...
    if output.content:
        self._tts_player.put(output.content, output.speech_prompt, urgent=...)
        # 写入 memory
        self._memory.record_utterance(
            text=output.content,
            topic_tag=output.topic_tag,
            utterance_id=tts_item_id,    # 需要 tts_player.put 返回 id
            segment_id=script_state.get("segment_id"),
            cue_hits=output.cue_hits,
        )
        if output.is_qa_answer and output.answered_question:
            self._memory.record_qa(output.answered_question, output.content)
```

`last_said` 字段废弃,改由 `memory.render_recent()` 提供。

---

## 长直播的 token 预算

### 增长曲线(2h)

| 段 | 大小特性 | 2h 末期 tokens |
|---|---|---|
| recent_utterances | 固定 maxlen=20 → 600 字 | ~900 |
| cue_status | 当前 segment 的 cue 数(<10) | ~150 |
| topic_summary | **线性增长**,假设 80 个独立 topic | ~2400 |
| recent_qa | 滚动 10 分钟窗口,~10 条 | ~600 |
| **新增合计** | | **~4050** |

加上原有 ~2000 → 单次 prompt **~6000 tokens**(2h 末期峰值)。

### prompt cache 优化

固定不变的部分(可缓存):

- system_prompt(~300)
- persona_ctx(~150)
- knowledge_ctx(~750)

合计 ~1200 tokens 走 cache(1/4 价)。

变化部分每次新算:~4800 tokens。

### 成本估算(Gemini 2.5 Flash, 2026 价)

| 阶段 | 单次 input | 单场 (按 2500 次 call) | 价格 |
|---|---|---|---|
| 当前 V0 | 2000 | 5M | $1.50 |
| V2 不开 cache | 6000 | 15M | $4.50 |
| **V2 开 cache** | 1200×0.25 + 4800 = 5100 | 12.75M | **$3.83** |

实际成本接受(单场 < $5)。

### 长场退化策略(>4h 才启用)

`topics` 列表线性增长会爆。两条防线:

1. **滚动摘要**:每 30 分钟,在后台线程让 LLM 把 30 分钟前的 topic 列表压缩成一句话,
   原始 entries 删除。**先不实现,2h 内不需要**。
2. **硬截断**:topic_lookback_seconds 之外的 entry 在 render 时不展示原始时间,
   只显示"已讲过 N 次"。

---

## 线程安全

- 所有数据结构由 `RLock` 保护
- DirectorAgent 多路并发(MAX_CONCURRENT_LLM=2)同时读 memory → 用 RLock 允许重入
- write 路径(`record_utterance` / `record_qa`)只在主 fire 线程末尾调用,无并发写

---

## SessionManager 装配

`session.py` 在 `_build_and_start` 中:

```python
from src.live.session_memory import SessionMemory

memory = SessionMemory(
    recent_window=20,
    topic_lookback_seconds=1800,
    qa_lookback_seconds=600,
    qa_max_entries=50,
)
self._memory = memory

director = DirectorAgent(
    tts_queue=tts_queue,
    tts_player=tts_player,
    knowledge_ctx=knowledge_ctx,
    persona_ctx=persona_ctx,
    llm_generate_fn=llm_client.generate,
    urgent_queue=urgent_queue,
    memory=memory,                   # 新增
)
```

session stop 时:

```python
self._memory = None   # 散场即弃,不持久化
```

---

## 测试

### `session_memory_test.py`

```python
def test_recent_utterances_window():
    m = SessionMemory(recent_window=3)
    for s in ["a", "b", "c", "d"]:
        m.record_utterance(text=s, topic_tag=None, utterance_id="x",
                          segment_id=None, cue_hits=None)
    assert "d" in m.render_recent()
    assert "a" not in m.render_recent()


def test_topic_summary_counts_repeats():
    m = SessionMemory()
    for _ in range(3):
        m.record_utterance(text="x", topic_tag="成分:益生菌",
                          utterance_id="x", segment_id="s1", cue_hits=None)
    out = m.render_topic_summary()
    assert "成分:益生菌" in out
    assert "已讲 3 次" in out


def test_cue_status_per_segment():
    m = SessionMemory()
    m.record_utterance(text="x", topic_tag=None, utterance_id="x",
                      segment_id="s1", cue_hits=["新西兰原装"])
    out = m.render_cue_status("s1", ["新西兰原装", "买二送一"])
    assert "新西兰原装 ✓ 已说" in out
    assert "买二送一 ✗ 未说" in out


def test_qa_lookback_window(monkeypatch):
    m = SessionMemory(qa_lookback_seconds=60)
    m.record_qa("怎么吃", "饭后温水冲服")
    # 模拟 70 秒后
    monkeypatch.setattr("time.monotonic", lambda: m._start_ts + 70)
    assert m.is_question_answered("怎么吃") is None


def test_question_fingerprint_matches_paraphrase():
    assert _fingerprint("这个怎么吃") == _fingerprint("怎么吃啊")
    assert _fingerprint("多大可以吃") != _fingerprint("怎么吃")


def test_thread_safety_concurrent_writes():
    import threading
    m = SessionMemory(recent_window=100)
    def worker(i):
        for j in range(50):
            m.record_utterance(text=f"u{i}-{j}", topic_tag=f"t{i}",
                              utterance_id=f"id-{i}-{j}", segment_id="s1",
                              cue_hits=None)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    # 200 次写入,deque maxlen=100,应保留最后 100 条
    assert len(m._recent) == 100
```

### director_agent 集成测试

`director_agent_memory_test.py`:

- mock LLM 返回带 topic_tag/cue_hits 的 JSON
- 跑 5 次 fire,断言 memory.render_recent() 包含 5 条
- 第 2 次让 LLM 返回 `is_qa_answer=true`,断言 record_qa 被调用

---

## 实施步骤(TDD)

按顺序提交,每步独立可 review:

1. `session_memory.py` + 单测(纯数据结构,无依赖)
2. `schema.py` 的 `DirectorOutput` 增加 4 个字段(topic_tag / cue_hits / is_qa_answer / answered_question)
3. `director_agent.py`:
   - `build_director_prompt` 增加 memory 段
   - `parse_director_response` 解析新字段
   - `_fire` 调用 memory.record_*
   - 删除 `_last_said`
4. `session.py` 装配 memory
5. system prompt 文本更新

每步跑测试 + manual smoke test(mock 模式跑 30 秒看日志)。

---

## 影响面

| 文件 | 改动 | 行数 |
|---|---|---|
| `src/live/session_memory.py` | 新建 | ~150 |
| `src/live/session_memory_test.py` | 新建 | ~120 |
| `src/live/schema.py` | DirectorOutput +4 字段 | +5 |
| `src/live/director_agent.py` | prompt + parse + _fire 改造 | ~80 |
| `src/live/director_agent_*_test.py` | 适配 + 新增集成测试 | ~80 |
| `src/live/session.py` | 装配 memory | ~10 |

预计总改动 ~450 行(其中测试 ~200 行)。

---

## 风险

| 风险 | 对策 |
|---|---|
| LLM 不按 schema 返回 topic_tag | parse 兜底 None,memory 跳过该字段;不影响主链路 |
| topic_tag 命名漂移("成分" vs "成分:益生菌") | system prompt 强约束格式 + few-shot 示例 |
| cue_hits 返回不在 cue 列表中的字符串 | 写入 memory 前用 set 过滤 |
| 高并发 fire 抢 memory 锁 | RLock 重入,且 render 都是只读快照,争用很小 |
| 2h 末期 topic_summary 过长 | render 时按"近期 + 计数"压缩,详见 token 预算 |

---

## 后置工作

- 滚动摘要(>4h 长场景启用)
- QA 指纹升级到 embedding(本地 bge-small-zh,~30ms)
- 跨场记忆(独立项目,接 ChromaDB)
- 前端展示 memory 状态(plans 页面看"已讲话题分布")
