# Python Monorepo Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the Vision Python codebase from a single `pyproject.toml` to a uv workspace monorepo with 4 packages (`vision-shared` / `vision-intelligence` / `vision-live` / `vision-api`), without changing runtime behavior.

**Architecture:** Introduce `python-packages/<name>/src/vision_<name>/` layout per package. The root `pyproject.toml` becomes a workspace aggregator that depends on `vision-api`, which transitively pulls in the rest. All `src.X.Y` imports rewrite to `vision_X.Y`. Tests stay colocated with sources using `*_test.py` naming. Migration is bottom-up: `shared` → `intelligence` → `live` → `api`, each step commit-sized and independently revertible.

**Tech Stack:** `uv` workspaces, `hatchling` build backend, `pytest` + `pytest-asyncio`, `ruff`. No new runtime dependencies.

**Source spec:** `docs/superpowers/specs/2026-04-18-python-monorepo-migration-design.md`

---

## Pre-Flight

### Task 0: Create the feature branch

**Files:**
- None (git only)

- [ ] **Step 0.1: Verify you start from latest `feat/session-memory-and-litellm` or the branch the spec was committed on**

```bash
cd /Users/xiu/code/vision
git status
git log --oneline -n 3
```

Expected: working tree clean, most recent commit is the spec alignment commit.

- [ ] **Step 0.2: Create and switch to the refactor branch**

```bash
git checkout -b refactor/python-monorepo
git status
```

Expected: switched to new branch, tree clean.

---

## Phase A — Scaffolding (no code moves yet)

### Task 1: Create `python-packages/` directory tree with empty packages

**Files:**
- Create: `python-packages/shared/src/vision_shared/__init__.py`
- Create: `python-packages/intelligence/src/vision_intelligence/__init__.py`
- Create: `python-packages/live/src/vision_live/__init__.py`
- Create: `python-packages/api/src/vision_api/__init__.py`

- [ ] **Step 1.1: Create the directory skeleton**

```bash
mkdir -p python-packages/shared/src/vision_shared
mkdir -p python-packages/intelligence/src/vision_intelligence
mkdir -p python-packages/live/src/vision_live
mkdir -p python-packages/api/src/vision_api
```

- [ ] **Step 1.2: Create empty `__init__.py` for each new package namespace**

Write these 4 files with identical content `"""Vision <pkg> package."""` (adjust pkg name):

```python
"""Vision shared package."""
```

```python
"""Vision intelligence package."""
```

```python
"""Vision live package."""
```

```python
"""Vision api package."""
```

- [ ] **Step 1.3: Commit**

```bash
git add python-packages/
git commit -m "chore(monorepo): scaffold python-packages/ skeleton"
```

### Task 2: Write per-package `pyproject.toml` files

**Files:**
- Create: `python-packages/shared/pyproject.toml`
- Create: `python-packages/intelligence/pyproject.toml`
- Create: `python-packages/live/pyproject.toml`
- Create: `python-packages/api/pyproject.toml`

- [ ] **Step 2.1: Write `python-packages/shared/pyproject.toml`**

```toml
[project]
name = "vision-shared"
version = "0.1.0"
description = "Vision shared utilities: database, event bus, common helpers"
requires-python = ">=3.13"
license = { text = "MIT" }
dependencies = [
    "aiosqlite>=0.20",
    "pyyaml>=6.0.3",
    "python-dotenv>=1.2.2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vision_shared"]
```

- [ ] **Step 2.2: Write `python-packages/intelligence/pyproject.toml`**

```toml
[project]
name = "vision-intelligence"
version = "0.1.0"
description = "Vision intelligence modules (competitor monitoring, topic discovery, content ingestion)"
requires-python = ">=3.13"
license = { text = "MIT" }
dependencies = [
    "vision-shared",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vision_intelligence"]
```

- [ ] **Step 2.3: Write `python-packages/live/pyproject.toml`**

```toml
[project]
name = "vision-live"
version = "0.1.0"
description = "Vision live-streaming modules: session, danmaku, TTS, RAG, LLM gateway"
requires-python = ">=3.13"
license = { text = "MIT" }
dependencies = [
    "vision-shared",
    "litellm>=1.50.0",
    "chromadb>=0.5.0",
    "sentence-transformers>=3.0.0",
    "google-genai>=1.72.0",
    "google-cloud-aiplatform>=1.147.0",
    "google-cloud-texttospeech>=2.17.0",
    "pyttsx3>=2.99",
    "sounddevice>=0.5.5",
    "numpy>=2.4.4",
    "mitmproxy>=12.2.1",
    "playwright>=1.49.0",
    "betterproto>=2.0.0b7",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vision_live"]
```

