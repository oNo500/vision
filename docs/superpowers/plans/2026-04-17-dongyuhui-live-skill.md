# dongyuhui-live Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained Claude Code skill (`~/.claude/skills/dongyuhui-live/`) that serves as a three-in-one live-streaming script assistant (generator / retriever / reviewer) for tonic-health/food products in a grounded Dong Yuhui style.

**Architecture:** Pure Markdown skill — SKILL.md routes user intent to GENERATE / SEARCH / REVIEW branches. Reference files provide style patterns, phrase library, scene templates, review rubrics, category knowledge, and compliance defaults. A Python script handles corpus ingestion (text cleanup + optional URL download). No runtime dependencies beyond Claude reading Markdown.

**Tech Stack:** Markdown (skill content), Python 3 + PyYAML (ingest script), pytest (tests)

---

## File Map

**Skill entry — create:**
- `~/.claude/skills/dongyuhui-live/SKILL.md` — skill entry point with intent routing, generate/search/review contracts, degradation rules

**References — create:**
- `~/.claude/skills/dongyuhui-live/references/style-principles.md` — style core + red lines
- `~/.claude/skills/dongyuhui-live/references/phrase-library.md` — ~80 seed phrases across 9 unit types
- `~/.claude/skills/dongyuhui-live/references/review-checklist.md` — 7+1 review dimensions with scoring rubric
- `~/.claude/skills/dongyuhui-live/references/scene-templates.md` — 9 scene definitions + 2h skeleton
- `~/.claude/skills/dongyuhui-live/references/category-knowledge.md` — tonic-health domain knowledge

**Products — create:**
- `~/.claude/skills/dongyuhui-live/products/README.md` — product profile spec
- `~/.claude/skills/dongyuhui-live/products/_defaults/compliance-tonic-health.md` — ad-law / food-safety compliance defaults

**Corpus — create:**
- `~/.claude/skills/dongyuhui-live/corpus/README.md` — frontmatter ingestion spec
- `~/.claude/skills/dongyuhui-live/corpus/index.md` — empty index (maintained by script)

**Scripts — create:**
- `~/.claude/skills/dongyuhui-live/scripts/ingest_corpus.py` — corpus ingestion (Path A: text, Path B: URL)
- `~/.claude/skills/dongyuhui-live/scripts/ingest_corpus_test.py` — TDD tests

---

## Task 1: Directory scaffold + SKILL.md

**Files:**
- Create: `~/.claude/skills/dongyuhui-live/SKILL.md`
- Create: `~/.claude/skills/dongyuhui-live/corpus/index.md`

### Context

SKILL.md is the only file Claude reads when the skill is invoked. It must contain: frontmatter (name + description + trigger phrases), intent routing table, full generate/search/review contracts, degradation rules, and explicit "do not" list. This is the most critical file — everything else is referenced from it.

`corpus/index.md` starts empty — the ingest script maintains it.

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p ~/.claude/skills/dongyuhui-live/{references,products/_defaults,corpus/seed,corpus/ingested,scripts}
```

- [ ] **Step 2: Create SKILL.md**

```markdown
---
name: dongyuhui-live
description: >-
  Use for writing or reviewing Chinese 2h live-streaming sales scripts
  in grounded "Dong Yuhui" style, for tonic-health/food products.
  Triggers on: 写直播稿, 帮我审一下, 有没有……的 Hook, 来一段……故事,
  review live script, 董宇辉风格, 直播脚本, 直播文案, 口播稿.
---

# dongyuhui-live

Tonic-health/food category. Grounded Dong Yuhui style. Three-in-one live-streaming script assistant.

## Capabilities

1. **GENERATE** — produce scene-level script snippets (phrase-unit granularity)
2. **SEARCH** — query the phrase library / corpus by type, product, scene, tags
3. **REVIEW** — critique user-written scripts across 7+1 dimensions

## Prerequisites

- Before generating for a specific product, check `products/<slug>/profile.md` exists.
  If missing, tell the user and operate in **no-profile degradation mode** (use only
  `references/category-knowledge.md` — do not invent origin, batch, or price details).
- ALL output must pass compliance filtering against `claims_forbidden` + `forbidden_words`
  from the product profile AND `products/_defaults/compliance-tonic-health.md`.

## Intent Routing

| User signal | Route | Required input |
|---|---|---|
| "帮我审一下 / 看看这段 / 挑毛病 / review" + pasted text | **REVIEW** | text (required); scene, product (optional) |
| "写一段 / 来一段 / 生成 …… 的 Hook / 故事 / 段落" | **GENERATE** | scene + product (required); duration, emotion (optional) |
| "有没有 / 查一下 / 找一句 …… 的比喻 / 金句 / Hook" | **SEARCH** | phrase type or keyword (required) |
| Ambiguous ("帮我写直播稿") | **Clarify once** | Ask: "A) review existing text B) generate new snippet C) search phrase library" |

**Priority when multiple intents match:** REVIEW > SEARCH > GENERATE.
**Clarification budget:** ask at most ONE clarifying question, then proceed.

### Session context

Remember the product / scene / emotion from the first mention in this conversation.
Carry forward unless the user explicitly changes it. Never re-ask for info already given.

---

## Branch 1: GENERATE

Read these files in order before generating:

1. `references/style-principles.md` — style guardrails
2. `products/<slug>/profile.md` — product facts + compliance bounds
   (fallback: `references/category-knowledge.md` if no profile)
3. `corpus/index.md` — scan for 2-3 same-scene/type anchor snippets
   (fallback: `references/phrase-library.md` if corpus is empty)
4. `references/scene-templates.md` — scene structure for the requested scene

### Scene IDs (9 types)

`opening` | `product_story` | `product_detail` | `metaphor_moment` | `qa_live` | `soft_push` | `hard_push` | `transition` | `closing`

### Phrase unit types (9 types)

`HOOK` | `METAPHOR` | `STORY` | `KNOWLEDGE` | `TRANSITION` | `SELF_TALK` | `GOLDEN` | `SOFT_CTA` | `HARD_CTA`

### Output format

Return Markdown. Prefix each phrase unit with an HTML comment tag:

```markdown
<!-- HOOK -->
Content here...

<!-- STORY -->
Content here...

<!-- METAPHOR -->
Content here...

<!-- GOLDEN -->
Content here...
```

### Compliance gate

Before returning, scan ALL output against:
- `forbidden_words` from product profile
- `claims_forbidden` from product profile
- `products/_defaults/compliance-tonic-health.md` universal list

If any hit: rewrite the offending phrase and append a note at the end:
`> [!WARNING] Compliance: rewrote "X" to avoid forbidden term "Y".`

### Save to disk

- Default: do NOT save. Return inline.
- If user says "save / keep / store": write to `{cwd}/output/live/scripts/YYYY-MM-DD-<product>-<scene>.md`
  if cwd contains `code/vision`, else `./YYYY-MM-DD-<product>-<scene>.md` (confirm path with user).

---

## Branch 2: SEARCH

1. Read `corpus/index.md` — one-line-per-entry summary index
2. Filter by user criteria (segment_type, product, scene, tags — any combination)
3. For matches: open the full corpus file and return content with source attribution
4. Also search `references/phrase-library.md` for matching phrase units
5. If zero matches: say so honestly, then ask "Want me to generate one instead?"

### Return format

```markdown
## Match 1 (source: phrase-library.md | HOOK | tag: imagery)
"Content..."

## Match 2 (source: corpus/seed/20240915-01.md | HOOK | tag: imagery)
"Content..."
```

Return 3-5 candidates. Always include source attribution.

---

## Branch 3: REVIEW

Read `references/review-checklist.md` for the full rubric, then evaluate the user's text.

### Dimensions (7 + 1)

| # | Dimension | Scale | What to check |
|---|---|---|---|
| 1 | Literary quality | 1-5 | Metaphor density, imagery, beyond info-dumping |
| 2 | Storytelling | 1-5 | People/places/events woven in; specificity |
| 3 | Groundedness | 1-5 | No obscure classical Chinese; natural for a newcomer host |
| 4 | Rhythm | 1-5 | Long/short sentence alternation; breath points |
| 5 | CTA integration | 1-5 | Sales nudge feels natural vs forced |
| 6 | Quotability | 1-5 | 1-2 screenshot-worthy golden lines present |
| 7 | Jarring words | pass/warn | Flag non-DYH expressions (internet slang, health-product cliches) |
| + | Compliance | pass/warn | Hits on `claims_forbidden` / `forbidden_words` |

### Output template (use exactly this structure)

```markdown
## Review Report

**Overall:** <one-sentence verdict>

**Scores**
- Literary: N/5 — <brief note>
- Storytelling: N/5 — <brief note>
- Groundedness: N/5 — <brief note>
- Rhythm: N/5 — <brief note>
- CTA integration: N/5 — <brief note>
- Quotability: N/5 — <brief note>
- Jarring words: pass | warn: <list specific words>
- Compliance: pass | warn: <list forbidden terms hit>

**Top 3 Suggestions**
1. [location in text] -> [what to change] -> [replacement sentence]
2. ...
3. ...

**Rewrite Demo** (1-2 examples)
Original: "..." -> Rewritten: "..."
```

### Learning loop

- Only give Top 3 + 1-2 demos. Do NOT rewrite the entire script.
- If the same dimension scores low 3+ times in a conversation, point the user to the
  relevant section in `references/style-principles.md` or `references/phrase-library.md`.

---

## Degradation

- **No product profile:** use `references/category-knowledge.md` only; do not fabricate origin/batch/price
- **Empty corpus:** fall back to `references/phrase-library.md` for all anchor/search needs
- **Same dimension low 3+ times:** proactively link to the matching `references/` section

## Do NOT

- Generate a full 2h script in one go
- Make creative decisions for the user (review suggests, user decides)
- Auto-install yt-dlp / whisper (print install instructions if missing)
- Distribute this skill or its corpus externally
```

- [ ] **Step 3: Create empty corpus/index.md**

```markdown
<!-- Corpus index — maintained by scripts/ingest_corpus.py. Do not edit manually. -->
```

- [ ] **Step 4: Commit**

```bash
cd ~/.claude/skills/dongyuhui-live
git init
git add SKILL.md corpus/index.md
git commit -m "feat: scaffold dongyuhui-live skill with SKILL.md entry point"
```

---

## Task 2: Style principles + red lines

**Files:**
- Create: `~/.claude/skills/dongyuhui-live/references/style-principles.md`

### Context

This is the style DNA of the skill. It defines what "grounded Dong Yuhui style" means for a newcomer host selling tonic-health products. Claude reads this before every GENERATE call. It must be specific enough to produce consistent output — not vague platitudes.

- [ ] **Step 1: Create style-principles.md**

```markdown
# Style Principles — Grounded Dong Yuhui

This document defines the style core for all generated content. Read it before every
GENERATE call. It is the single source of truth for "what this style sounds like."

