.PHONY: install lint format help

# ── Install ────────────────────────────────────────────────────────────────────

install:
	uv sync

# ── Lint & Format ──────────────────────────────────────────────────────────────

lint:
	uv run ruff check scripts/

format:
	uv run ruff format scripts/

# ── Help ───────────────────────────────────────────────────────────────────────

help:
	@echo "Available commands:"
	@echo "  make install    Install dependencies"
	@echo "  make lint       Run linter"
	@echo "  make format     Format code"