- [ ] **Step 2.4: Write `python-packages/api/pyproject.toml`**

```toml
[project]
name = "vision-api"
version = "0.1.0"
description = "Vision FastAPI entrypoint"
requires-python = ">=3.13"
license = { text = "MIT" }
dependencies = [
    "vision-shared",
    "vision-intelligence",
    "vision-live",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic-settings>=2.0",
    "python-multipart>=0.0.9",
]

[project.scripts]
vision-api = "vision_api.main:run"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vision_api"]
```

- [ ] **Step 2.5: Commit**

```bash
git add python-packages/*/pyproject.toml
git commit -m "chore(monorepo): add per-package pyproject.toml stubs"
```

### Task 3: Update root `pyproject.toml` to declare the workspace

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 3.1: Replace root `pyproject.toml` content**

Keep current runtime `dependencies` (safety net during migration; they are removed in Task 12). Add `[tool.uv.workspace]`, `[tool.uv.sources]`, and update `[tool.pytest.ini_options]`.

Full file content:

```toml
[project]
name = "vision"
version = "0.1.0"
description = "Visual content creation toolkit — live streaming, video editing, audio processing"
readme = "README.md"
requires-python = ">=3.13"
license = { text = "MIT" }

# TEMPORARY safety net during monorepo migration.
# Will be replaced with `vision-api` in Task 12.
dependencies = [
    "google-cloud-aiplatform>=1.147.0",
    "google-cloud-texttospeech>=2.17.0",
    "google-genai>=1.72.0",
    "mitmproxy>=12.2.1",
    "numpy>=2.4.4",
    "python-dotenv>=1.2.2",
    "pyttsx3>=2.99",
    "pyyaml>=6.0.3",
    "sounddevice>=0.5.5",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic-settings>=2.0",
    "aiosqlite>=0.20",
    "playwright>=1.49.0",
    "betterproto>=2.0.0b7",
    "litellm>=1.50.0",
    "chromadb>=0.5.0",
    "sentence-transformers>=3.0.0",
    "python-multipart>=0.0.9",
]

[tool.uv.workspace]
members = ["python-packages/*"]

[tool.uv.sources]
vision-shared = { workspace = true }
vision-intelligence = { workspace = true }
vision-live = { workspace = true }
vision-api = { workspace = true }

[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
    "ruff>=0.8.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["src", "tests", "python-packages"]
python_files = ["*_test.py", "test_*.py"]
markers = [
    "slow: tests that download models / run real embeddings",
]

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = [
    "E",
    "W",
    "F",
    "I",
    "B",
    "C4",
    "UP",
]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

> **Why `testpaths = ["src", "tests", "python-packages"]`:** During intermediate commits we have tests in both old and new locations. The final cleanup (Task 13) narrows `testpaths` to `["python-packages"]`.

- [ ] **Step 3.2: Run `uv sync` to resolve the workspace**

```bash
uv sync
```

Expected: uv installs the 4 new workspace packages as editable + keeps existing dependencies. No errors.

- [ ] **Step 3.3: Run full test suite before any code moves**

```bash
uv run pytest -q
```

Expected: same pass/fail count as on `master` (establishes baseline). Record the number here:

> Baseline passed: __ tests (fill in during execution)

- [ ] **Step 3.4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(monorepo): declare uv workspace with 4 members"
```

---

## Phase B — Migrate `shared` (leaf, no internal deps)

### Task 4: Move `src/shared/` sources into `vision_shared`