## Core Identity

A newcomer host selling tonic-health / food products. Sincere, warm, slightly
self-deprecating. Uses literary metaphor and storytelling to make products feel like
life companions, not commodities. Never sounds like a traditional sales host.

## The Four Pillars

### 1. Literary Metaphor (wenxue bi yu)

Turn product attributes into sensory images from daily life and nature.

**Do:**
- Map taste/texture to weather, seasons, landscapes: "This porridge is like the first
  warm morning after spring rain — it doesn't hit you, it holds you."
- Use concrete objects: kitchens, old wooden tables, grandmother's hands, morning markets
- Keep metaphors within 1-2 sentences; don't extend into full allegories

**Don't:**
- Abstract philosophical metaphors ("life is like a river...")
- Metaphors that require cultural footnotes

**Examples:**
- "This black sesame paste, when you stir it, the aroma is like opening an old wooden
  drawer you haven't touched in years — everything inside is still warm."
- "Astragalus root tea in winter is like putting on a padded jacket from the inside out."

### 2. Human Narrative (renwen xushi)

Every product has people, places, and processes behind it. Tell those stories.

**Do:**
- Name specific places (Wen County, Dong'e, Ning Xia Zhongning)
- Mention real roles: the farmer, the picker, the old master who roasts it
- Describe one vivid detail (the soil color, the drying racks, the sunrise timing)
- Keep stories to 3-5 sentences — a snapshot, not a documentary

**Don't:**
- Fabricate people or places not in the product profile
- Over-dramatize ("tears streaming down the farmer's weathered face...")
- Turn every product into a poverty narrative

**Examples:**
- "The goji berries from Zhongning — the pickers go out at 5am because the morning
  dew makes the skins tightest. By noon the sun softens them and they burst in transit."

### 3. Knowledge Seeding (zhishi zhongcao)

Share one small, genuine piece of knowledge before or alongside the product pitch.

**Do:**
- Traditional food therapy concepts (shi liao): seasonal eating, warming/cooling foods
- 24 solar terms and their food associations
- Simple nutritional facts (mucin protein in yam, collagen in donkey-hide gelatin)
- Common idioms / proverbs about food and health
- Keep it to 1-2 sentences of knowledge, then bridge to product

**Don't:**
- Cite obscure classical texts (Shang Shu, Dao De Jing, Huang Di Nei Jing)
- Make medical claims (see compliance)
- Lecture — the knowledge should feel like a casual aside

**Examples:**
- "Old folks say 'autumn dryness hurts the lungs' (qiu zao shang fei) — that's why
  this season everyone reaches for pear soup or tremella. This product does the same job,
  just in a packet you can take to the office."

### 4. Sincere Anti-Routine (zhencheng fan taolu)

Break the standard live-commerce script patterns. Be human.

**Do:**
- Acknowledge being a newcomer: "I'm still learning this — bear with me"
- Pause and think visibly: "Let me find the right words for this..."
- Admit product limits: "This won't replace a meal, but as a daily supplement..."
- Use humor about the live-streaming format: "I know I'm supposed to yell 3-2-1 right
  now, but I'd rather just tell you why I actually like this"

**Don't:**
- Overdo self-deprecation to the point of seeming incompetent
- Use it as a sales tactic ("I'm just a small host, so my price MUST be the lowest")
- Be anti-routine about EVERYTHING — some standard phrases are fine for pacing

## Red Lines

### Forbidden: Deep Classical Chinese

- NO: quotes from Shang Shu, Dao De Jing, Zhuang Zi, Shi Jing (unless extremely
  well-known single lines like "天行健" level)
- NO: wenyanwen sentence structures in the script
- YES: common Tang/Song poetry lines everyone learned in school (Li Bai, Du Fu, Su Shi — 
  famous lines only)
- YES: chengyu (four-character idioms) that are genuinely colloquial
- YES: folk sayings, agricultural proverbs, seasonal wisdom

### Forbidden: Over-sentimentality

- NO: tear-jerking narratives designed to guilt-purchase
- NO: "If you don't buy this, you don't love your parents" type framing
- YES: genuine warmth, nostalgia, family connection (without weaponizing it)

### Forbidden: Aggressive Sales Language

- NO: "3-2-1 shang lianjie!", "kuai qiang!", "cuoguole jiu meile!"
- NO: artificial scarcity that sounds fake
- YES: gentle urgency ("we only prepared X sets for today's live")
- YES: explaining the deal clearly without pressure ("the live-room price saves you X")

### The Newcomer Constraint

This host is NEW. The style must feel:
- Slightly uncertain but genuine (not polished-smooth)
- Learning alongside the audience
- More "neighbor sharing a discovery" than "expert lecturing"
- Comfortable with silence and imperfection

## Tone Calibration by Scene

| Scene | Energy | Metaphor density | CTA strength |
|---|---|---|---|
| opening | Warm, relaxed | Low | None |
| product_story | Immersive, slow | High | None |
| product_detail | Informative, grounded | Medium | Low |
| metaphor_moment | Poetic, contemplative | Very high | None |
| qa_live | Conversational, responsive | Low | Low |
| soft_push | Warm + nudging | Medium | Medium |
| hard_push | Clear, direct, still warm | Low | High |
| transition | Light, bridging | Low | None |
| closing | Reflective, grateful | Medium | None |
```

- [ ] **Step 2: Commit**

```bash
cd ~/.claude/skills/dongyuhui-live
git add references/style-principles.md
git commit -m "feat: add style principles with four pillars and red lines"
```

---

## Task 3: Scene templates + 2h skeleton

**Files:**
- Create: `~/.claude/skills/dongyuhui-live/references/scene-templates.md`

### Context

This file defines the 9 scene types and provides a reference 2h skeleton. Claude reads it during GENERATE to understand structure for the requested scene. Each scene template tells Claude what phrase units to include and in what order.

- [ ] **Step 1: Create scene-templates.md**

```markdown
# Scene Templates

9 scene types for a 2h tonic-health live-streaming session. Each template defines the
purpose, typical duration, expected phrase units, and structural notes.

## Scene Definitions

### opening (5-10 min)

**Purpose:** Warm up the room. Establish the host persona. Preview tonight's products.

**Phrase unit sequence:**
1. HOOK — draw viewers in (a seasonal observation, a question, a small image)
2. SELF_TALK — newcomer self-intro, warmth, "glad you're here"
3. KNOWLEDGE — one light seasonal/food fact to set the topic
4. TRANSITION — bridge to first product

**Notes:**
- Energy: relaxed, unhurried
- No selling. No product details yet.
- Mention "tonight we have X" as a preview, not a pitch

---

### product_story (10-15 min)

**Purpose:** The human story behind the product — origin, people, craft, land.

**Phrase unit sequence:**
1. HOOK — an image or question tied to the product's origin
2. STORY — the core narrative (place, people, process). 3-5 sentences.
3. KNOWLEDGE — one food-therapy or seasonal fact that connects
4. METAPHOR — a sensory metaphor for the product experience
5. GOLDEN — one quotable line that captures the story's essence

**Notes:**
- This is Dong Yuhui's strongest territory. Lean into specificity.
- All facts MUST come from `products/<slug>/profile.md`. Do not invent origins.
- If no profile exists, use only generic category knowledge and say so.

---

### product_detail (8-12 min)

**Purpose:** Ingredients, process, usage — the rational case.

**Phrase unit sequence:**
1. KNOWLEDGE — lead with an interesting fact (ingredient, process, nutrition)
2. STORY — brief mention of how it's made (links back to product_story if already done)
3. KNOWLEDGE — usage instructions, best practices, common mistakes
4. SELF_TALK — personal touch ("I've been having this every morning for a week...")
5. SOFT_CTA — first gentle mention of the deal

**Notes:**
- Keep it grounded. This is the informational scene, not the poetic one.
- Reference FAQ from the product profile for common questions.
- Compliance is critical here — never cross into medical claims.

---

### metaphor_moment (2-5 min)

**Purpose:** Pure literary pause. A sensory, poetic snippet about the product or its context.

**Phrase unit sequence:**
1. METAPHOR — the main image (extended, 2-3 sentences)
2. GOLDEN — distill it into one quotable line

**Notes:**
- Short and impactful. This is the "screenshot moment."
- No product specs, no CTA. Just beauty.
- Works best after product_story or product_detail as a palate cleanser.

---

### qa_live (5-10 min)

**Purpose:** Address audience questions from danmaku. Maintain conversational energy.

**Phrase unit sequence:**
1. SELF_TALK — acknowledge the question warmly
2. KNOWLEDGE — answer with substance (pull from product FAQ or category knowledge)
3. METAPHOR — optional: if the answer lends itself to an image
4. SOFT_CTA — optional: if the question naturally leads to "and that's why..."

**Notes:**
- Claude generates TEMPLATE answers. The host adapts in real-time.
- Common questions for tonic-health: "Can pregnant women eat this?", "How to prepare?",
  "What's the difference from brand X?" — reference product FAQ.
- Never guess medical answers. Default: "I'm not a doctor — please consult yours."

---

### soft_push (3-5 min)

**Purpose:** Story-ending into gentle deal introduction. Bridge emotion to action.

**Phrase unit sequence:**
1. GOLDEN — callback to the story or metaphor from earlier
2. SOFT_CTA — introduce the deal: what's included, what's special about the live price
3. SELF_TALK — "I genuinely think this is worth trying" (sincere, not salesy)

**Notes:**
- The transition from story to deal should feel like a natural conclusion, not a gear shift.
- Mention specifics: price, included extras, limited quantity.
- Tone stays warm. This is not a countdown.

---

### hard_push (2-3 min)

**Purpose:** Clear call to action. Link is up. Time to decide.

**Phrase unit sequence:**
1. HARD_CTA — direct: "Link is up, cart item #N, here's what you get for the price"
2. KNOWLEDGE — one last rational reason (value comparison, shelf life, daily cost breakdown)
3. HARD_CTA — repeat with urgency: quantity remaining, deal ending time

**Notes:**
- Even hard_push stays warm for this host. No screaming.
- Newcomer-friendly version: "I'm not great at the pressure thing, so I'll just say —
  if what I described sounds good to you, the link is right there."
- Always state the price clearly. No hidden conditions.

---

### transition (30s-1 min)

**Purpose:** Bridge between two products or two major topics.

**Phrase unit sequence:**
1. TRANSITION — a one-sentence bridge ("Speaking of X, that actually reminds me of...")
2. HOOK — tease the next topic

**Notes:**
- Keep it extremely short. This is a breath, not a scene.
- Can be playful or reflective.

---

### closing (5 min)

**Purpose:** Wrap up. Thank the audience. Golden line. Invite follow.

**Phrase unit sequence:**
1. GOLDEN — the evening's closing thought (reflective, warm)
2. SELF_TALK — genuine thanks, "I'm still learning, thanks for being here"
3. SOFT_CTA — gentle follow invite ("If you enjoyed tonight, hit follow — same time next week")

**Notes:**
- No selling in closing.
- End on a human note, not a transaction.

---

## 2h Skeleton (Reference)

A typical 2-product session. Adjust freely.

```
opening(8 min)
--- Product A ---
product_story(12 min)
product_detail(10 min)
metaphor_moment(3 min)
soft_push(4 min)
qa_live(8 min)
hard_push(3 min)
--- Bridge ---
transition(1 min)
--- Product B ---
product_story(12 min)
product_detail(10 min)
metaphor_moment(3 min)
soft_push(4 min)
qa_live(8 min)
hard_push(3 min)
--- Wrap ---
closing(5 min)
--- Buffer: ~6 min for organic conversation ---
```

Total: ~114 min scripted + ~6 min organic = 2h
```

- [ ] **Step 2: Commit**

```bash
cd ~/.claude/skills/dongyuhui-live
git add references/scene-templates.md
git commit -m "feat: add 9 scene templates with 2h skeleton"
```

---

## Task 4: Review checklist

**Files:**
- Create: `~/.claude/skills/dongyuhui-live/references/review-checklist.md`

### Context

This is the scoring rubric for the REVIEW branch. Claude reads it before evaluating user-submitted scripts. Each dimension needs concrete scoring criteria — not just a label. The output template is in SKILL.md; this file provides the detailed rubric.

- [ ] **Step 1: Create review-checklist.md**

```markdown
# Review Checklist — 7+1 Dimensions

Use this rubric when evaluating user-submitted live-streaming scripts. Score each
dimension independently. The goal is to help the user internalize the style, not to
rewrite their work.

## Scoring Rubric

### 1. Literary Quality (wenxue hua chengdu) — 1 to 5

| Score | Criteria |
|---|---|
| 1 | Pure information listing. No imagery. Reads like a product spec sheet. |
| 2 | One attempted metaphor, but generic ("like a warm hug"). No sensory specificity. |
| 3 | 1-2 concrete metaphors with sensory detail. Some sentences create images. |
| 4 | Multiple metaphors that are specific and varied. The text creates a consistent atmosphere. |
| 5 | Metaphors feel inevitable — not decorative but structural. The product IS the image. |

**What to flag:** Overused metaphors (warm hug, like sunshine, tastes like home).
Generic adjectives (delicious, amazing, wonderful) without sensory grounding.

### 2. Storytelling (gushi xing) — 1 to 5

| Score | Criteria |
|---|---|
| 1 | No people, places, or events. Just product attributes. |
| 2 | Mentions a place name but no detail. "From Shandong" with nothing specific. |
| 3 | Has a place + one detail (soil type, climate, process step). Readable but thin. |
| 4 | Named people or roles (the farmer, the roaster), a specific setting, a vivid moment. |
| 5 | The story has arc (small tension/resolution), emotional specificity, and feels TRUE. |

**What to flag:** Fabricated stories not grounded in product profile. Poverty
exploitation narratives. Stories that go on too long (>5 sentences for a single scene).

### 3. Groundedness (jie di qi chengdu) — 1 to 5

| Score | Criteria |
|---|---|
| 1 | Reads like a literature essay. Uses wenyanwen structures. Obscure classical references. |
| 2 | Mix of bookish and colloquial. Some sentences feel forced or performative. |
| 3 | Mostly natural spoken Chinese. Occasional overly literary phrasing. |
| 4 | Sounds like someone actually talking. Cultural references are common knowledge. |
| 5 | Completely natural. Could be transcribed speech. The newcomer persona is consistent. |

**What to flag:** Direct quotes from Dao De Jing, Shang Shu, Zhuang Zi. Wenyanwen
sentence patterns. Vocabulary a new host would not naturally use. Overly polished
phrasing that breaks the "learning alongside you" persona.

### 4. Rhythm (jiezou gan) — 1 to 5

| Score | Criteria |
|---|---|
| 1 | All sentences are the same length. No variation. Reading it aloud feels monotone. |
| 2 | Some length variation but no deliberate pacing. No breath points. |
| 3 | Mix of long and short sentences. Some natural pause points. |
| 4 | Clear rhythm pattern: build-up with longer sentences, punch with short ones. Good for reading aloud. |
| 5 | Musical quality. Long sentences flow, short ones land. Natural breath points every 15-20 characters. Silence is used intentionally. |

**What to flag:** Three or more consecutive long sentences (>30 chars) without a break.
Run-on structures. No variation between descriptive and punchy lines.

### 5. CTA Integration (cu dan rongru du) — 1 to 5

| Score | Criteria |
|---|---|
| 1 | No CTA at all (in a scene that needs one), or CTA is a jarring "BUY NOW!" |
| 2 | CTA exists but feels pasted on. Tone shifts abruptly from storytelling to selling. |
| 3 | CTA is present and not jarring, but could be more natural. |
| 4 | CTA flows from the preceding content. Feels like a natural conclusion to the story. |
| 5 | You barely notice the CTA because it's woven into the narrative. The story IS the pitch. |

**What to flag:** "3-2-1 shang lianjie!", "jia ren men chong!", "cuoguole jiu meile!",
any countdown-style pressure. Also flag scenes that SHOULD have a CTA but don't
(soft_push, hard_push scenes with zero buying guidance).

### 6. Quotability (jin ju ke jianji du) — 1 to 5

| Score | Criteria |
|---|---|
| 1 | No sentence stands on its own. Everything is context-dependent. |
| 2 | One sentence could maybe be pulled out, but it's not memorable. |
| 3 | One clear golden line that could be screenshot-shared. |
| 4 | 1-2 strong golden lines. At least one is genuinely memorable. |
| 5 | Multiple quotable lines. At least one could go viral as a standalone image. |

**What to flag:** Scripts with zero standalone quotable sentences. Also flag "fake deep"
lines that sound profound but say nothing ("life is a journey of taste").

### 7. Jarring Word Detection (weiheci jiance) — pass / warn

Scan for words and phrases that break the Dong Yuhui style:

**Internet slang to flag:** YYDS, jiue le, ka, 666, lao tie men, bao zi men (in sales
context), di di di (countdown sounds)

**Health-product cliches to flag:** tian hua ban (ceiling), xing jia bi zhi wang, 
quan wang zui di, mai yi song yi (as a yelling pitch), jiankang tou zi

**Generic live-commerce phrases to flag:** "3-2-1 shang lianjie", "ku cun bu duo le
kuai qiang", "jia ren men chong chong chong", "xian dao xian de", "shou man wei kuai"

**Report format:** List each flagged word/phrase with its location in the text.

### +. Compliance Check (heguixing jiancha) — pass / warn

Cross-reference ALL text against:
1. The specific product's `claims_forbidden` and `forbidden_words` (from profile.md)
2. The universal list in `products/_defaults/compliance-tonic-health.md`

**Report format:** List each forbidden term/claim found, its location, and the rule it violates.

---

## Review Output Rules

1. Use the exact template from SKILL.md (Branch 3: REVIEW output template)
2. Give Top 3 suggestions only — ranked by impact on style quality
3. Include 1-2 rewrite demos — show exactly how to fix the worst issues
4. Do NOT rewrite the entire script. The user must learn by revising.
5. If the same dimension scores <= 2 three times in one conversation, add:
   "This dimension keeps scoring low. Review `references/style-principles.md` section
   [specific section name] for guidance."
```

- [ ] **Step 2: Commit**

```bash
cd ~/.claude/skills/dongyuhui-live
git add references/review-checklist.md
git commit -m "feat: add 7+1 review checklist with scoring rubrics"
```

---

## Task 5: Category knowledge (tonic-health domain)

**Files:**
- Create: `~/.claude/skills/dongyuhui-live/references/category-knowledge.md`

### Context

Domain knowledge for tonic-health / food products. This is the factual backbone when no product profile exists, and supplements product profiles with general category context. Covers common ingredients, traditional food therapy, 24 solar terms, and what's safe to claim.

- [ ] **Step 1: Create category-knowledge.md**

```markdown
# Category Knowledge — Tonic Health & Food (zi bu yang sheng)

General domain knowledge for the tonic-health/food category. Use this as background
context for all generation and review. When no specific product profile exists, this is
the ONLY factual source — do not invent specifics.

## Common Tonic-Health Ingredients

### Donkey-Hide Gelatin (e jiao / a jiao)
- Primary source: Dong'e County, Shandong Province (Dong'e well water is key)
- Traditional use: nourish blood (bu xue), moisten dryness (run zao)
- Common forms: pure blocks, ejiao cake (with sesame, walnut, yellow wine), powder
- Key compounds: collagen, amino acids
- Processing: donkey hide simmered for days; quality depends on water source + simmering time
- Season association: autumn/winter consumption tradition

