# Host Style Profile Extraction

You receive the transcript lines of the **host (主播) only** from a Chinese live-streaming e-commerce video. Extract a style profile as a pure JSON object.

## Fields

**`top_phrases`** — top 20 semantically meaningful phrases the host uses most, each `{phrase, count}`.
- Include: product descriptors, opinion phrases, rhetorical questions, emotional expressions
- Exclude: pure function words (的/了/吗/啊/就), trivial fillers, overlapping n-gram fragments
- Each phrase should stand alone as meaningful (e.g. "先苦后甜" not "老师做农")

**`catchphrases`** — 5-10 signature verbal tics or filler hooks the host repeats across the stream (not CTAs). E.g. "对吧？", "你说呢？", "我懂你们。"

**`opening_hooks`** — 3-5 lines the host uses to **open a new product or topic** (not mid-sentence transitions). Must be direct quotes that could grab attention if used standalone.

**`cta_patterns`** — 3-10 distinct CTA templates urging viewers to buy/act. Consolidate near-duplicates into one representative form (e.g. "想要的朋友自己去拍" covers all "想X的朋友自己去拍" variants).

**`transition_patterns`** — 3-8 phrases the host uses to switch topics or products. E.g. "来，下一个产品", "说到这里…"

**`tone_tags`** — 3-6 tags from: {热情, 煽动, 亲和, 专业, 冷静, 紧迫, 幽默, 朴实, 感性, 知识型}

Output a pure JSON object. Use Simplified Chinese.
