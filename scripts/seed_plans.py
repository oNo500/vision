"""Seed a sample LivePlan into vision.db for development/testing.

Usage:
    python scripts/seed_plans.py [--db PATH]

Re-running is safe: it skips insertion if a plan with the same name already exists.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path so src imports work.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shared.db import Database  # noqa: E402

SAMPLE_PLAN = {
    "name": "示例方案 · 瑷尔博士水乳套装",
    "product": {
        "name": "瑷尔博士益生菌水乳套装",
        "description": "以益生菌科技为核心，修护皮肤屏障，持续补水保湿，适合敏感肌和换季护肤需求。",
        "price": "299元（直播间专属价，原价399元）",
        "highlights": [
            "2000亿活性益生菌，强化皮肤屏障",
            "72小时持续补水，上脸不黏腻",
            "0酒精0香精，敏感肌亲测可用",
            "水乳双管，早晚护肤一步到位",
            "买一套送同款小样，拿来旅行超方便",
        ],
        "faq": [
            {"question": "敏感肌能用吗？", "answer": "可以，0酒精0香精配方，皮肤科测试过，敏感肌和孕妇均可使用。"},
            {"question": "和其他产品能叠加吗？", "answer": "可以，作为基础水乳，在洗脸后最先用，再叠加精华和防晒没问题。"},
            {"question": "多久见效？", "answer": "一般7天感受到明显保湿效果，坚持28天代谢周期后屏障修护效果更显著。"},
            {"question": "有没有试用装？", "answer": "今天拍正装直接赠送同款小样，量够用两周，特别适合先试后买。"},
        ],
    },
    "persona": {
        "name": "小美",
        "style": "亲切真实，像闺蜜推荐好物，不夸大不浮夸，强调亲身体验感",
        "catchphrases": [
            "宝宝们注意看",
            "这个真的绝了",
            "我用了三个月了，回购第三瓶了",
            "不买绝对后悔",
            "家人们冲！",
        ],
        "forbidden_words": ["最便宜", "全网最低", "治疗", "无副作用", "药用级"],
    },
    # Script design: each segment = one phase of the live session.
    # - text: instructions for the AI director (NOT a verbatim script);
    #         the AI reads this as context and speaks naturally around it.
    # - duration: how long this phase lasts in seconds; the AI fills the
    #             time by responding to danmaku and proactively talking.
    # - must_say: True = the AI must deliver the text verbatim before
    #             the phase ends (e.g., price announcements, CTAs).
    #             False = text is a guide only; AI improvises freely.
    # - keywords: topics the AI should weave in during this phase.
    "script": {
        "segments": [
            {
                "id": "s1",
                "text": (
                    "【开场预热 · 5分钟】"
                    "欢迎新进来的观众，自我介绍，告诉大家今天直播的主题是护肤好物分享。"
                    "引导点关注、开小黄车，营造轻松氛围，让观众留下来。"
                ),
                "duration": 300,
                "must_say": False,
                "keywords": ["关注", "小黄车", "今天带来"],
            },
            {
                "id": "s2",
                "text": (
                    "【产品介绍 · 20分钟】"
                    "重点讲解瑷尔博士益生菌水乳的核心卖点：益生菌科技修护屏障、72小时补水、0酒精0香精适合敏感肌。"
                    "结合自身使用体验，回应弹幕里的皮肤问题，引导观众点击购物车。"
                ),
                "duration": 1200,
                "must_say": False,
                "keywords": ["益生菌", "屏障", "敏感肌", "72小时", "购物车"],
            },
            {
                "id": "s3",
                "text": (
                    "【互动答疑 · 15分钟】"
                    "专门回答弹幕里的产品问题：成分、用法、适合肤质、与其他产品叠加顺序等。"
                    "保持轻松对话感，鼓励观众把问题打在弹幕里，逐一解答。"
                ),
                "duration": 900,
                "must_say": False,
                "keywords": ["问题", "成分", "用法", "敏感肌", "孕妇"],
            },
            {
                "id": "s4",
                "text": (
                    "【限时促单 · 5分钟】"
                    "直播间专属价299元，原价399元，买正装送同款旅行小样。库存有限，引导立即下单。"
                ),
                "duration": 300,
                "must_say": True,
                "keywords": ["299", "限时", "库存", "小样", "下单"],
            },
            {
                "id": "s5",
                "text": (
                    "【产品介绍（第二轮） · 20分钟】"
                    "新进来的观众较多，重新介绍产品卖点，侧重真实使用感受和对比其他同类产品的差异。"
                    "继续响应弹幕，保持场子热度。"
                ),
                "duration": 1200,
                "must_say": False,
                "keywords": ["益生菌", "对比", "使用感受", "购物车"],
            },
            {
                "id": "s6",
                "text": (
                    "【互动游戏 · 10分钟】"
                    "发起弹幕互动：让观众打出自己的肤质，按肤质给出不同的护肤建议，顺带植入产品适用场景。"
                    "气氛活跃后再引导下单。"
                ),
                "duration": 600,
                "must_say": False,
                "keywords": ["肤质", "弹幕", "互动", "护肤建议"],
            },
            {
                "id": "s7",
                "text": (
                    "【第二次促单 · 5分钟】"
                    "再次强调直播间价格优惠和赠品，提醒库存告急，给还在犹豫的观众最后一推。"
                ),
                "duration": 300,
                "must_say": True,
                "keywords": ["299", "赠品", "库存", "最后机会"],
            },
            {
                "id": "s8",
                "text": (
                    "【收尾预告 · 5分钟】"
                    "感谢今天的观众和下单的宝宝，预告下次直播时间和主题，引导关注账号，温馨道别。"
                ),
                "duration": 300,
                "must_say": False,
                "keywords": ["感谢", "下次直播", "关注", "再见"],
            },
        ]
    },
}


async def seed(db_path: str) -> None:
    db = Database(db_path)
    await db.init()

    store = db.plan_store
    existing = await store.list_all()
    names = {p["name"] for p in existing}

    if SAMPLE_PLAN["name"] in names:
        print(f"[skip] Plan already exists: {SAMPLE_PLAN['name']!r}")
    else:
        plan = await store.create(SAMPLE_PLAN)
        print(f"[ok]   Created plan: {plan['name']!r}  id={plan['id']}")

    await db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample LivePlan data")
    parser.add_argument("--db", default="vision.db", help="SQLite database path (default: vision.db)")
    args = parser.parse_args()
    asyncio.run(seed(args.db))


if __name__ == "__main__":
    main()