### Goji Berry (gou qi / ning xia gou qi)
- Primary source: Zhongning County, Ningxia (the "goji capital")
- Traditional use: nourish liver and kidney (zi bu gan shen), brighten eyes (ming mu)
- Quality markers: large, red, sweet, few seeds, sinks in water
- Common forms: dried, tea, wine infusion, congee ingredient
- Harvest: summer picking, sun-dried
- Season association: year-round, peaks in autumn

### Iron-Stick Yam (tie gun shan yao)
- Primary source: Wen County, Jiaozuo, Henan (lu tu / heavy clay soil)
- Traditional use: strengthen spleen and stomach (jian pi yang wei)
- Quality markers: short and thick (vs long sandy-soil varieties), high mucin protein
- Common forms: fresh, dried slices, powder
- Key distinction: lu tu yam vs sha tu (sandy soil) yam — mucin protein 3x difference
- Season association: late autumn harvest, winter consumption

### Astragalus Root (huang qi)
- Primary source: Inner Mongolia, Gansu, Shanxi
- Traditional use: boost qi (bu qi), strengthen exterior defense (gu biao)
- Common forms: sliced root (for soups), powder, tea
- Quality markers: thick slices, yellow cross-section, slightly sweet taste
- Season association: autumn/winter tonic soups

### Bird's Nest (yan wo)
- Primary source: Southeast Asia (Indonesia, Malaysia, Thailand)
- Traditional use: nourish yin (zi yin), moisten lungs (run fei), beauty
- Common forms: dried nests (need soaking + stewing), ready-to-eat bottled
- Key compounds: sialic acid, EGF-like factors (claimed, not all proven)
- Quality markers: minimal feather residue, intact strands, natural color
- Season association: year-round

### Tremella / Snow Fungus (yin er / xue er)
- Primary source: Fujian (Gutian county), Sichuan, Yunnan
- Traditional use: moisten lungs (run fei), nourish skin (yang yan)
- Common forms: dried (needs soaking), instant freeze-dried, soup base
- Preparation: slow-cook until gelatinous; pairs with lotus seed, red dates, goji
- Season association: autumn (against autumn dryness / qiu zao)

