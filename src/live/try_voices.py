#!/usr/bin/env python3
"""
try_voices.py — 批量试听 Gemini TTS 声音

用法:
    uv run scripts/live/try_voices.py
    uv run scripts/live/try_voices.py --text "感谢大家的支持！"
    uv run scripts/live/try_voices.py --voices Kore Zephyr Puck
"""
from __future__ import annotations

import argparse
import os
import tempfile
import wave

from dotenv import load_dotenv

load_dotenv()

# 带货场景试听文本
DEFAULT_TEXT = "哇，这个产品真的超级好用！买到就是赚到，姐妹们抓紧下单，数量有限哦！"

# 推荐先试的声音（女声优先，适合带货）
DEFAULT_VOICES = [
    "Kore",
    "Zephyr",
    "Aoede",
    "Leda",
    "Sulafat",
    "Puck",
    "Charon",
]


def speak(client, voice: str, text: str) -> None:
    from google.genai import types

    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    audio_data = response.candidates[0].content.parts[0].inline_data.data

    import subprocess
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    with wave.open(tmp_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(audio_data)
    subprocess.run(["afplay", tmp_path], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="批量试听 Gemini TTS 声音")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="试听文本")
    parser.add_argument("--voices", nargs="+", default=DEFAULT_VOICES, help="声音列表")
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    args = parser.parse_args()

    if not args.project:
        print("请设置 GOOGLE_CLOUD_PROJECT 或在 .env 中配置")
        raise SystemExit(1)

    from google import genai
    client = genai.Client(vertexai=True, project=args.project, location="us-central1")

    print(f'试听文本："{args.text}"\n')

    for voice in args.voices:
        print(f"▶ 播放 {voice}...")
        try:
            speak(client, voice, args.text)
            print(f"  ✓ {voice} 播放完成\n")
        except Exception as e:
            print(f"  ✗ {voice} 失败: {e}\n")

    print("试听完成！用 --voices <名字> 单独重听某个声音。")


if __name__ == "__main__":
    main()
