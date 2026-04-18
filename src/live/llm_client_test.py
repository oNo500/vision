"""Tests for LLMClient (LiteLLM-based)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.live.llm_client import LLMClient


def _fake_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_generate_returns_content(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "src.live.llm_client.completion",
        lambda **_: _fake_response('{"ok": true}'),
    )
    client = LLMClient(model="vertex_ai/gemini-2.5-flash", project="p")
    assert client.generate("hello") == '{"ok": true}'


def test_generate_passes_vercel_gateway_config(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response("")

    monkeypatch.setattr("src.live.llm_client.completion", fake_completion)
    client = LLMClient(
        model="vercel/gemini-2.5-flash",
        api_base="https://gateway.ai.vercel.com/v1/x",
        api_key="vtoken",
    )
    client.generate("hi", system="you are a bot")

    assert captured["model"] == "vercel/gemini-2.5-flash"
    assert captured["api_base"] == "https://gateway.ai.vercel.com/v1/x"
    assert captured["api_key"] == "vtoken"
    assert captured["messages"][0] == {"role": "system", "content": "you are a bot"}
    assert captured["messages"][1] == {"role": "user", "content": "hi"}


def test_generate_passes_vertex_project(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}
    monkeypatch.setattr(
        "src.live.llm_client.completion",
        lambda **kw: captured.update(kw) or _fake_response(""),
    )
    client = LLMClient(model="vertex_ai/gemini-2.5-flash", project="my-proj")
    client.generate("x")

    assert captured["vertex_project"] == "my-proj"
    assert captured["vertex_location"] == "us-central1"


def test_generate_without_system_has_single_user_message(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}
    monkeypatch.setattr(
        "src.live.llm_client.completion",
        lambda **kw: captured.update(kw) or _fake_response(""),
    )
    client = LLMClient(model="openai/gpt-4o", api_key="k")
    client.generate("hi")
    assert captured["messages"] == [{"role": "user", "content": "hi"}]


def test_generate_omits_absent_kwargs(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}
    monkeypatch.setattr(
        "src.live.llm_client.completion",
        lambda **kw: captured.update(kw) or _fake_response(""),
    )
    client = LLMClient(model="openai/gpt-4o")   # no api_base, no api_key, no project
    client.generate("hi")

    assert "api_base" not in captured
    assert "api_key" not in captured
    assert "vertex_project" not in captured
