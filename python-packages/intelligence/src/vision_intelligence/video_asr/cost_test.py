from vision_intelligence.video_asr.cost import estimate_cost_usd


def test_flash_audio_pricing():
    # 100k input (audio) + 10k output
    c = estimate_cost_usd(model="gemini-2.5-flash",
                          input_tokens=100_000, output_tokens=10_000)
    # 100k * 0.30/1M + 10k * 2.50/1M = 0.03 + 0.025 = 0.055
    assert round(c, 4) == 0.055


def test_unknown_model_returns_zero():
    assert estimate_cost_usd(model="unknown", input_tokens=1, output_tokens=1) == 0.0
