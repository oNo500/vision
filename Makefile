.PHONY: install dev api web test lint format help

SHELL = cmd

# ── Install ────────────────────────────────────────────────────────────────────

install:
	uv sync
	pnpm install

# ── Dev ────────────────────────────────────────────────────────────────────────

api:
	start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\temp\chrome-cdp"
	uv run uvicorn vision_api.main:app --host 127.0.0.1 --port 8090

web:
	start "Vision Web" cmd /k "cd /d %CD% && pnpm --filter web dev"
	timeout /t 4 /nobreak >nul
	start "" "http://localhost:3000"

dev: api web

# ── Test ───────────────────────────────────────────────────────────────────────

test:
	uv run pytest python-packages/ -v

test-watch:
	uv run pytest python-packages/ -v --tb=short -f

# ── Lint & Format ──────────────────────────────────────────────────────────────

lint:
	uv run ruff check python-packages/
	pnpm --filter web lint

format:
	uv run ruff format python-packages/
	pnpm --filter web format

# ── Video ASR ──────────────────────────────────────────────────────────────────

asr:
	uv run vision-video-asr run --sources config/video_asr/sources.yaml

# ── Help ───────────────────────────────────────────────────────────────────────

help:
	@echo.
	@echo Usage: make ^<target^>
	@echo.
	@echo   install      Install Python + Node dependencies
	@echo   api          Launch Chrome (CDP:9222) + FastAPI backend (localhost:8090)
	@echo   web          Start Next.js frontend in new window + open browser
	@echo   test         Run Python tests
	@echo   test-watch   Run Python tests in watch mode
	@echo   lint         Lint Python + frontend
	@echo   format       Format Python + frontend
	@echo.
