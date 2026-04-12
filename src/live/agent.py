#!/usr/bin/env python3
"""
agent.py — Live orchestration agent entry point.

Usage (dev mode, mock LLM + mock TTS):
    uv run src/live/agent.py --mock

Usage (real Douyin events via CDP + mock LLM):
    uv run src/live/agent.py --mock --cdp-url http://localhost:9222

Usage (production, requires GCP credentials):
    export GOOGLE_CLOUD_PROJECT=your-project-id
    uv run src/live/agent.py --script src/live/example_script.yaml
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import signal
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="[%H:%M:%S]",
)
logger = logging.getLogger(__name__)

_MOCK_EVENTS = [
    {"type": "enter",   "user": "用户A", "is_follower": True,  "t": 5},
    {"type": "danmaku", "user": "用户B", "text": "这个怎么买？",    "t": 30},
    {"type": "gift",    "user": "用户C", "gift": "小心心", "value": 1,    "t": 60},
    {"type": "danmaku", "user": "用户D", "text": "主播加油！",     "t": 75},
    {"type": "gift",    "user": "用户E", "gift": "火箭",    "value": 500,  "t": 90},
    {"type": "danmaku", "user": "用户F", "text": "有没有优惠？",    "t": 100},
    {"type": "danmaku", "user": "用户G", "text": "666",            "t": 101},
    {"type": "danmaku", "user": "用户H", "text": "哪里能买到？",   "t": 102},
    {"type": "danmaku", "user": "用户I", "text": "好棒！",         "t": 103},
    {"type": "danmaku", "user": "用户J", "text": "继续！",         "t": 104},
]

_DEFAULT_PRODUCT_YAML = "src/live/data/product.yaml"
_DEFAULT_SCRIPT_YAML = "src/live/example_script.yaml"


def _make_vertex_llm_generate_fn(project: str, location: str = "us-central1", model: str = "gemini-2.5-flash"):
    """Return a generate_fn(prompt) -> str backed by Vertex AI."""
    import vertexai
    from vertexai.generative_models import GenerativeModel
    from src.live.director_agent import _SYSTEM_PROMPT

    vertexai.init(project=project, location=location)
    m = GenerativeModel(model_name=model, system_instruction=_SYSTEM_PROMPT)

    def _generate(prompt: str) -> str:
        response = m.generate_content(prompt)
        return response.text

    return _generate


def _make_mock_llm_generate_fn():
    """Return a simple mock generate_fn for dev mode."""
    def _generate(prompt: str) -> str:
        if "怎么买" in prompt or "哪里" in prompt or "优惠" in prompt:
            content = "点左下角购物车就能下单，今天直播间专属价九十九！"
            source = "interaction"
        else:
            content = "大家好，今天给大家带来一款超好用的面膜，感兴趣的扣1！"
            source = "script"
        return json.dumps({
            "content": content,
            "speech_prompt": "热情自然地介绍，语速稍快，像朋友聊天",
            "source": source,
            "reason": "mock",
        }, ensure_ascii=False)

    return _generate


def main() -> None:
    parser = argparse.ArgumentParser(description="Live orchestration agent")
    parser.add_argument("--script", default=_DEFAULT_SCRIPT_YAML, help="Path to YAML script")
    parser.add_argument("--product", default=_DEFAULT_PRODUCT_YAML, help="Path to product knowledge YAML")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM and mock TTS (dev mode)")
    parser.add_argument("--cdp-url", default=None, metavar="URL",
                        help="Chrome DevTools Protocol URL, e.g. http://localhost:9222. "
                             "When set, uses CdpEventCollector for real Douyin events. "
                             "Omit to use mock event replay.")
    parser.add_argument("--speed", type=float, default=1.0, help="Mock event replay speed multiplier")
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"), help="GCP project ID")
    parser.add_argument("--audio-device", default=None, metavar="DEVICE",
                        help="Output audio device name substring for OBS/streaming, e.g. 'CABLE Input' (VB-Cable). "
                             "Omit to use the system default speaker (local dev)")
    args = parser.parse_args()

    from src.live.cdp_collector import CdpEventCollector
    from src.live.director_agent import DirectorAgent
    from src.live.event_collector import MockEventCollector
    from src.live.knowledge_base import KnowledgeBase
    from src.live.orchestrator import Orchestrator
    from src.live.script_runner import ScriptRunner
    from src.live.tts_player import TTSPlayer

    # Queues
    event_queue: queue.Queue = queue.Queue()
    tts_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()

    # LLM generate function
    if args.mock:
        llm_generate = _make_mock_llm_generate_fn()
        logger.info("Running in MOCK mode (no Vertex AI calls)")
    else:
        if not args.project:
            logger.error("--project or GOOGLE_CLOUD_PROJECT required in production mode")
            sys.exit(1)
        llm_generate = _make_vertex_llm_generate_fn(args.project)

    # TTS speak function
    if args.mock:
        def speak_fn(text: str, speech_prompt: str | None = None) -> None:
            logger.info("[TTS MOCK] (%s) %s", speech_prompt or "default", text)
            time.sleep(0.5)
    else:
        speak_fn = None   # uses Gemini TTS via GOOGLE_CLOUD_PROJECT env var

    # Knowledge base
    kb = KnowledgeBase(args.product)
    logger.info("KnowledgeBase loaded: %s", kb.product_name)

    # Wire components
    script_runner = ScriptRunner.from_yaml(args.script)
    if args.cdp_url:
        event_collector = CdpEventCollector(out_queue=event_queue, cdp_url=args.cdp_url)
        logger.info("Using CdpEventCollector (cdp=%s)", args.cdp_url)
    else:
        event_collector = MockEventCollector(_MOCK_EVENTS, event_queue, speed=args.speed)
    tts_player = TTSPlayer(tts_queue, speak_fn=speak_fn, audio_device=args.audio_device)
    orchestrator = Orchestrator(tts_queue=tts_queue)
    director = DirectorAgent(
        tts_queue=tts_queue,
        tts_player=tts_player,
        knowledge_ctx=kb.context_for_prompt(),
        llm_generate_fn=llm_generate,
    )

    # Graceful shutdown
    stop_event = threading.Event()

    def handle_signal(sig, frame):
        logger.info("Shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Start threads
    script_runner.start()
    event_collector.start()
    tts_player.start()
    director.start(
        get_state_fn=script_runner.get_state,
        get_events_fn=orchestrator.get_events,
    )
    logger.info("Agent running. Ctrl+C to stop.")

    # Main loop: drain event queue into orchestrator
    while not stop_event.is_set():
        script_state = script_runner.get_state()
        if script_state.get("finished"):
            logger.info("Script finished.")
            break

        while True:
            try:
                event = event_queue.get_nowait()
                orchestrator.handle_event(event, script_state)
            except queue.Empty:
                break

        stop_event.wait(timeout=0.5)

    # Teardown
    director.stop()
    event_collector.stop()
    script_runner.stop()
    tts_player.stop()
    logger.info("Agent stopped.")


if __name__ == "__main__":
    main()
