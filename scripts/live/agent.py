#!/usr/bin/env python3
"""
agent.py — Live orchestration agent entry point.

Usage (dev mode with mock events and system TTS):
    uv run scripts/live/agent.py --script scripts/live/example_script.yaml --mock

Usage (production, requires GCP credentials):
    export GOOGLE_CLOUD_PROJECT=your-project-id
    uv run scripts/live/agent.py --script scripts/live/example_script.yaml
"""
from __future__ import annotations

import argparse
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

# Mock events for development
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


def build_mock_llm():
    """Return a simple mock LLM that echoes back a canned response."""
    from scripts.live.schema import Decision

    class MockLLM:
        def decide(self, script_state, events):
            questions = [e for e in events if e.text and "？" in e.text]
            if questions:
                return Decision(
                    action="respond",
                    content=f"感谢{questions[0].user}的提问！购买链接在直播间左下角～",
                    reason="mock: contains question",
                )
            return Decision(action="skip", reason="mock: no question")

    return MockLLM()


def main() -> None:
    parser = argparse.ArgumentParser(description="Live orchestration agent")
    parser.add_argument("--script", default="scripts/live/example_script.yaml", help="Path to YAML script")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM and mock TTS (dev mode)")
    parser.add_argument("--speed", type=float, default=1.0, help="Mock event replay speed multiplier")
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"), help="GCP project ID")
    args = parser.parse_args()

    from scripts.live.event_collector import MockEventCollector
    from scripts.live.orchestrator import Orchestrator
    from scripts.live.script_runner import ScriptRunner
    from scripts.live.tts_player import TTSPlayer

    # Queues
    event_queue: queue.Queue = queue.Queue()
    tts_queue: queue.Queue[str] = queue.Queue()

    # LLM client
    if args.mock:
        llm = build_mock_llm()
        logger.info("Running in MOCK mode (no Vertex AI calls)")
    else:
        if not args.project:
            logger.error("--project or GOOGLE_CLOUD_PROJECT required in production mode")
            sys.exit(1)
        from scripts.live.llm_client import LLMClient
        llm = LLMClient(project=args.project)

    # TTS speak function
    if args.mock:
        def speak_fn(text: str, speech_prompt: str | None = None) -> None:
            logger.info("[TTS MOCK] %s (prompt=%s)", text, speech_prompt)
            time.sleep(0.3)   # simulate short playback
    else:
        speak_fn = None   # uses macOS `say` by default

    # Wire components
    script_runner = ScriptRunner.from_yaml(args.script)
    event_collector = MockEventCollector(_MOCK_EVENTS, event_queue, speed=args.speed)
    tts_player = TTSPlayer(tts_queue, speak_fn=speak_fn)
    orchestrator = Orchestrator(tts_queue=tts_queue, llm_client=llm, llm_batch_size=5, llm_interval=10.0)

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
    logger.info("Agent running. Ctrl+C to stop.")

    # Main loop: drain event queue and tick orchestrator
    while not stop_event.is_set():
        script_state = script_runner.get_state()
        if script_state.get("finished"):
            logger.info("Script finished.")
            break

        # Drain all pending events
        while True:
            try:
                event = event_queue.get_nowait()
                orchestrator.handle_event(event, script_state)
            except queue.Empty:
                break

        # Time-based LLM flush
        orchestrator.tick(script_state)
        stop_event.wait(timeout=0.5)

    # Teardown
    event_collector.stop()
    script_runner.stop()
    tts_player.stop()
    logger.info("Agent stopped.")


if __name__ == "__main__":
    main()
