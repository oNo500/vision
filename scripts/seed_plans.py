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

from vision_shared.db import Database  # noqa: E402

SAMPLE_PLAN = {
    "name": "示例方案 · 垆土铁棍山药粉",
    "product": {
        "name": "垆土铁棍山药粉",
        "description": "产自河南焦作温县垆土地，铁棍山药经低温烘干、石磨研磨制成。垆土保水保肥，铁棍山药淀粉细腻、黏液蛋白丰富，冲泡即食，健脾养胃，老少皆宜。",
        "price": "128元/500g（直播间专属价，原价168元）",
        "highlights": [
            "原产地垆土认证，非普通沙地山药",
            "低温烘干锁住黏液蛋白，营养不流失",
            "石磨研磨，粉质细腻无颗粒感",
            "冲泡即食，60°水冲开即可，不结块",
            "无添加无增稠剂，配料表只有山药",
        ],
        "faq": [
            {"question": "和普通山药粉有什么区别？", "answer": "铁棍山药产自温县垆土地，黏液蛋白含量是普通山药的3倍以上，口感更细腻，养胃效果更明显。"},
            {"question": "怎么冲泡？", "answer": "取一勺（约20g）放入碗中，先用少量60度温水调成糊，再加热水搅匀即可。不能用开水直接冲，会结块。"},
            {"question": "糖尿病人能喝吗？", "answer": "山药GI值较低，但我们不做医疗建议，请在医生指导下根据自身情况决定。"},
            {"question": "保质期多久？", "answer": "密封干燥存放18个月。开封后建议3个月内喝完，放冰箱冷藏更佳。"},
            {"question": "有没有小包装试喝？", "answer": "今天直播间拍500g正装，赠送3小包独立装，出差旅行携带方便。"},
        ],
    },
    "persona": {
        "name": "豫珍",
        "style": "朴实接地气，像邻居大姐推荐自家好物，讲产地讲故事，不用网红腔，强调真实农产品品质",
        "catchphrases": [
            "家人们看一下",
            "这个真的不一样",
            "我们产地直发",
            "老品种，老口味",
            "冲就完了",
        ],
        "forbidden_words": ["治疗", "药用", "治病", "降血糖", "最便宜", "全网最低", "无副作用"],
    },
    # Script design: each segment = one phase of the live session.
    # - title: phase name (e.g., "开场预热")
    # - goal: the strategic intent for this phase (what to accomplish)
    # - duration: how long this phase lasts in seconds
    # - cue: key talking points or verbatim lines (may be empty)
    # - must_say: True = deliver cue items verbatim; False = cue is optional context
    # - keywords: topics to naturally weave in during this phase
    "script": {
        "segments": [
            {
                "id": "s1",
                "title": "开场预热",
                "goal": "欢迎新进来的观众，介绍今天主角是河南温县垆土铁棍山药粉，引导点关注、开小黄车，说清楚直播间今天有专属价。",
                "duration": 300,
                "cue": [],
                "must_say": False,
                "keywords": ["关注", "小黄车", "温县", "垆土", "直播间专属价"],
            },
            {
                "id": "s2",
                "title": "产地故事",
                "goal": "讲垆土和铁棍山药的关系：为什么温县出好山药，垆土保水保肥，铁棍山药生长周期长，黏液蛋白含量高。让观众先建立对产品来源的信任感。",
                "duration": 600,
                "cue": [
                    "温县垆土，保水保肥，和沙地山药完全不一样",
                    "铁棍山药生长周期比普通山药长两个月",
                    "黏液蛋白含量是普通山药的三倍以上",
                ],
                "must_say": False,
                "keywords": ["温县", "垆土", "铁棍山药", "黏液蛋白", "产地"],
            },
            {
                "id": "s3",
                "title": "产品介绍",
                "goal": "重点讲加工工艺：低温烘干锁住营养、石磨研磨口感细腻、无添加配料表只有山药。结合冲泡演示，让观众看到实物状态和口感。",
                "duration": 900,
                "cue": [
                    "低温烘干，营养不流失",
                    "石磨研磨，粉质细腻，冲出来没有颗粒",
                    "配料表翻过来看，就只有山药两个字",
                ],
                "must_say": False,
                "keywords": ["低温烘干", "石磨", "无添加", "细腻", "冲泡"],
            },
            {
                "id": "s4",
                "title": "现场冲泡演示",
                "goal": "现场演示正确冲泡方法，强调先用温水调糊再加热水，展示成品颜色和质地，让观众看到实际效果，消除「会不会结块」的顾虑。",
                "duration": 600,
                "cue": [
                    "先用60度温水把它调成糊，不要直接用开水",
                    "你们看，一点颗粒都没有，非常细腻",
                    "颜色是自然的淡黄色，没有漂白过",
                ],
                "must_say": True,
                "keywords": ["温水调糊", "细腻", "颜色", "演示"],
            },
            {
                "id": "s5",
                "title": "互动答疑",
                "goal": "回答弹幕里的问题：怎么吃、能不能加牛奶、糖尿病人适不适合、保质期、和其他品牌的区别。保持轻松对话感，引导继续提问。",
                "duration": 600,
                "cue": [],
                "must_say": False,
                "keywords": ["怎么吃", "牛奶", "保质期", "区别", "问题"],
            },
            {
                "id": "s6",
                "title": "限时促单",
                "goal": "制造紧迫感，强调直播间专属价和赠品，给还在犹豫的观众最后一推。",
                "duration": 300,
                "cue": [
                    "直播间专属128，平时要168，只有今天",
                    "拍500g正装，额外赠3小包独立装",
                    "库存不多，家人们冲",
                ],
                "must_say": True,
                "keywords": ["128", "限时", "赠品", "库存", "下单"],
            },
            {
                "id": "s7",
                "title": "产品介绍（第二轮）",
                "goal": "新进来的观众较多，重新简短介绍产地和产品卖点，引导点购物车，顺带回应新弹幕的问题。",
                "duration": 600,
                "cue": [
                    "温县垆土铁棍山药，不是普通山药",
                    "低温烘干无添加，配料表就山药两字",
                ],
                "must_say": False,
                "keywords": ["温县", "无添加", "购物车", "新观众"],
            },
            {
                "id": "s8",
                "title": "收尾预告",
                "goal": "感谢下单的家人，提醒收货注意事项，预告下次直播时间和产品，引导关注账号，温馨道别。",
                "duration": 300,
                "cue": [],
                "must_say": False,
                "keywords": ["感谢", "收货", "下次直播", "关注", "再见"],
            },
        ]
    },
}


async def seed(db_path: str) -> None:
    db = Database(db_path)
    await db.init()

    from vision_live.plan_store import PlanStore
    store = PlanStore(db.conn)
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
