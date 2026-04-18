# Host Style Profile Extraction

You receive the host's (主播) transcript lines only. Produce a JSON profile with:

- `top_phrases`: top 20 most frequent 2-4 char phrases (excluding trivial function words), each `{phrase, count}`
- `catchphrases`: 5-10 口头禅 (signature filler/hooks the host repeats)
- `opening_hooks`: 3-5 representative opening lines (direct quotes)
- `cta_patterns`: 3-10 representative CTA lines (direct quotes)
- `transition_patterns`: 3-8 transitional phrases (e.g. "接下来…", "说到这里…")
- `tone_tags`: 3-6 tags from {热情, 煽动, 亲和, 专业, 冷静, 紧迫, 幽默, 朴实}

Output a pure JSON object matching the schema. Use Simplified Chinese.
