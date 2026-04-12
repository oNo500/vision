.PHONY: install dev api web test lint format help

# ── Install ────────────────────────────────────────────────────────────────────

install:
	uv sync
	pnpm install

# ── Dev ────────────────────────────────────────────────────────────────────────

dev: api web

api:
	open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-cdp || true
	uv run uvicorn src.api.main:app --reload --port 8000

web:
	pnpm --filter web dev

# ── Test ───────────────────────────────────────────────────────────────────────

test:
	uv run pytest tests/ -v

test-watch:
	uv run pytest tests/ -v --tb=short -f

# ── Lint & Format ──────────────────────────────────────────────────────────────

lint:
	uv run ruff check src/
	pnpm --filter web lint

format:
	uv run ruff format src/
	pnpm --filter web format

# ── Help ───────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "  install      Install Python + Node dependencies"
	@echo "  api          Start Chrome (port 9222) + FastAPI backend (localhost:8000)"
	@echo "  web          Start Next.js frontend (localhost:3000)"
	@echo "  test         Run Python tests"
	@echo "  test-watch   Run Python tests in watch mode"
	@echo "  lint         Lint Python + frontend"
	@echo "  format       Format Python + frontend"
	@echo ""
