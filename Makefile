.PHONY: install install-py
.PHONY: test lint format
.PHONY: help

# ── Install ────────────────────────────────────────────────────────────────────

install: install-py

install-py:
	uv sync

# ── Test ───────────────────────────────────────────────────────────────────────

test:
	uv run pytest

# ── Lint & Format ──────────────────────────────────────────────────────────────

lint:
	uv run ruff check vision/ scripts/

format:
	uv run ruff format vision/ scripts/

# ── Help ───────────────────────────────────────────────────────────────────────

help:
	@echo "Available commands:"
	@echo "  make install    Install all dependencies"
	@echo "  make test       Run tests"
	@echo "  make lint       Run linter"
	@echo "  make format     Format code"
