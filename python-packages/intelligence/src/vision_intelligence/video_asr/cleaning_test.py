from vision_intelligence.video_asr.cleaning import (
    normalize_punctuation, traditional_to_simplified, jieba_tokenize,
)


def test_normalize_punctuation_halfwidth_to_fullwidth():
    s = "你好,今天怎么样?"
    assert normalize_punctuation(s) == "你好，今天怎么样？"


def test_normalize_punctuation_keeps_english_words():
    s = "AI is great. iPhone 15, true?"
    # English words with punctuation inside tokens remain halfwidth;
    # only sentence-delimiter punctuation right after Chinese chars converts
    out = normalize_punctuation(s)
    # No aggressive conversion inside English:
    assert "iPhone 15" in out
    # Sentence-final punctuation after English may stay halfwidth (acceptable)
    # but after CJK char it must convert:
    s2 = "家人们好,这个产品.真不错!"
    assert normalize_punctuation(s2) == "家人们好，这个产品。真不错！"


def test_traditional_to_simplified():
    assert traditional_to_simplified("個體實體") == "个体实体"


def test_jieba_tokenize_chinese():
    out = jieba_tokenize("家人们晚上好")
    # Must produce a space-separated string
    assert " " in out
    assert "家人们" in out.split() or "晚上" in out.split()