### Red Dates (hong zao / da zao)
- Primary sources: Xinjiang (Hetian, Ruoqiang), Henan, Shandong
- Traditional use: nourish blood (bu xue), calm spirit (an shen)
- Common forms: dried whole, sliced, paste, in ejiao cakes
- Quality markers: large, thin skin, thick flesh, small pit
- Season association: autumn harvest, year-round use

## The 24 Solar Terms and Food Therapy

Tonic-health products naturally map to seasonal eating traditions:

| Season | Key terms | Food therapy theme | Relevant products |
|---|---|---|---|
| Spring | Li Chun, Yu Shui, Jing Zhe | Liver nourishing (yang gan), light/green foods | Goji tea, chrysanthemum, light soups |
| Summer | Li Xia, Xiao Shu, Da Shu | Clear heat (qing re), strengthen spleen (jian pi) | Mung bean, lotus seed, barley water |
| Autumn | Li Qiu, Bai Lu, Qiu Fen | Moisten lungs (run fei), combat dryness (fang zao) | Tremella, pear, ejiao, honey, yam |
| Winter | Li Dong, Da Xue, Dong Zhi | Warm and tonify (wen bu), store energy (cang jing) | Ejiao cake, astragalus soup, lamb, goji |

**Key principle:** "Eat in season" (shi ling er shi) — always connect products to the
current or upcoming season.

## Traditional Food Therapy Concepts (simplified, for spoken use)

- **Bu qi** (boost vital energy): astragalus, yam, red dates
- **Bu xue** (nourish blood): ejiao, red dates, longan, goji
- **Run fei** (moisten lungs): tremella, pear, lily bulb, honey
- **Jian pi** (strengthen spleen/digestion): yam, lotus seed, gordon euryale
- **Zi yin** (nourish yin fluids): bird's nest, tremella, lily bulb
- **Wen yang** (warm yang energy): ginger, cinnamon, walnut, lamb

**Important:** These are food therapy (shi liao) concepts, not medical diagnoses or
treatments. Always frame as "traditional dietary wisdom" not "cures" or "treats."

## What You Can and Cannot Say

### Safe to say (food/dietary framing):
- "Traditionally used for..." / "Old folks say..."
- "A seasonal choice for autumn dryness"
- "Supports daily wellness as part of a balanced diet"
- "Rich in [nutrient]" (if factually verified)

### Never say (medical/therapeutic framing):
- "Treats / cures / heals [condition]"
- "Lowers blood sugar / blood pressure / cholesterol"
- "Replaces medication"
- "Clinically proven to..."
- "No side effects"
- "Suitable for all people" (always add "consult your doctor" for medical conditions)

See `products/_defaults/compliance-tonic-health.md` for the complete forbidden list.
```

- [ ] **Step 2: Commit**

```bash
cd ~/.claude/skills/dongyuhui-live
git add references/category-knowledge.md
git commit -m "feat: add tonic-health category knowledge reference"
```

---

## Task 6: Phrase library (~80 seed phrases)

**Files:**
- Create: `~/.claude/skills/dongyuhui-live/references/phrase-library.md`

### Context

This is the fallback "ammunition" when the corpus is empty. ~80 phrases across 9 unit types, written as abstract imitations of the Dong Yuhui style adapted for tonic-health. These are NOT copied from Dong Yuhui — they're original phrases written in his style patterns. Claude uses them as style anchors during GENERATE and as search results during SEARCH.

- [ ] **Step 1: Create phrase-library.md**

```markdown
# Phrase Library — Seed Collection

~80 original phrases written in the grounded Dong Yuhui style for tonic-health/food.
These are NOT quotes — they are style-patterned originals for use as generation anchors
and search fallback when the corpus is empty.

Organized by phrase unit type. Each entry tagged with applicable scenes and tags.

---

## HOOK (opening lines that pull listeners in)

### H-01 | scene: opening | tags: [season, imagery]
"Have you noticed that autumn has a specific smell? Not the osmanthus or the chrysanthemum — it's the smell of the first pot of soup simmering after you dig out the clay pot you haven't touched since spring."

### H-02 | scene: product_story | tags: [origin, question]
"If you drive into Wen County in late October, you'll see something odd — the fields look empty, but every family's courtyard is full. Drying racks, everywhere. Do you know what's on them?"

### H-03 | scene: opening | tags: [daily-life, warmth]
"I don't know about you, but in winter my first instinct after waking up isn't to check my phone — it's to hold something warm. A cup, a bowl, anything. That three seconds of warmth in your palms, that's the real alarm clock."

### H-04 | scene: product_story | tags: [season, contrast]
"Everyone talks about spring for new beginnings, but I think autumn is when we actually start taking care of ourselves. Spring is ambition. Autumn is 'okay, let me actually eat properly.'"

### H-05 | scene: opening | tags: [self-talk, newcomer]
"I have to be honest — I'm still figuring out this whole live-streaming thing. But one thing I am sure about is what I eat, and tonight I want to show you something I've been having every morning."

### H-06 | scene: product_detail | tags: [curiosity, knowledge]
"Quick question — do you know why your grandmother always insisted on using clay pots instead of metal ones for soups? It's not superstition. There's actual science to it, and it connects to what we're talking about tonight."

### H-07 | scene: opening | tags: [imagery, food]
"Close your eyes for a second. Imagine a kitchen at 6am — the window's foggy, something's bubbling on the stove, and the smell is so thick you could almost chew it. That's the feeling I want to bring to this live room tonight."

### H-08 | scene: product_story | tags: [people, origin]
"Last month I spoke to a yam farmer in Wen County. He said something that stuck with me: 'The yam doesn't care about you. You have to care about the soil first.' That changed how I think about food."

### H-09 | scene: qa_live | tags: [engagement, warm]
"Someone in the comments just asked something I've been wanting to talk about all evening — hold on, let me find it... yes, THIS one. Great question."

---

## METAPHOR (sensory images for products)

### M-01 | scene: product_story | tags: [texture, warmth] | product: ejiao
"Ejiao cake melts on your tongue like the last sliver of sunlight on a winter windowsill — slow, warm, and gone before you're ready."

### M-02 | scene: metaphor_moment | tags: [imagery, nature] | product: yam-powder
"Yam powder in hot water — watch it bloom. It's like watching morning fog dissolve over a lake. First it's cloudy, then it's smooth, then it's just... still."

### M-03 | scene: product_detail | tags: [taste, comfort] | product: goji
"Good goji berries have this sweetness that doesn't announce itself. It sneaks up on you, like the warmth of a blanket you didn't realize you needed."

### M-04 | scene: metaphor_moment | tags: [imagery, craft] | product: ejiao
"The old ejiao masters say you can tell the quality by the sound when you snap a piece. It should sound like breaking thin ice on a winter morning — clean, sharp, no hesitation."

### M-05 | scene: product_story | tags: [earth, origin] | product: yam
"Lu tu — heavy clay soil. Your shoes stick to it after rain. Farmers complain about it. But that sticky, stubborn soil is exactly why the yam grows so dense. The soil doesn't let go, and the yam doesn't give up."

### M-06 | scene: metaphor_moment | tags: [season, contemplation]
"Winter tonic foods are like savings — you don't feel the benefit today, but come spring, when everyone else is dragging, you'll have something to draw from."

### M-07 | scene: product_detail | tags: [process, care] | product: tremella
"Slow-cooking tremella until it's gelatinous takes 3-4 hours. There's no shortcut. It's the kind of recipe that teaches you something about patience — the good stuff doesn't rush."

### M-08 | scene: metaphor_moment | tags: [imagery, seasonal]
"There's a moment in late autumn — the air gets thin and dry, and your lips crack before you even notice. That's your body's way of writing you a note: 'I need something moist.' Listen to it."

### M-09 | scene: product_story | tags: [warmth, family]
"My grandmother never called it 'health food.' She just said 'something good for winter.' No scientific words, no marketing. Just a bowl, and the sound of her saying 'drink it while it's warm.'"

---

## STORY (narrative snippets about origin, people, craft)

### S-01 | scene: product_story | tags: [origin, people] | product: ejiao
"In Dong'e, there's a well. Not fancy — you'd walk right past it. But the locals will tell you the water from that well is why Dong'e ejiao tastes different from any other. Something about the mineral content, the temperature, the way it interacts with the hide. Science has explanations. The old masters just say: 'It's the well.'"

### S-02 | scene: product_story | tags: [origin, process] | product: yam
"Iron-stick yam from Wen County takes 10 months in the ground. Sandy-soil yam takes 5. The farmer doesn't make more money for waiting longer — the market price is similar. But the mucin protein content is triple. That's the difference between fast and patient."

### S-03 | scene: product_story | tags: [people, craft] | product: tremella
"In Gutian, Fujian, the tremella growers check their cultivation rooms at 2am. Not because they have to — the automated sprayers handle humidity. They check because 'you can feel if it's right.' Thirty years of growing and they still trust their hands more than the sensors."

### S-04 | scene: product_story | tags: [origin, contrast] | product: goji
"Zhongning goji versus generic goji — put them side by side and you can see it. Zhongning berries are smaller, darker red, and when you bite one, the juice stains your fingers. The generic ones are plump and pretty, but they taste like water with food coloring."

### S-05 | scene: product_story | tags: [season, tradition]
"There's a saying in traditional food therapy: 'Qiu shou dong cang' — harvest in autumn, store in winter. It's not just about crops. It's about your body. Autumn is when you stock up on what you'll need to get through the cold months."

### S-06 | scene: product_story | tags: [people, dedication] | product: astragalus
"The best astragalus comes from high-altitude plateaus in Gansu. The harvesters dig by hand — machines damage the root. One man told me he's been doing this for 22 years. 'The mountain soil is different every year,' he said. 'You have to feel where the root runs.'"

### S-07 | scene: product_story | tags: [process, craft] | product: ejiao
"Ejiao simmering is three days and three nights. The fire can't be too strong or too weak. The old masters say 'wen huo man ao' — gentle fire, slow cooking. In a world that wants everything instant, this process is almost rebellious."

### S-08 | scene: product_story | tags: [origin, nature] | product: red-dates
"Hetian red dates from Xinjiang get 15 hours of sunlight a day in summer. The temperature swings 20 degrees between day and night. That stress — the heat, the cold, the dry air — is what concentrates the sweetness. The harshest conditions make the sweetest fruit."

---

## KNOWLEDGE (small facts and food-therapy wisdom)

### K-01 | scene: product_detail | tags: [food-therapy, seasonal]
"The old saying goes: 'Qiu zao shang fei' — autumn dryness harms the lungs. That's not mysticism — dry air genuinely irritates airways and skin. Traditional response: moisten from inside. Tremella soup, pear, honey, lily bulb. Our ancestors didn't have humidifiers, but they had kitchens."

