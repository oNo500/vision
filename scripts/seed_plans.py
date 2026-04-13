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
    "script": {
        "segments": [
            {
                "id": "s1",
                "text": "宝宝们注意看！今天给大家带来一个我回购三次的水乳套装，就是这个瑷尔博士益生菌系列。",
                "duration": 15,
                "must_say": True,
                "keywords": ["瑷尔博士", "益生菌", "回购"],
            },
            {
                "id": "s2",
                "text": "咱们直播间今天专属价299，原价399，买就送同款旅行小样，数量有限，冲就完了！",
                "duration": 10,
                "must_say": True,
                "keywords": ["299", "直播间专属", "小样"],
            },
            {
                "id": "s3",
                "text": "这套水乳的核心是2000亿活性益生菌，专门修护皮肤屏障。我之前换季总过敏，用了这个之后好多了。",
                "duration": 20,
                "must_say": False,
                "keywords": ["益生菌", "屏障", "过敏"],
            },
            {
                "id": "s4",
                "text": "有宝宝问敏感肌能用吗？能用！0酒精0香精，皮肤科做过测试的，孕妇也没问题。",
                "duration": 15,
                "must_say": False,
                "keywords": ["敏感肌", "0酒精", "孕妇"],
            },
            {
                "id": "s5",
                "text": "家人们最后再说一遍，库存不多了，299拿走水乳套装加小样，不买绝对后悔，现在下单！",
                "duration": 10,
                "must_say": True,
                "keywords": ["299", "库存", "下单"],
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
