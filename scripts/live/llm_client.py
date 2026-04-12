"""LLMClient — calls Vertex AI Gemini and returns a Decision.

Prompt building and JSON parsing are pure functions, making them easy to unit test
without any network calls.
"""
from __future__ import annotations

import json
import logging

from scripts.live.schema import Decision, Event

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一个直播控场助手，负责决定是否回应观众互动，并为 TTS 提供朗读风格指引。

规则：
- 保持主播的热情、亲切风格，像跟朋友聊天
- 不得提及竞品或负面信息
- 回复简短，不超过20字
- 人设约束：[待填充]
- 禁用词：[待填充]

speech_prompt 填写方式：用一句话描述朗读时的情绪、语速和语气，要具体到场景。
例如：
- "收到大额礼物时真情流露的惊喜，语气先快后慢，情绪有起伏"
- "轻快热情地迎接新观众，像见到老朋友，语速稍快"
- "紧迫真诚地催单，语速偏快像跟闺蜜说悄悄话"
- "耐心温和回答问题，语速适中像朋友聊天"

请根据当前直播状态和待处理互动，返回严格的 JSON，格式：
{
  "action": "respond" | "defer" | "skip",
  "content": "回复文案（仅 action=respond 时填写，不超过20字）",
  "speech_prompt": "朗读风格描述（仅 action=respond 时填写）",
  "interrupt_script": false,
  "reason": "决策理由"
}
不要输出 JSON 以外的任何内容。
"""


def build_prompt(script_state: dict, events: list[Event]) -> str:
    """Build the user-turn prompt for Gemini from script state and buffered events."""
    event_lines = "\n".join(
        f"- [{e.type}] {e.user}: {e.text or e.gift or '(进场)'}"
        for e in events
    )
    interruptible = script_state.get("interruptible", True)
    return (
        f"当前脚本段落：{script_state.get('segment_id', 'unknown')}"
        f"（关键词：{', '.join(script_state.get('keywords', []))}）\n"
        f"段落剩余时间：{script_state.get('remaining_seconds', 0):.0f}s\n"
        f"当前段落可打断：{'是' if interruptible else '否'}\n"
        f"\n待处理互动（共 {len(events)} 条）：\n{event_lines}\n"
        f"\n请决定如何处理。"
    )


class LLMClient:
    """Wraps Vertex AI Gemini for live orchestration decisions."""

    def __init__(self, project: str, location: str = "us-central1", model: str = "gemini-2.5-flash") -> None:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=project, location=location)
        self._model = GenerativeModel(
            model_name=model,
            system_instruction=_SYSTEM_PROMPT,
        )
        logger.info("LLMClient initialized (model=%s)", model)

    def decide(self, script_state: dict, events: list[Event]) -> Decision:
        """Call Gemini and return a structured Decision."""
        prompt = build_prompt(script_state, events)
        try:
            response = self._model.generate_content(prompt)
            return self.parse_response(response.text)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return Decision(action="skip", reason=f"llm error: {e}")

    @staticmethod
    def parse_response(raw: str) -> Decision:
        """Parse Gemini JSON output into a Decision. Returns skip on any parse error."""
        try:
            # Strip markdown code fences if present
            text = raw.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:-1])
            data = json.loads(text)
            return Decision(
                action=data.get("action", "skip"),
                content=data.get("content"),
                speech_prompt=data.get("speech_prompt"),
                interrupt_script=data.get("interrupt_script", False),
                reason=data.get("reason", ""),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("LLM parse error: %s | raw=%s", e, raw[:200])
            return Decision(action="skip", reason=f"parse error: {e}")