### K-02 | scene: product_detail | tags: [nutrition, science] | product: yam
"Iron-stick yam is unusually high in mucin protein — that slippery coating when you peel it. Mucin forms a protective film on mucous membranes. That's why traditional medicine says yam 'strengthens the spleen' — it's literally coating your digestive tract."

### K-03 | scene: product_detail | tags: [food-therapy, concept]
"'Bu qi' — replenishing vital energy. Sounds mystical, but think of it practically: when you're exhausted, cold, and catching every bug, that's what traditional medicine calls 'qi deficiency.' The dietary response: warm, easy-to-digest, nutrient-dense foods. Astragalus, yam, red dates."

### K-04 | scene: product_detail | tags: [preparation, practical] | product: yam-powder
"The trick with yam powder: NEVER use boiling water directly. Use 60-degree water first, stir into a paste, THEN add hot water. Boiling water hits the starch too fast and you get lumps. Every single complaint about 'clumpy yam powder' is a water temperature problem."

### K-05 | scene: product_detail | tags: [nutrition, practical] | product: ejiao
"Ejiao is essentially concentrated collagen and amino acids. Your body breaks it down the same way it breaks down any protein — it's not magic. But as a consistent daily supplement, it gives your body building blocks it can use. Think of it as premium raw material, not a miracle."

### K-06 | scene: opening | tags: [seasonal, solar-term]
"Today is Bai Lu — White Dew. The name tells you everything: it's the moment when morning moisture starts condensing. The air turns. Your body feels it before your mind does. This is when the kitchen clock resets from cold soups to warm pots."

### K-07 | scene: product_detail | tags: [comparison, practical] | product: goji
"Fresh goji versus dried goji — most people don't realize fresh goji exists. It's a completely different experience: juicy, slightly tart, more vitamin C. Dried goji concentrates the sweetness and makes it shelf-stable, but you lose some water-soluble nutrients. Both are good. Just different."

### K-08 | scene: qa_live | tags: [safety, medical]
"A fair question and I want to be straight with you: I'm not a doctor. Traditional food therapy is about daily dietary habits, not medical treatment. If you have a specific condition — diabetes, pregnancy, allergies — please consult your doctor before adding anything new. I can tell you about the food; your doctor tells you about YOUR body."

---

## TRANSITION (bridges between topics/products)

### T-01 | scene: transition | tags: [natural-bridge]
"Speaking of patience in the kitchen... you know what else takes patience? The next product I want to show you. Different ingredient, same philosophy: slow is better."

### T-02 | scene: transition | tags: [seasonal-bridge]
"We just talked about moistening in autumn. But there's another side to autumn eating — warming the core. And that's where this next one comes in."

### T-03 | scene: transition | tags: [contrast-bridge]
"The ejiao we just looked at is about gentle, slow nourishment. This next product is its counterpart — same philosophy, completely different experience. Let me show you."

### T-04 | scene: transition | tags: [story-bridge]
"Remember I mentioned that farmer in Wen County? Well, on that same trip, I stopped at a market in Jiaozuo and found something I wasn't expecting..."

### T-05 | scene: transition | tags: [question-bridge]
"Someone just asked in the comments: 'What do you pair with the ejiao cake?' Perfect timing — because the next product is literally the answer."

---

## SELF_TALK (newcomer authenticity, self-deprecation, sincerity)

### ST-01 | scene: opening | tags: [newcomer, honest]
"Alright, I'll be real — I've been doing this for [X] weeks and I still get nervous when the viewer count goes above 50. But I figure if I'm going to be nervous, I might as well be nervous while showing you something genuinely good."

### ST-02 | scene: product_detail | tags: [personal, authentic]
"I started having this every morning about two weeks ago. Not because I'm selling it — I started before I ever planned this live. My skin didn't transform and I didn't lose 10 years. But I stopped feeling that 3pm crash. That's enough for me."

### ST-03 | scene: qa_live | tags: [humble, learning]
"Honestly? I don't know the answer to that one. Let me look it up after the live and I'll post it in the fan group. I'd rather say 'I don't know' than make something up."

### ST-04 | scene: soft_push | tags: [sincere, anti-pressure]
"Look, I'm not going to pretend there are only 50 sets left and a countdown timer. There are [X] sets. The price is [Y]. If what I described sounds like something you'd use, the link is there. If not, totally fine — thanks for listening to me ramble about yams for twenty minutes."

### ST-05 | scene: closing | tags: [grateful, warm]
"I know my live rooms aren't the most exciting — no dancing, no games, just me talking about food for two hours. If you stayed this long, that means something to me. Genuinely. Thank you."

### ST-06 | scene: hard_push | tags: [newcomer, gentle-sell]
"I'm supposed to create urgency right now — that's what the playbook says. But I think if I explained the product well enough, you already know if you want it. So I'll just say: link is up, cart item number [X], and if you need a minute to think, that's completely fine."

---

## GOLDEN (quotable one-liners for screenshots)

### G-01 | scene: metaphor_moment | tags: [seasonal, philosophy]
"Autumn isn't something you survive. It's something you nourish back from."

### G-02 | scene: product_story | tags: [craft, patience]
"The best things in the kitchen never learned to hurry."

### G-03 | scene: closing | tags: [warmth, care]
"Taking care of yourself isn't selfish. It's the first honest thing you can do every morning."

### G-04 | scene: product_story | tags: [origin, earth] | product: yam
"The soil holds on, and the yam doesn't give up. That's why it's good."

### G-05 | scene: metaphor_moment | tags: [food, connection]
"Every bowl of soup carries a place, a season, and someone who cared enough to stir it."

### G-06 | scene: closing | tags: [simplicity, authentic]
"The recipe for a good life isn't complicated — eat in season, sleep on time, and find something warm to hold."

### G-07 | scene: product_story | tags: [time, value]
"Ten months in the ground. Three days in the pot. Five minutes in your bowl. The math of real food always looks unfair."

### G-08 | scene: metaphor_moment | tags: [seasonal, body]
"Your body writes you notes all year. Dry lips in autumn, cold hands in winter. Most people ignore them. Tonic food is just... reading the mail."

---

## SOFT_CTA (gentle deal introduction)

### SC-01 | scene: soft_push | tags: [story-to-deal]
"So that's the story — from that well in Dong'e to this package in front of me. Tonight's live-room price is [X] yuan, which includes [extras]. I set this up because I wanted to make it easy to try."

### SC-02 | scene: soft_push | tags: [value-framing]
"Do the math with me: [X] yuan divided by [Y] days of use — that's [Z] yuan per day. Less than a cup of coffee. Except this stays with you longer than caffeine."

### SC-03 | scene: soft_push | tags: [gentle-invite]
"If you've been thinking about trying this kind of thing but never had a good entry point — this is a decent one. Good product, fair price, and you heard the whole story behind it."

### SC-04 | scene: product_detail | tags: [natural-mention]
"By the way, for tonight we put together a bundle: [description]. It's in the cart, item number [X]. No pressure — I'll keep talking about it either way."

### SC-05 | scene: soft_push | tags: [seasonal-nudge]
"Li Dong is [X] days away. If you want to start your winter pantry, this is a good first item. The shelf life is [Y] months, so no rush to use it all at once."

---

## HARD_CTA (clear call to action — newcomer-warm style)

### HC-01 | scene: hard_push | tags: [direct, clear]
"Okay, link is up. Cart item number [X]. [Product name], [quantity], [price] yuan. That includes [extras]. If you want it, tap the cart now."

### HC-02 | scene: hard_push | tags: [urgency-honest]
"We prepared [X] sets for tonight. I'm not going to pretend that's a made-up number — it's what we have. Once they're gone, next restock is in [Y] weeks. Just being transparent."

### HC-03 | scene: hard_push | tags: [last-call]
"Last mention tonight — [product name], [price] yuan, cart item [X]. After this I'm moving to the next product and won't come back to it. Your call."

### HC-04 | scene: hard_push | tags: [rational-push]
"Let me break it down one more time: [price] gets you [contents]. Per day that's [daily cost]. [Comparable product] in a store runs [higher price]. The live-room price is [difference] lower. That's the deal."

### HC-05 | scene: hard_push | tags: [newcomer-soft]
"I know I'm supposed to count down right now. I'm not going to do that. The link is there, the price is clear, and you're smart enough to decide. I'll be here if you have questions."
```

- [ ] **Step 2: Commit**

```bash
cd ~/.claude/skills/dongyuhui-live
git add references/phrase-library.md
git commit -m "feat: add phrase library with ~80 seed phrases across 9 unit types"
```

---

## Task 7: Products scaffold + compliance defaults

**Files:**
- Create: `~/.claude/skills/dongyuhui-live/products/README.md`
- Create: `~/.claude/skills/dongyuhui-live/products/_defaults/compliance-tonic-health.md`

### Context

Products directory holds per-product profiles. The README defines the profile format. The compliance file is the universal forbidden-word/claim list for tonic-health, based on Chinese advertising law and food safety regulations. New products copy from this baseline and customize.

- [ ] **Step 1: Create products/README.md**

```markdown
# Product Profiles

Each product gets its own directory: `products/<slug>/profile.md`

## Directory structure

```
products/
├── _defaults/
│   └── compliance-tonic-health.md    # Universal compliance baseline
├── ejiao-gao/                        # Example product
│   ├── profile.md
│   └── assets/                       # Optional: images, certificates
└── README.md                         # This file
```

## Profile format

Create `products/<slug>/profile.md` with this structure:

```yaml
---
slug: <lowercase-hyphenated>
name: <full product name in Chinese>
category: [滋补养生, 食品]
sku: <optional>
price: <number>
origin: <place>
maker: <brand>
cert: [<food production license>, <test reports>]
shelf_life: <duration>
storage: <conditions>
target_audience: [<audience segment 1>, <audience segment 2>]

# Compliance — start by copying from _defaults/compliance-tonic-health.md
# then customize per product
claims_allowed: [<claim 1>, <claim 2>]
claims_forbidden: [<claim 1>, <claim 2>]
forbidden_words: [<word 1>, <word 2>]
---

# Product Story
<Real, verifiable origin/craft narrative. Not literary — just facts.>

# Ingredients & Process
<Key ingredients, sourcing, manufacturing process.>

# Usage Instructions
<Daily dosage, preparation method, storage after opening.>

# FAQ
Q: <common question>
A: <factual answer>

# Promotion Reference
<Current deals, bundles, gifts, limited quantities.>
```

## How profiles are used

- **GENERATE:** facts, origin stories, ingredients pulled from here
- **REVIEW:** compliance check scans against `claims_forbidden` + `forbidden_words`
- **SEARCH:** product name/category used to filter phrase library results

## No profile? No problem.

