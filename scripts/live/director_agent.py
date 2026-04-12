"""DirectorAgent — proactive LLM loop that drives continuous TTS output.

The director fires whenever the TTS queue is idle, or at most every
MAX_SILENCE_SECONDS seconds. It collects full context (script state,
product knowledge, recent events) and asks Gemini to produce the next
utterance, optionally improving on the script text.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time

from scripts.live.schema import DirectorOutput, Event

logger = logging.getLogger(__name__)

MAX_SILENCE_SECONDS = 15.0   # force output if TTS has been idle this long

_SYSTEM_PROMPT = """\
你是一个经验丰富的带货主播，正在进行抖音直播。
你的任务是：根据当前直播脚本段落、产品知识和观众互动，决定下一句要说什么。

规则：
- 优先回应观众互动（问题、礼物、热情弹幕），但不能忽视脚本进度
- 改写脚本内容，让它听起来更自然、口语化，而不是照本宣科
- 如果脚本段落标记了 must_say=true，必须基于脚本原文，不可大幅偏离
- 每次只说一句话，不超过 30 字
- 禁用词不得出现在输出中
- speech_prompt 描述朗读时的情绪、语速和语气（一句话，要具体）

返回严格的 JSON，格式：
{
  "content": "下一句台词（不超过30字）",
  "speech_prompt": "朗读风格描述",
  "source": "script" | "interaction" | "knowledge",
  "reason": "决策理由（简短）"
}
不要输出 JSON 以外的任何内容。
"""


def build_director_prompt(
    script_state: dict,
    knowledge_ctx: str,
    recent_events: list[Event],
    last_said: str,
) -> str:
    """Build the user-turn prompt for the director LLM call."""
    event_lines = "\n".join(
        f"  - [{e.type}] {e.user}: {e.text or e.gift or '(进场)'}"
        for e in recent_events[-10:]   # cap at 10 most recent
    ) or "  （暂无互动）"

    must_say = script_state.get("must_say", False)
    return (
        f"=== 产品知识 ===\n{knowledge_ctx}\n\n"
        f"=== 当前脚本段落 ===\n"
        f"段落ID：{script_state.get('segment_id', 'unknown')}\n"
        f"参考原文：{script_state.get('segment_text', '').strip()}\n"
        f"关键词：{', '.join(script_state.get('keywords', []))}\n"
        f"剩余时间：{script_state.get('remaining_seconds', 0):.0f}s\n"
        f"必须贴近原文：{'是' if must_say else '否'}\n\n"
        f"=== 最近观众互动 ===\n{event_lines}\n\n"
        f"=== 上一句说的 ===\n{last_said or '（开场，还没说过话）'}\n\n"
        f"请决定下一句说什么。"
    )


def parse_director_response(raw: str) -> DirectorOutput:
    """Parse LLM JSON output into a DirectorOutput. Returns a fallback on error."""
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        data = json.loads(text)
        return DirectorOutput(
            content=data["content"],
            speech_prompt=data.get("speech_prompt", "自然平稳地说"),
            source=data.get("source", "script"),
            reason=data.get("reason", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Director parse error: %s | raw=%s", e, raw[:200])
        return DirectorOutput(content="", speech_prompt="", source="script", reason=f"parse error: {e}")
