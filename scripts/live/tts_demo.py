#!/usr/bin/env python3
"""TTS demo: play 10 hardcoded lines back-to-back to test latency/continuity."""
from __future__ import annotations

import queue
import time
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="[%H:%M:%S]")

LINES = [
    "哈喽各位宝宝们，晚上好！欢迎来到我的直播间！",
    "今天给大家带来一款超级好用的面膜，先点个关注不迷路！",
    "这款超能面膜，纯植物萃取，敏感肌也能放心用！",
    "现在直播间专属价只要九十九，原价一百九十九！",
    "买二还送一，今天下单真的超划算！",
    "已经有超过十万套卖出去了，口碑超级好！",
    "敷完当天就能感觉皮肤水润，持续用二十八天有明显改善！",
    "不管是油皮干皮还是敏感肌，都测试过不刺激！",
    "七天无理由退换，买了不满意直接退！",
    "心动的宝宝们赶紧点左下角购物车，数量有限！",
]

def main():
    from scripts.live.tts_player import TTSPlayer

    tts_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
    player = TTSPlayer(tts_queue)
    player.start()

    speech_prompt = "带货主播热情介绍产品，语速适中，自然有感情，像在跟朋友聊天"

    for i, line in enumerate(LINES):
        logging.getLogger().info("[DEMO] Queuing line %d: %s", i + 1, line)
        tts_queue.put((line, speech_prompt))

    logging.getLogger().info("All 10 lines queued, waiting for playback to finish...")
    tts_queue.join()
    logging.getLogger().info("Done.")
    player.stop()

if __name__ == "__main__":
    main()