The skill degrades gracefully: only uses `references/category-knowledge.md` for general
info. Will NOT invent origin, price, batch, or certification details.
```

- [ ] **Step 2: Create products/_defaults/compliance-tonic-health.md**

```markdown
# Compliance Baseline — Tonic Health & Food Category

Universal forbidden words and claims for tonic-health/food products in Chinese
live-streaming. Based on PRC Advertising Law (guanggao fa), Food Safety Law
(shipin anquan fa), and health food advertising regulations.

Copy relevant items to each product's `claims_forbidden` and `forbidden_words` fields,
then add product-specific restrictions.

## Forbidden Claims (claims_forbidden)

These claim PATTERNS must never appear in generated or reviewed content:

### Medical/therapeutic claims
- Treats / cures / heals any disease or condition
- Prevents any disease
- Has therapeutic or medicinal effects
- Replaces medication or medical treatment
- Clinically proven to [medical effect]
- Recommended by doctors / hospitals
- Lowers blood sugar / blood pressure / cholesterol
- Anti-cancer / anti-tumor properties
- Cures insomnia / depression / anxiety
- Treats anemia / kidney deficiency / liver problems

### Absolute/superlative claims
- Best / number one / top quality in the category
- Lowest price nationwide / online
- No side effects whatsoever
- Suitable for everyone / all ages / all conditions
- 100% effective / guaranteed results
- The only product that...

### Misleading health claims
- Lose weight by eating this
- Look 10 years younger
- Immediate/overnight effects
- Permanent results
- Detoxification (pai du) as a medical claim
- Boosts immunity (mianyi li) as an absolute claim

## Forbidden Words (forbidden_words)

Individual words/phrases to scan for and reject:

### Medical terminology (when used as product claims)
- 治疗 (treat)
- 治愈 (cure)
- 疗效 (therapeutic effect)
- 药用 (medicinal use)
- 药效 (drug efficacy)
- 处方 (prescription)
- 根治 (radical cure)
- 康复 (recovery, in medical context)
- 替代药物 (replace medication)
- 治病 (cure disease)

### Absolute terms
- 最 (most/best, when comparing to competitors)
- 第一 (number one, when ranking products)
- 唯一 (the only)
- 全网最低 (lowest price online)
- 最便宜 (cheapest)
- 史上最 (best in history)
- 天花板 (ceiling/ultimate, in product claims)

### Urgency manipulation
- 立竿见影 (immediate effect)
- 一用就见效 (works immediately)
- 无副作用 (no side effects)
- 纯天然无害 (pure natural harmless — implies medical safety)
- 立刻见效 (instant results)

### Misleading body claims
- 排毒 (detox, as medical claim)
- 减肥 (weight loss, as product effect)
- 降血糖 (lower blood sugar)
- 降血压 (lower blood pressure)
- 降血脂 (lower blood lipids)
- 抗癌 (anti-cancer)
- 抗衰老 (anti-aging, as absolute medical claim)

## Safe Phrasing Alternatives

| Instead of... | Say... |
|---|---|
| "Treats qi deficiency" | "Traditionally enjoyed for daily nourishment" |
| "Cures dry skin" | "A seasonal moistening food in traditional diet" |
| "Boosts immunity" | "Part of a balanced winter diet" |
| "Lowers blood sugar" | "A low-GI food option — consult your doctor for medical advice" |
| "Detoxifies the body" | "A light, clean-ingredient addition to your routine" |
| "Anti-aging miracle" | "A traditional beauty food passed down through generations" |
| "No side effects" | "Made from [specific ingredients] with no added [specific thing]" |

## Notes

- This list is NOT exhaustive. When in doubt, err on the side of caution.
- Food products (shipin) face stricter ad rules than general products.
- Health food (baojian shipin, blue-hat products) has separate regulations not covered here.
- Live-streaming commerce has additional FTC-equivalent disclosure requirements.
- Always check if the product has a "blue hat" (baojian shipin) registration — if not,
  it CANNOT make any health-function claims at all.
```

- [ ] **Step 3: Commit**

```bash
cd ~/.claude/skills/dongyuhui-live
git add products/README.md products/_defaults/compliance-tonic-health.md
git commit -m "feat: add product profile spec and compliance baseline"
```

---

## Task 8: Corpus scaffold + ingestion spec

**Files:**
- Create: `~/.claude/skills/dongyuhui-live/corpus/README.md`

### Context

The corpus README defines the frontmatter format for all corpus entries. Both hand-written (seed/) and script-ingested (ingested/) entries must follow this format. This is the contract between the user, the ingest script, and Claude's search/generate logic.

- [ ] **Step 1: Create corpus/README.md**

```markdown
# Corpus — Dong Yuhui Style Reference Library

This directory holds real speech fragments from Dong Yuhui or similar creators, tagged
for retrieval by the SEARCH and GENERATE branches.

## Directory structure

```
corpus/
├── README.md       # This file — ingestion spec
├── index.md        # Auto-maintained by scripts/ingest_corpus.py
├── seed/           # Hand-curated entries (user-written)
└── ingested/       # Script-imported entries
```

## Entry format

One file per entry. Filename = the `id` field. Extension: `.md`.

```yaml
---
id: <YYYYMMDD>-<product>-<type>-<seq>    # e.g. 20240915-ejiao-story-01
source: <origin description>              # e.g. "与辉同行 · 2024-09-15"
source_url: <url or empty>
segment_type: <one of 9 types>            # HOOK | METAPHOR | STORY | KNOWLEDGE |
                                          # TRANSITION | SELF_TALK | GOLDEN |
                                          # SOFT_CTA | HARD_CTA
product_category: [滋补养生, 食品]         # array
product: <specific product or empty>       # e.g. 阿胶糕
scene: <one of 9 scene IDs>               # opening | product_story | product_detail |
                                          # metaphor_moment | qa_live | soft_push |
                                          # hard_push | transition | closing
tags: [<tag1>, <tag2>]                    # free-form: 产地, 情感, 画面感, 节气, etc.
length_sec: <estimated duration or empty>
style_score:
  literary: <1-5>
  story: <1-5>
  grounded: <1-5>
  rhythm: <1-5>
notes: <optional annotation>
---

<Original speech content. Preserve as-is, no editing.>
```

## Required fields

These fields MUST be present (script will reject entries without them):
- `id`, `source`, `segment_type`, `product_category`, `scene`, `tags`

## Enumerations

**segment_type:** HOOK, METAPHOR, STORY, KNOWLEDGE, TRANSITION, SELF_TALK, GOLDEN, SOFT_CTA, HARD_CTA

**scene:** opening, product_story, product_detail, metaphor_moment, qa_live, soft_push, hard_push, transition, closing

## Index format (index.md)

Each entry = one line. Auto-generated by the ingest script:

```
- [<id>](<subdir>/<id>.md) · <segment_type> · <product> · [<tags>] · "<first 30 chars>..."
```

Do NOT edit index.md manually. Run `ingest_corpus.py` to rebuild.

## Adding entries manually

1. Create a `.md` file in `corpus/seed/` following the format above
2. Run `python scripts/ingest_corpus.py --rebuild-index` to update `index.md`
   (or add the index line manually if you prefer)

## Privacy

This corpus is for personal use only. Do NOT commit to public repositories or share.
```

- [ ] **Step 2: Commit**

```bash
cd ~/.claude/skills/dongyuhui-live
git add corpus/README.md
git commit -m "feat: add corpus ingestion spec and directory structure"
```

---

## Task 9: Ingest script — tests first (TDD)

**Files:**
- Create: `~/.claude/skills/dongyuhui-live/scripts/ingest_corpus_test.py`

### Context

TDD is NON-NEGOTIABLE per the constitution. Write all 5 test cases BEFORE any implementation. The script uses only stdlib + PyYAML. Tests mock filesystem and external tools.

- [ ] **Step 1: Create ingest_corpus_test.py with all 5 test cases**

```python
"""Tests for ingest_corpus.py — written BEFORE implementation (TDD)."""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def skill_dir():
    """Create a temporary skill directory structure."""
    tmpdir = tempfile.mkdtemp()
    corpus_dir = Path(tmpdir) / "corpus"
    (corpus_dir / "seed").mkdir(parents=True)
    (corpus_dir / "ingested").mkdir(parents=True)
    (corpus_dir / "index.md").write_text(
        "<!-- Corpus index — maintained by scripts/ingest_corpus.py. "
        "Do not edit manually. -->\n"
    )
    scripts_dir = Path(tmpdir) / "scripts"
    scripts_dir.mkdir()
    yield tmpdir
    shutil.rmtree(tmpdir)


@pytest.fixture
def sample_srt(tmp_path):
    """Create a sample SRT file for testing."""
    content = (
        "1\n"
        "00:00:01,000 --> 00:00:05,000\n"
        "This is the first segment about ejiao.\n"
        "\n"
        "2\n"
        "00:00:06,000 --> 00:00:10,000\n"
        "This is the second segment about goji berries.\n"
        "\n"
    )
    srt_file = tmp_path / "test.srt"
    srt_file.write_text(content, encoding="utf-8")
    return srt_file


@pytest.fixture
def sample_txt(tmp_path):
    """Create a sample plain-text file for testing."""
    content = (
        "This is the first paragraph about ejiao.\n"
        "\n"
        "This is the second paragraph about goji berries.\n"
    )
    txt_file = tmp_path / "test.txt"
    txt_file.write_text(content, encoding="utf-8")
    return txt_file


class TestSplitSegments:
    """Test 1: Path A — splitting text into segments."""

    def test_split_srt_into_segments(self, sample_srt):
        from ingest_corpus import split_segments

        segments = split_segments(str(sample_srt))
        assert len(segments) == 2
        assert "first segment about ejiao" in segments[0]
        assert "second segment about goji" in segments[1]

    def test_split_txt_into_segments(self, sample_txt):
        from ingest_corpus import split_segments

        segments = split_segments(str(sample_txt))
        assert len(segments) == 2
        assert "first paragraph about ejiao" in segments[0]
        assert "second paragraph about goji" in segments[1]

    def test_split_empty_file(self, tmp_path):
        from ingest_corpus import split_segments

        empty = tmp_path / "empty.txt"
        empty.write_text("", encoding="utf-8")
        segments = split_segments(str(empty))
        assert segments == []