**Files:**
- Move `src/shared/db.py` → `python-packages/shared/src/vision_shared/db.py`
- Move `src/shared/event_bus.py` → `python-packages/shared/src/vision_shared/event_bus.py`
- Move `src/shared/ordered_item_store.py` → `python-packages/shared/src/vision_shared/ordered_item_store.py`
- Move `src/shared/ordered_item_store_test.py` → `python-packages/shared/src/vision_shared/ordered_item_store_test.py`
- Delete `src/shared/__init__.py` (superseded by the new package's `__init__.py`)

- [ ] **Step 4.1: Move source files with `git mv` (preserves history)**

```bash
git mv src/shared/db.py python-packages/shared/src/vision_shared/db.py
git mv src/shared/event_bus.py python-packages/shared/src/vision_shared/event_bus.py
git mv src/shared/ordered_item_store.py python-packages/shared/src/vision_shared/ordered_item_store.py
git mv src/shared/ordered_item_store_test.py python-packages/shared/src/vision_shared/ordered_item_store_test.py
git rm src/shared/__init__.py
```

- [ ] **Step 4.2: Rewrite imports inside the moved files**

Files in `python-packages/shared/src/vision_shared/` only reference other shared modules. Replace `from src.shared.X` with `from vision_shared.X`:

```bash
grep -rn "from src\.shared" python-packages/shared/src/vision_shared/
```

Expected files needing edits (confirm with the command above):

- `python-packages/shared/src/vision_shared/db.py` — 2 `from src.shared...` occurrences
- `python-packages/shared/src/vision_shared/ordered_item_store_test.py` — 1 occurrence

For each occurrence, manually (or with `sed -i '' 's/from src\.shared\./from vision_shared./g' <file>` on macOS) change:

```diff
- from src.shared.ordered_item_store import OrderedItemStore
+ from vision_shared.ordered_item_store import OrderedItemStore
```

> [!WARNING]
> Use manual review, not blind sed, because `from src.shared.plan_store` does not exist (plan_store lives in `src/live/`). Do NOT rewrite imports that aren't prefixed with `src.shared.` yet.

- [ ] **Step 4.3: Verify `vision_shared` is self-contained**

```bash
grep -rn "from src\." python-packages/shared/src/vision_shared/
```

Expected: no matches (shared only imports stdlib and third-party).

- [ ] **Step 4.4: Run shared package tests**

```bash
uv run pytest python-packages/shared -q
```

Expected: all tests that used to pass in `src/shared/` still pass (`ordered_item_store_test.py`).

- [ ] **Step 4.5: Keep legacy imports working via a bridge (temporary)**

Other modules still `import src.shared.db`. Leave `src/shared/` as an empty directory temporarily — we will rewrite their imports in later tasks. To prevent `ModuleNotFoundError` during intermediate commits, add a re-export stub at `src/shared/__init__.py`:

Actually, **skip the stub**. The C1 decision is "no compatibility shims". Instead, we rewrite callers to `vision_shared` **in the same commit** as the move by including a one-shot rewrite of every `from src.shared` usage across the repo.

Run:

```bash
grep -rln "from src\.shared" src/ scripts/ tests/
```

Expected files (confirm count):

- `src/api/main.py`
- `src/api/deps.py`
- `src/live/*.py` — many files (see full list via grep)
- `scripts/seed_plans.py`
- `tests/shared/test_db.py`
- `tests/shared/test_event_bus.py`
- `tests/api/test_live_routes.py`

Apply the rewrite:

```bash
find src scripts tests -type f -name "*.py" -exec sed -i '' 's/from src\.shared\./from vision_shared./g' {} +
find src scripts tests -type f -name "*.py" -exec sed -i '' 's/import src\.shared/import vision_shared/g' {} +
```

Verify nothing else starts with `src.shared`:

```bash
grep -rn "src\.shared" src/ scripts/ tests/
```

Expected: no matches.

- [ ] **Step 4.6: Run the full test suite**

```bash
uv run pytest -q
```

Expected: same count of passes as the Task 3 baseline.

- [ ] **Step 4.7: Commit**

```bash
git add -A
git commit -m "refactor(monorepo): migrate src/shared -> vision_shared"
```

---

## Phase C — Migrate `intelligence` (empty, just placeholder)

### Task 5: Verify `intelligence` package stub + remove legacy `src/intelligence/`

**Files:**
- Delete: `src/intelligence/` (empty dir)

- [ ] **Step 5.1: Confirm `src/intelligence/` has no files**

```bash
find src/intelligence -type f
```

Expected: no output.

- [ ] **Step 5.2: Remove the empty directory**

```bash
rmdir src/intelligence 2>/dev/null || rm -rf src/intelligence
```

- [ ] **Step 5.3: Confirm `vision_intelligence` is importable**

```bash
uv run python -c "import vision_intelligence; print(vision_intelligence.__name__)"
```

Expected: `vision_intelligence`

- [ ] **Step 5.4: Commit**

```bash
git add -A
git commit -m "refactor(monorepo): remove empty src/intelligence, use vision_intelligence stub"
```

---

## Phase D — Migrate `live` (the big one)

### Task 6: Move `src/live/` sources and runtime assets into `vision_live`

**Files (sources):** 53 Python files — move all of `src/live/*.py`
**Files (assets):**
- Move `src/live/example_script.yaml` → `python-packages/live/src/vision_live/example_script.yaml`
- Move `src/live/data/product.yaml` → `python-packages/live/src/vision_live/data/product.yaml`
- Move `src/live/.gitkeep` (delete; no longer needed)

- [ ] **Step 6.1: List everything to be moved**

```bash
find src/live -maxdepth 2 -type f
```

Cross-check against expected count (~55 files including yaml + gitkeep).

- [ ] **Step 6.2: Move all `.py` files with `git mv` (one command per group to keep commits readable)**

```bash
mkdir -p python-packages/live/src/vision_live/data

# Move Python sources
for f in src/live/*.py; do
  name=$(basename "$f")
  if [ "$name" = "__init__.py" ]; then
    git rm "$f"
  else
    git mv "$f" "python-packages/live/src/vision_live/$name"
  fi
done

# Move yaml / runtime assets
git mv src/live/example_script.yaml python-packages/live/src/vision_live/example_script.yaml
git mv src/live/data/product.yaml python-packages/live/src/vision_live/data/product.yaml
git rm src/live/.gitkeep
rmdir src/live/data src/live 2>/dev/null || rm -rf src/live
```

Verify:

```bash
find python-packages/live/src/vision_live -type f | wc -l
```

Expected: ~55 (depending on exact count).

- [ ] **Step 6.3: Rewrite internal live imports**

All `from src.live.X` in live files become `from vision_live.X`. All `from src.shared.X` already became `from vision_shared.X` in Task 4.

```bash
find python-packages/live/src/vision_live -type f -name "*.py" \
  -exec sed -i '' 's/from src\.live\./from vision_live./g' {} +
find python-packages/live/src/vision_live -type f -name "*.py" \
  -exec sed -i '' 's/import src\.live/import vision_live/g' {} +
```

- [ ] **Step 6.4: Hunt down late-binding imports inside function bodies**

`src/live/session.py` has several `from src.live.X` and `from src.api.settings` inside methods (lines 243, 261, 279, 338, 374). The `src.live.X` ones are already covered by Step 6.3. The `from src.api.settings` one is handled in Task 8. For now, confirm:

```bash
grep -rn "from src\." python-packages/live/src/vision_live/
```

Expected matches should be **only** `from src.api.settings import get_settings` (remaining for Task 8). If you see `from src.live` anywhere, fix it with sed before continuing.

- [ ] **Step 6.5: Rewrite remaining callers in `src/api/` and `scripts/`**

```bash
find src/api scripts -type f -name "*.py" \
  -exec sed -i '' 's/from src\.live\./from vision_live./g' {} +
find src/api scripts -type f -name "*.py" \
  -exec sed -i '' 's/import src\.live/import vision_live/g' {} +

find tests -type f -name "*.py" \
  -exec sed -i '' 's/from src\.live\./from vision_live./g' {} +
```

Verify:

```bash
grep -rn "src\.live" src/ scripts/ tests/
```

Expected: no matches.

- [ ] **Step 6.6: Fix runtime paths in `src/api/settings.py`**

Edit `src/api/settings.py` lines 14-15:

```diff
-    default_script_path: str = "src/live/example_script.yaml"
-    default_product_path: str = "src/live/data/product.yaml"
+    default_script_path: str = "python-packages/live/src/vision_live/example_script.yaml"
+    default_product_path: str = "python-packages/live/src/vision_live/data/product.yaml"
```

> [!IMPORTANT]
> These defaults are filesystem paths, not Python imports. They must track where the YAML files actually live on disk after the move.

- [ ] **Step 6.7: Run live package tests**

```bash
uv run pytest python-packages/live -q
```

Expected: all live tests pass (same count as baseline minus any that live in `tests/`).

- [ ] **Step 6.8: Run the full test suite**

```bash
uv run pytest -q
```

Expected: same baseline (api tests may still import `src.api`, that's fine — fixed in Task 7).

- [ ] **Step 6.9: Commit**

```bash
git add -A
git commit -m "refactor(monorepo): migrate src/live -> vision_live incl. yaml assets"
```

---

## Phase E — Migrate `api` (depends on everything)

### Task 7: Move `src/api/` into `vision_api`

**Files:**
- Move `src/api/main.py` → `python-packages/api/src/vision_api/main.py`
- Move `src/api/settings.py` → `python-packages/api/src/vision_api/settings.py`
- Move `src/api/deps.py` → `python-packages/api/src/vision_api/deps.py`
- Delete `src/api/__init__.py`

- [ ] **Step 7.1: Move files**

```bash
git mv src/api/main.py python-packages/api/src/vision_api/main.py
git mv src/api/settings.py python-packages/api/src/vision_api/settings.py
git mv src/api/deps.py python-packages/api/src/vision_api/deps.py
git rm src/api/__init__.py
rmdir src/api 2>/dev/null || rm -rf src/api
```

- [ ] **Step 7.2: Rewrite internal api imports**

```bash
find python-packages/api/src/vision_api -type f -name "*.py" \
  -exec sed -i '' 's/from src\.api\./from vision_api./g' {} +
find python-packages/api/src/vision_api -type f -name "*.py" \
  -exec sed -i '' 's/import src\.api/import vision_api/g' {} +
```

- [ ] **Step 7.3: Rewrite remaining callers (live + scripts + tests)**

```bash
find python-packages scripts tests -type f -name "*.py" \
  -exec sed -i '' 's/from src\.api\./from vision_api./g' {} +
find python-packages scripts tests -type f -name "*.py" \
  -exec sed -i '' 's/import src\.api/import vision_api/g' {} +
```

Verify:

```bash
grep -rn "src\.api" python-packages/ scripts/ tests/
```

Expected: no matches.

- [ ] **Step 7.4: Confirm there are no remaining `from src.` imports anywhere**

```bash
grep -rn "from src\." python-packages/ scripts/ tests/
```

Expected: **zero matches**. If any show up, fix them before continuing.

- [ ] **Step 7.5: Add the `run()` entrypoint to `vision_api.main`**

Edit `python-packages/api/src/vision_api/main.py`. Append at the bottom:

```python
def run() -> None:
    """Console-script entry point: `uv run vision-api`."""
    import uvicorn

    uvicorn.run(
        "vision_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
```

- [ ] **Step 7.6: Re-sync to register the console script**

```bash
uv sync
```

Expected: uv reinstalls `vision-api` with the `vision-api` console entrypoint.

- [ ] **Step 7.7: Smoke-test FastAPI startup**

Start it in the background (terminal 1):

```bash
uv run vision-api
```

From terminal 2, call health:

```bash
curl -s http://127.0.0.1:8000/health
```

Expected: `{"status":"healthy"}`

Then kill the server (`Ctrl+C` in terminal 1).

- [ ] **Step 7.8: Full test suite**

```bash
uv run pytest -q
```

Expected: baseline count passes.

- [ ] **Step 7.9: Commit**

```bash
git add -A
git commit -m "refactor(monorepo): migrate src/api -> vision_api incl. run() entrypoint"
```

---

## Phase F — Clean up scripts and root `tests/`

### Task 8: Normalize `scripts/seed_plans.py`

**Files:**
- Modify: `scripts/seed_plans.py`

The old file uses `sys.path.insert(...)` to make `src` importable. With the workspace install, `vision_shared` is on `sys.path` by virtue of editable install — the hack is no longer needed.

- [ ] **Step 8.1: Remove the `sys.path` hack**

Edit `scripts/seed_plans.py`:

```diff
-import sys
-from pathlib import Path
-
-# Add project root to sys.path so src imports work.
-sys.path.insert(0, str(Path(__file__).parent.parent))
-
-from src.shared.db import Database  # noqa: E402
+from vision_shared.db import Database
```

(The `from src.shared.db import Database` should already have been rewritten in Task 4. This step is about removing the now-dead `sys.path` hack and the unused imports.)

- [ ] **Step 8.2: Run the seed script**

```bash
uv run python scripts/seed_plans.py --db /tmp/vision_seed_test.db
```

Expected output (first run): `[ok]   Created plan: '示例方案 · 垆土铁棍山药粉'  id=<integer>`

Clean up:

```bash
rm /tmp/vision_seed_test.db
```

- [ ] **Step 8.3: Commit**

```bash
git add scripts/seed_plans.py
git commit -m "refactor(monorepo): drop sys.path hack from scripts/seed_plans.py"
```

### Task 9: Relocate root `tests/` into the appropriate package

**Files:**
- Move `tests/shared/test_db.py` → `python-packages/shared/src/vision_shared/db_test.py`
- Move `tests/shared/test_event_bus.py` → `python-packages/shared/src/vision_shared/event_bus_test.py`
- Move `tests/api/test_live_routes.py` → `python-packages/api/src/vision_api/live_routes_test.py`
- Delete: `tests/` (the whole directory, including `__init__.py` files)

- [ ] **Step 9.1: Move test files and rename to `*_test.py` convention**

```bash
git mv tests/shared/test_db.py python-packages/shared/src/vision_shared/db_test.py
git mv tests/shared/test_event_bus.py python-packages/shared/src/vision_shared/event_bus_test.py
git mv tests/api/test_live_routes.py python-packages/api/src/vision_api/live_routes_test.py
```

- [ ] **Step 9.2: Verify imports inside the moved tests**

```bash
grep -n "^from " python-packages/shared/src/vision_shared/db_test.py \
                   python-packages/shared/src/vision_shared/event_bus_test.py \
                   python-packages/api/src/vision_api/live_routes_test.py
```

Expected: every `from vision_*` import resolves; no `src.*` left. If something still says `src.`, rewrite manually.

- [ ] **Step 9.3: Remove the old `tests/` tree**

```bash
git rm -r tests/
```

- [ ] **Step 9.4: Run package-scoped tests**

```bash
uv run pytest python-packages/shared -q
uv run pytest python-packages/api -q
```

Expected: pass.

- [ ] **Step 9.5: Commit**

```bash
git add -A
git commit -m "refactor(monorepo): relocate root tests/ into colocated *_test.py files"
```

---

## Phase G — Final sweep and root cleanup

### Task 10: Remove empty `src/` tree

**Files:**
- Delete: `src/` (now fully empty)

- [ ] **Step 10.1: Confirm `src/` has no tracked files**

```bash
git ls-files src/
find src -type f 2>/dev/null
```

Expected: both commands produce no output. If either shows a file, move or delete it first.

- [ ] **Step 10.2: Remove `src/` directory**

```bash
rm -rf src/
```

- [ ] **Step 10.3: Full test suite + FastAPI smoke**

```bash
uv run pytest -q
uv run vision-api &
SERVER_PID=$!
sleep 3
curl -s http://127.0.0.1:8000/health
kill $SERVER_PID
```

Expected: tests green; curl prints `{"status":"healthy"}`.

- [ ] **Step 10.4: Commit**

```bash
git add -A
git commit -m "refactor(monorepo): remove empty src/ tree"
```

### Task 11: Narrow pytest testpaths now that migration is complete

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 11.1: Edit `[tool.pytest.ini_options]`**

Before:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["src", "tests", "python-packages"]
python_files = ["*_test.py", "test_*.py"]
markers = [
    "slow: tests that download models / run real embeddings",
]
```

After:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["python-packages"]
python_files = ["*_test.py"]
markers = [
    "slow: tests that download models / run real embeddings",
]
```

Changes: drop `pythonpath = ["."]`, `src`/`tests` from testpaths, `test_*.py` from `python_files`.

- [ ] **Step 11.2: Run the full test suite**

```bash
uv run pytest -q
```

Expected: same test count as baseline; none were living outside `python-packages` at this point.

- [ ] **Step 11.3: Commit**

```bash
git add pyproject.toml
git commit -m "chore(monorepo): narrow pytest testpaths to python-packages"
```

### Task 12: Drop root runtime dependencies, replace with `vision-api`

**Files:**
- Modify: `pyproject.toml`

This is the end state from the spec: root depends only on `vision-api`, which transitively pulls in everything else.

- [ ] **Step 12.1: Edit root `pyproject.toml` dependencies block**

Replace the entire `dependencies = [...]` block with:

```toml
dependencies = [
    "vision-api",
]
```

- [ ] **Step 12.2: Re-sync**

```bash
uv sync
```

Expected: uv resolves the graph; all transitively-required packages install; console script `vision-api` still works.

- [ ] **Step 12.3: Full test suite + FastAPI smoke**

```bash
uv run pytest -q
uv run vision-api &
SERVER_PID=$!
sleep 3
curl -s http://127.0.0.1:8000/health
kill $SERVER_PID
```

Expected: tests green; curl prints `{"status":"healthy"}`.

- [ ] **Step 12.4: Verify `uv.lock` diff looks sane**

```bash
git diff uv.lock | head -80
```

Expected: lockfile changes mention the 4 workspace members and removal of duplicate top-level entries. No unexpected dependency version jumps.

- [ ] **Step 12.5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(monorepo): root depends only on vision-api"
```

### Task 13: Manual live-streaming / RAG smoke test (human verification)

**Files:** None (manual verification)

Because this migration is a refactor, automated tests are the primary gate. But the `live` module has heavyweight integrations (LiteLLM, chromadb, Playwright) whose behavior is hard to cover in unit tests. Do a brief manual pass.

- [ ] **Step 13.1: Start the API**

```bash
uv run vision-api
```

- [ ] **Step 13.2: Verify core endpoints respond (separate terminal)**

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/plans | head -c 500
curl -s http://127.0.0.1:8000/live/sessions | head -c 500
```

Expected: each returns JSON without 5xx errors. Empty lists are acceptable if DB is empty.

- [ ] **Step 13.3: Start the web UI and browse to `/plans`**

In another terminal:

```bash
cd apps/web
pnpm dev
```

Open `http://localhost:3000/plans` in a browser. Expected: list renders without console errors. Drill into a plan if data exists; RAG panel loads.

- [ ] **Step 13.4: Stop both processes**

`Ctrl+C` on both terminals.

- [ ] **Step 13.5: Commit nothing (smoke test has no file changes)**

If you found issues, create follow-up commits with fixes. If everything works, proceed to Task 14.

### Task 14: Open the PR

**Files:** None (GitHub only)

- [ ] **Step 14.1: Push the branch**

```bash
git push -u origin refactor/python-monorepo
```

- [ ] **Step 14.2: Create the PR**

```bash
gh pr create --title "refactor: convert Python codebase to uv workspace monorepo" --body "$(cat <<'EOF'
## Summary

Converts the Python side of Vision from a single `pyproject.toml` to a uv workspace monorepo with 4 packages: `vision-shared`, `vision-intelligence`, `vision-live`, `vision-api`.

No runtime behavior changes. Enables future modules (ASR pipeline, topic monitoring, competitor scraping) to declare their own heavyweight dependencies without polluting the `live` environment.

Design spec: `docs/superpowers/specs/2026-04-18-python-monorepo-migration-design.md`
Implementation plan: `docs/superpowers/plans/2026-04-18-python-monorepo-migration.md`

## Test plan

- [x] `uv sync` resolves the workspace
- [x] `uv run pytest -q` matches pre-migration baseline count
- [x] `uv run vision-api` starts FastAPI; `/health` returns 200
- [x] `curl /plans` and `curl /live/sessions` return without 5xx
- [x] `apps/web` at `localhost:3000/plans` renders and RAG panel loads
- [x] `scripts/seed_plans.py` runs with a throwaway DB
EOF
)"
```

Expected: PR opens; link is printed.

---

## Self-Review Notes (from plan author)

- Spec coverage: each spec section maps to tasks — Section 3 layout (Tasks 1, 4-7, 10), Section 4 pyprojects (Tasks 2, 3, 12), Section 5 import rewrites (Tasks 4-8), Section 6 test relocation (Task 9), Section 7 risks covered by smoke tests (Tasks 7.7, 10.3, 12.3, 13), Section 8 execution ordering matches.
- Key deltas from spec uncovered during drafting:
  - Test files are already `*_test.py` in the codebase, not `*.test.py`. The spec was aligned to reality in the 2nd spec commit; this plan reflects that.
  - `src/api/settings.py` has two filesystem-path defaults (`default_script_path`, `default_product_path`) pointing into `src/live/`. These must be updated (Step 6.6) when the YAML files move.
  - `scripts/seed_plans.py` uses a `sys.path.insert` hack that becomes dead code after workspace install (Task 8).
  - `src/live/session.py` has function-local imports (delayed imports for circular-dep avoidance) on lines 243, 261, 279, 338, 374-376. The sed rewrites cover all of them since they share the `from src.live.` and `from src.api.` prefixes.
- Type/naming consistency: `vision_shared`, `vision_intelligence`, `vision_live`, `vision_api` appear consistently. Console script is `vision-api` (hyphen) but the module it launches is `vision_api` (underscore) — this is correct Python console-script convention.