class TestValidateFrontmatter:
    """Test 2: Path A — frontmatter required fields validation."""

    def test_valid_frontmatter_passes(self):
        from ingest_corpus import validate_frontmatter

        fm = {
            "id": "20240915-ejiao-story-01",
            "source": "test source",
            "segment_type": "STORY",
            "product_category": ["滋补养生"],
            "scene": "product_story",
            "tags": ["产地"],
        }
        # Should not raise
        validate_frontmatter(fm)

    def test_missing_required_field_raises(self):
        from ingest_corpus import validate_frontmatter

        fm = {
            "id": "20240915-ejiao-story-01",
            "source": "test source",
            # missing segment_type, product_category, scene, tags
        }
        with pytest.raises(ValueError, match="segment_type"):
            validate_frontmatter(fm)

    def test_invalid_segment_type_raises(self):
        from ingest_corpus import validate_frontmatter

        fm = {
            "id": "test-01",
            "source": "test",
            "segment_type": "INVALID_TYPE",
            "product_category": ["食品"],
            "scene": "opening",
            "tags": ["test"],
        }
        with pytest.raises(ValueError, match="segment_type"):
            validate_frontmatter(fm)

    def test_invalid_scene_raises(self):
        from ingest_corpus import validate_frontmatter

        fm = {
            "id": "test-01",
            "source": "test",
            "segment_type": "HOOK",
            "product_category": ["食品"],
            "scene": "invalid_scene",
            "tags": ["test"],
        }
        with pytest.raises(ValueError, match="scene"):
            validate_frontmatter(fm)


class TestWriteEntry:
    """Test 3: Path A — writing entry and updating index."""

    def test_write_entry_creates_file_and_updates_index(self, skill_dir):
        from ingest_corpus import write_entry

        fm = {
            "id": "20240915-ejiao-story-01",
            "source": "与辉同行 · 2024-09-15",
            "source_url": "",
            "segment_type": "STORY",
            "product_category": ["滋补养生", "食品"],
            "product": "阿胶糕",
            "scene": "product_story",
            "tags": ["产地", "情感"],
            "length_sec": 45,
            "style_score": {"literary": 4, "story": 5, "grounded": 5, "rhythm": 4},
            "notes": "test entry",
        }
        content = "This is the original speech content."

        write_entry(
            skill_dir=skill_dir,
            subdir="ingested",
            frontmatter=fm,
            content=content,
        )

        # Check file was created
        entry_path = Path(skill_dir) / "corpus" / "ingested" / "20240915-ejiao-story-01.md"
        assert entry_path.exists()
        text = entry_path.read_text(encoding="utf-8")
        assert "segment_type: STORY" in text
        assert "This is the original speech content." in text

        # Check index was updated
        index_path = Path(skill_dir) / "corpus" / "index.md"
        index_text = index_path.read_text(encoding="utf-8")
        assert "20240915-ejiao-story-01" in index_text
        assert "STORY" in index_text
        assert "阿胶糕" in index_text


class TestDuplicateId:
    """Test 4: Path A — duplicate ID rejection."""

    def test_duplicate_id_rejected_without_force(self, skill_dir):
        from ingest_corpus import write_entry

        fm = {
            "id": "20240915-ejiao-story-01",
            "source": "test",
            "segment_type": "STORY",
            "product_category": ["滋补养生"],
            "product": "",
            "scene": "product_story",
            "tags": ["test"],
        }

        write_entry(
            skill_dir=skill_dir,
            subdir="ingested",
            frontmatter=fm,
            content="First version.",
        )

        with pytest.raises(FileExistsError, match="already exists"):
            write_entry(
                skill_dir=skill_dir,
                subdir="ingested",
                frontmatter=fm,
                content="Duplicate version.",
                force=False,
            )

    def test_duplicate_id_allowed_with_force(self, skill_dir):
        from ingest_corpus import write_entry

        fm = {
            "id": "20240915-ejiao-story-01",
            "source": "test",
            "segment_type": "STORY",
            "product_category": ["滋补养生"],
            "product": "",
            "scene": "product_story",
            "tags": ["test"],
        }

        write_entry(
            skill_dir=skill_dir,
            subdir="ingested",
            frontmatter=fm,
            content="First version.",
        )

        # Should NOT raise with force=True
        write_entry(
            skill_dir=skill_dir,
            subdir="ingested",
            frontmatter=fm,
            content="Overwritten version.",
            force=True,
        )

        entry_path = Path(skill_dir) / "corpus" / "ingested" / "20240915-ejiao-story-01.md"
        assert "Overwritten version." in entry_path.read_text(encoding="utf-8")


class TestUrlPathDependencyCheck:
    """Test 5: Path B — missing yt-dlp/whisper detection."""

    def test_missing_ytdlp_raises_clear_error(self):
        from ingest_corpus import check_url_dependencies

        with patch("shutil.which", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                check_url_dependencies()
            # Should exit with clear message about missing tools
            assert exc_info.value.code != 0

    def test_all_dependencies_present_passes(self):
        from ingest_corpus import check_url_dependencies

        def mock_which(name):
            return f"/usr/bin/{name}" if name in ("yt-dlp", "ffmpeg") else None

        with patch("shutil.which", side_effect=mock_which):
            # Should not raise (whisper is optional if faster-whisper or whisper exists)
            # For this test, we mock whisper as available too
            def mock_which_all(name):
                return f"/usr/bin/{name}"

            with patch("shutil.which", side_effect=mock_which_all):
                check_url_dependencies()  # Should not raise
```

- [ ] **Step 2: Run the tests — verify they FAIL**

```bash
cd ~/.claude/skills/dongyuhui-live/scripts
python -m pytest ingest_corpus_test.py -v
```

Expected: `ModuleNotFoundError: No module named 'ingest_corpus'` — all tests fail because the implementation doesn't exist yet.

- [ ] **Step 3: Commit failing tests**

```bash
cd ~/.claude/skills/dongyuhui-live
git add scripts/ingest_corpus_test.py
git commit -m "test: add ingest_corpus tests (red phase — implementation pending)"
```

---

## Task 10: Ingest script — implementation

**Files:**
- Create: `~/.claude/skills/dongyuhui-live/scripts/ingest_corpus.py`

### Context

Implement the functions that the tests in Task 9 exercise. Pure Python stdlib + PyYAML. Single file, under 300 lines. The script has two modes: `--from-text` (main path, zero deps) and `--from-url` (optional, needs yt-dlp + whisper). Also supports `--rebuild-index` to regenerate `corpus/index.md` from existing files.

- [ ] **Step 1: Create ingest_corpus.py**

```python
#!/usr/bin/env python3
"""Corpus ingestion tool for dongyuhui-live skill.

Path A (main): --from-text <file>  — split text/SRT/VTT, interactive tagging, write corpus
Path B (opt):  --from-url <url>    — download + transcribe, then hand to Path A
Utility:       --rebuild-index     — regenerate corpus/index.md from existing files
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install PyYAML")
    sys.exit(1)


# ── Constants ──────────────────────────────────────────────────────────────────

SEGMENT_TYPES = frozenset(
    ["HOOK", "METAPHOR", "STORY", "KNOWLEDGE", "TRANSITION",
     "SELF_TALK", "GOLDEN", "SOFT_CTA", "HARD_CTA"]
)

SCENE_IDS = frozenset(
    ["opening", "product_story", "product_detail", "metaphor_moment",
     "qa_live", "soft_push", "hard_push", "transition", "closing"]
)

REQUIRED_FIELDS = ("id", "source", "segment_type", "product_category", "scene", "tags")

SKILL_DIR = Path(__file__).resolve().parent.parent


# ── Pure functions ─────────────────────────────────────────────────────────────


def split_segments(file_path: str) -> list[str]:
    """Split a text/SRT/VTT file into individual speech segments.

    SRT: splits on subtitle boundaries (numbered blocks).
    TXT/VTT: splits on blank lines.
    Returns list of non-empty text segments.
    """
    path = Path(file_path)
    text = path.read_text(encoding="utf-8")

    if not text.strip():
        return []

    ext = path.suffix.lower()

    if ext == ".srt":
        # SRT format: blocks separated by blank lines
        # Each block: number, timestamp, text
        blocks = re.split(r"\n\s*\n", text.strip())
        segments = []
        for block in blocks:
            lines = block.strip().split("\n")
            # Skip block number and timestamp lines
            text_lines = [
                line for line in lines
                if not re.match(r"^\d+$", line.strip())
                and not re.match(r"\d{2}:\d{2}:\d{2}", line.strip())
            ]
            segment = " ".join(text_lines).strip()
            if segment:
                segments.append(segment)
        return segments

    # Default: split on blank lines (TXT, VTT, etc.)
    blocks = re.split(r"\n\s*\n", text.strip())
    if ext == ".vtt":
        # Skip VTT header and timestamp lines
        segments = []
        for block in blocks:
            lines = block.strip().split("\n")
            text_lines = [
                line for line in lines
                if not line.strip().startswith("WEBVTT")
                and not re.match(r"\d{2}:\d{2}:\d{2}", line.strip())
                and not re.match(r"^\d+$", line.strip())
            ]
            segment = " ".join(text_lines).strip()
            if segment:
                segments.append(segment)
        return segments

    return [b.strip() for b in blocks if b.strip()]


def validate_frontmatter(fm: dict) -> None:
    """Validate that required fields are present and enum values are correct.

    Raises ValueError with a descriptive message on failure.
    """
    for field in REQUIRED_FIELDS:
        if field not in fm or not fm[field]:
            raise ValueError(
                f"Missing required field: {field}. "
                f"Required: {', '.join(REQUIRED_FIELDS)}"
            )

    if fm["segment_type"] not in SEGMENT_TYPES:
        raise ValueError(
            f"Invalid segment_type: '{fm['segment_type']}'. "
            f"Must be one of: {', '.join(sorted(SEGMENT_TYPES))}"
        )

    if fm["scene"] not in SCENE_IDS:
        raise ValueError(
            f"Invalid scene: '{fm['scene']}'. "
            f"Must be one of: {', '.join(sorted(SCENE_IDS))}"
        )


def build_entry_text(frontmatter: dict, content: str) -> str:
    """Build the full Markdown entry with YAML frontmatter."""
    fm_text = yaml.dump(
        frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False
    )
    return f"---\n{fm_text}---\n\n{content}\n"


def build_index_line(subdir: str, frontmatter: dict, content: str) -> str:
    """Build a single index.md line for this entry."""
    entry_id = frontmatter["id"]
    seg_type = frontmatter["segment_type"]
    product = frontmatter.get("product", "")
    tags = frontmatter.get("tags", [])
    preview = content[:30].replace("\n", " ")
    if len(content) > 30:
        preview += "..."
    tags_str = ", ".join(tags) if tags else ""
    return (
        f"- [{entry_id}]({subdir}/{entry_id}.md) "
        f"· {seg_type} · {product} · [{tags_str}] · \"{preview}\""
    )


# ── Side-effect functions ──────────────────────────────────────────────────────


def write_entry(
    skill_dir: str,
    subdir: str,
    frontmatter: dict,
    content: str,
    force: bool = False,
) -> Path:
    """Write a corpus entry file and update index.md.

    Args:
        skill_dir: Root of the skill directory.
        subdir: 'seed' or 'ingested'.
        frontmatter: Validated frontmatter dict.
        content: The raw speech content.
        force: If True, overwrite existing entries.

    Returns:
        Path to the created entry file.

    Raises:
        FileExistsError: If entry already exists and force=False.
    """
    validate_frontmatter(frontmatter)

    root = Path(skill_dir)
    entry_id = frontmatter["id"]
    entry_dir = root / "corpus" / subdir
    entry_dir.mkdir(parents=True, exist_ok=True)
    entry_path = entry_dir / f"{entry_id}.md"

    if entry_path.exists() and not force:
        raise FileExistsError(
            f"Entry already exists: {entry_path}. Use --force to overwrite."
        )

    entry_text = build_entry_text(frontmatter, content)
    entry_path.write_text(entry_text, encoding="utf-8")

    # Update index
    index_path = root / "corpus" / "index.md"
    index_line = build_index_line(subdir, frontmatter, content)

    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
        # Remove old line for this ID if force-overwriting
        lines = [
            line for line in existing.split("\n")
            if f"[{entry_id}]" not in line
        ]
        lines.append(index_line)
        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        index_path.write_text(index_line + "\n", encoding="utf-8")

    return entry_path


def rebuild_index(skill_dir: str) -> int:
    """Rebuild corpus/index.md from all existing .md files in seed/ and ingested/.

    Returns the number of entries indexed.
    """
    root = Path(skill_dir)
    index_path = root / "corpus" / "index.md"
    lines = [
        "<!-- Corpus index — maintained by scripts/ingest_corpus.py. "
        "Do not edit manually. -->"
    ]
    count = 0

    for subdir in ("seed", "ingested"):
        dir_path = root / "corpus" / subdir
        if not dir_path.exists():
            continue
        for entry_file in sorted(dir_path.glob("*.md")):
            text = entry_file.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            # Extract frontmatter
            parts = text.split("---", 2)
            if len(parts) < 3:
                continue
            fm = yaml.safe_load(parts[1])
            content = parts[2].strip()
            lines.append(build_index_line(subdir, fm, content))
            count += 1

    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def check_url_dependencies() -> None:
    """Check that yt-dlp, ffmpeg, and a whisper variant are available.

    Exits with code 1 and a clear message if any dependency is missing.
    """
    missing = []
    for tool in ("yt-dlp", "ffmpeg"):
        if shutil.which(tool) is None:
            missing.append(tool)

    # Check for any whisper variant
    whisper_found = any(
        shutil.which(w) is not None
        for w in ("faster-whisper", "whisper", "whisper-ctranslate2")
    )
    if not whisper_found:
        missing.append("faster-whisper (or whisper)")

    if missing:
        print("ERROR: Missing required tools for URL ingestion:")
        for tool in missing:
            print(f"  - {tool}")
        print("\nInstall them:")
        print("  pip install yt-dlp faster-whisper")
        print("  brew install ffmpeg  # or: apt install ffmpeg")
        sys.exit(1)


def interactive_tag_segment(
    segment: str, index: int, total: int, source: str, product: str
) -> dict | None:
    """Interactively prompt user to tag a segment. Returns frontmatter dict or None to skip."""
    print(f"\n{'='*60}")
    print(f"Segment {index + 1}/{total}")
    print(f"{'='*60}")
    print(segment[:200])
    if len(segment) > 200:
        print(f"... ({len(segment)} chars total)")
    print()

    action = input("Tag this segment? [y/n/q] (y=yes, n=skip, q=quit): ").strip().lower()
    if action == "q":
        return None
    if action != "y":
        return {"_skip": True}

    print(f"\nSegment types: {', '.join(sorted(SEGMENT_TYPES))}")
    seg_type = input("segment_type: ").strip().upper()

    print(f"\nScenes: {', '.join(sorted(SCENE_IDS))}")
    scene = input("scene: ").strip().lower()

    tags_input = input("tags (comma-separated): ").strip()
    tags = [t.strip() for t in tags_input.split(",") if t.strip()]

    seq = input("sequence number (e.g. 01): ").strip() or f"{index + 1:02d}"

    product_slug = product.lower().replace(" ", "-") if product else "general"
    entry_id = f"{source.split('·')[-1].strip().replace('-', '').replace(' ', '')}-{product_slug}-{seg_type.lower()}-{seq}"

    return {
        "id": entry_id,
        "source": source,
        "source_url": "",
        "segment_type": seg_type,
        "product_category": ["滋补养生", "食品"],
        "product": product,
        "scene": scene,
        "tags": tags,
        "length_sec": None,
        "style_score": {"literary": 0, "story": 0, "grounded": 0, "rhythm": 0},
        "notes": "",
    }


# ── CLI ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Corpus ingestion tool for dongyuhui-live skill"
    )
    parser.add_argument("--from-text", type=str, help="Path to TXT/SRT/VTT file")
    parser.add_argument("--from-url", type=str, help="Video URL to download + transcribe")
    parser.add_argument("--source", type=str, required=True, help="Source description")
    parser.add_argument("--product", type=str, default="", help="Product name")
    parser.add_argument("--force", action="store_true", help="Overwrite existing entries")
    parser.add_argument(
        "--rebuild-index", action="store_true", help="Rebuild corpus/index.md"
    )
    parser.add_argument(
        "--skill-dir", type=str, default=str(SKILL_DIR), help="Skill root directory"
    )

    args = parser.parse_args()

    if args.rebuild_index:
        count = rebuild_index(args.skill_dir)
        print(f"Index rebuilt: {count} entries")
        return

    if args.from_url:
        check_url_dependencies()
        # Download audio and transcribe — minimal implementation
        import subprocess
        import tempfile

        tmpdir = tempfile.mkdtemp()
        audio_path = os.path.join(tmpdir, "audio.wav")
        print(f"Downloading audio from {args.from_url}...")
        subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "wav", "-o", audio_path, args.from_url],
            check=True,
        )
        print("Transcribing with whisper...")
        transcript_path = os.path.join(tmpdir, "transcript.txt")
        subprocess.run(
            ["faster-whisper", audio_path, "--output_format", "txt",
             "--output_dir", tmpdir],
            check=True,
        )
        # Find the transcript file
        for f in Path(tmpdir).glob("*.txt"):
            if f.name != "transcript.txt":
                transcript_path = str(f)
                break
        args.from_text = transcript_path
        print(f"Transcript saved to {transcript_path}")

    if not args.from_text:
        parser.error("Either --from-text or --from-url is required")

    segments = split_segments(args.from_text)
    if not segments:
        print("No segments found in input file.")
        return

    print(f"Found {len(segments)} segments in {args.from_text}")

    written = 0
    for i, segment in enumerate(segments):
        result = interactive_tag_segment(
            segment, i, len(segments), args.source, args.product
        )
        if result is None:
            print("Quitting.")
            break
        if result.get("_skip"):
            continue

        try:
            path = write_entry(
                skill_dir=args.skill_dir,
                subdir="ingested",
                frontmatter=result,
                content=segment,
                force=args.force,
            )
            print(f"  Written: {path}")
            written += 1
        except (ValueError, FileExistsError) as e:
            print(f"  ERROR: {e}")

    print(f"\nDone. {written} entries written.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the tests — verify they PASS**

```bash
cd ~/.claude/skills/dongyuhui-live/scripts
python -m pytest ingest_corpus_test.py -v
```

Expected: All 5 test classes (10 individual tests) PASS.

- [ ] **Step 3: Commit**

```bash
cd ~/.claude/skills/dongyuhui-live
git add scripts/ingest_corpus.py
git commit -m "feat: implement corpus ingest script (green phase — all tests pass)"
```

---

## Task 11: Final verification + commit

**Files:**
- Verify: all files in `~/.claude/skills/dongyuhui-live/`

### Context

Run the full test suite, verify the directory structure matches the spec, and do a final commit of any missing pieces.

- [ ] **Step 1: Run all tests**

```bash
cd ~/.claude/skills/dongyuhui-live/scripts
python -m pytest ingest_corpus_test.py -v
```

Expected: ALL PASS.

- [ ] **Step 2: Verify directory structure**

```bash
find ~/.claude/skills/dongyuhui-live -type f | sort
```

Expected output (all 12 deliverables from the spec):
```
~/.claude/skills/dongyuhui-live/SKILL.md
~/.claude/skills/dongyuhui-live/corpus/README.md
~/.claude/skills/dongyuhui-live/corpus/index.md
~/.claude/skills/dongyuhui-live/products/README.md
~/.claude/skills/dongyuhui-live/products/_defaults/compliance-tonic-health.md
~/.claude/skills/dongyuhui-live/references/category-knowledge.md
~/.claude/skills/dongyuhui-live/references/phrase-library.md
~/.claude/skills/dongyuhui-live/references/review-checklist.md
~/.claude/skills/dongyuhui-live/references/scene-templates.md
~/.claude/skills/dongyuhui-live/references/style-principles.md
~/.claude/skills/dongyuhui-live/scripts/ingest_corpus.py
~/.claude/skills/dongyuhui-live/scripts/ingest_corpus_test.py
```

- [ ] **Step 3: Final commit**

```bash
cd ~/.claude/skills/dongyuhui-live
git add -A
git status
# If there are uncommitted files:
git commit -m "chore: complete dongyuhui-live skill MVP — all 12 deliverables"
```

- [ ] **Step 4: Commit the plan to vision repo**

```bash
cd /Users/xiu/code/vision
git add docs/superpowers/plans/2026-04-17-dongyuhui-live-skill.md
git commit -m "docs(plans): add dongyuhui-live skill implementation plan"
```

---

## Self-Review Checklist

### Spec coverage

| Spec section | Task(s) | Covered? |
|---|---|---|
| 3.2 Directory structure | T1, T2-T8 | Yes — all dirs + files |
| 4 Intent routing | T1 (SKILL.md) | Yes — full routing table |
| 5 GENERATE | T1 (SKILL.md), T3, T2, T6 | Yes — contract + scenes + style + phrases |
| 6 SEARCH | T1 (SKILL.md), T6, T8 | Yes — contract + phrase lib + index |
| 7 REVIEW | T1 (SKILL.md), T4 | Yes — 7+1 rubric + template |
| 8 Products | T7 | Yes — README + compliance |
| 9 Corpus | T8, T1 | Yes — README + index |
| 10 Ingest script | T9, T10 | Yes — TDD tests + implementation |
| 11 SKILL.md | T1 | Yes — full SKILL.md |
| 12 Deliverables | T11 | Yes — verification step checks all 12 |
| 13 Validation | T11 | Yes — automated + manual replay described in spec |

### Placeholder scan

No TBD, TODO, or "implement later" found.

### Type consistency

- `split_segments` → returns `list[str]` → used in both tests and main()
- `validate_frontmatter` → raises `ValueError` → tests check `ValueError`
- `write_entry` → raises `FileExistsError` → tests check `FileExistsError`
- `check_url_dependencies` → calls `sys.exit(1)` → tests check `SystemExit`
- `SEGMENT_TYPES` / `SCENE_IDS` → same sets in constants, validation, and corpus/README.md
