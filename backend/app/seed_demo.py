# -*- coding: utf-8 -*-
"""生成演示用 mock 数据：用户、会话、消息、长周期情绪档案（近 90 天）。

运行：  python -m app.seed_demo
说明：  会清空除管理员外的所有业务数据后重建，仅用于本地 demo。
"""
import json
import random
from datetime import datetime, timedelta, timezone

from .database import SessionLocal, init_db
from .models import (ChatSession, EmotionCalibration, EmotionRecord, ForumComment,
                     ForumLike, ForumPost, Message, User)
from .security import hash_password

random.seed(42)

POSITIVE = ["喜悦", "平静", "感恩", "期待"]
NEGATIVE = ["悲伤", "焦虑", "愤怒", "恐惧", "孤独", "委屈", "低落"]
NEUTRAL = ["中性"]

TRIGGERS = ["工作压力大", "被领导批评", "和同事争执", "失眠睡不好", "一个人过节",
            "和家人拌嘴", "考试没发挥好", "被误解", "身体不太舒服", "想起旧事",
            "项目赶进度", "担心未来", "和朋友闹别扭", "收到好消息", "完成一件事"]

MOCK_USERS = [
    ("13900000001", "林小暖", 60),
    ("13900000002", "陈一诺", 45),
    ("13900000003", "周未眠", 40),
    ("13900000004", "苏念", 35),
    ("13900000005", "阿泽", 30),
    ("13900000006", "夏栀", 21),
    ("13900000007", "顾清", 14),
    ("13900000008", "李慢慢", 7),
]

DEMO_PHONE = "13900000000"
DEMO_PWD = "123456"

DEMO_SESSIONS = [
    {
        "title": "最近有点撑不住",
        "days_ago": 0,
        "dialog": [
            ("user", "最近工作压力好大，天天加班，感觉快撑不住了"),
            ("assistant", "听起来你这段时间真的很辛苦，连轴转的日子一定把你累坏了。谢谢你愿意说出来，我陪着你，先别急着硬扛。"),
            ("user", "嗯…今天又被领导批评了，觉得自己很没用"),
            ("assistant", "被批评的滋味很不好受，会让人怀疑自己。但那只是一件事，不代表你这个人不好。你已经很努力了，允许自己难过一会儿。"),
            ("user", "谢谢你，跟你说完好受一点了"),
            ("assistant", "能让你稍微轻松一点，我也很安心。记得今晚早点休息，对自己温柔一点好不好？"),
        ],
        "emotions": ["焦虑", "悲伤", "感恩"],
    },
    {
        "title": "一个人的周末",
        "days_ago": 1,
        "dialog": [
            ("user", "周末一个人待在家里，好孤独，好像没人记得我"),
            ("assistant", "一个人的周末确实容易让人心里空落落的。但此刻你愿意和我说话，我们就已经连接上了，你不是一个人。"),
            ("user", "有时候真的觉得没人理解我"),
            ("assistant", "那种不被理解的感觉很沉。可我在这里，愿意听你把心里的话都讲给我，你愿意说多久都可以。"),
        ],
        "emotions": ["孤独", "委屈"],
    },
    {
        "title": "小小的开心",
        "days_ago": 2,
        "dialog": [
            ("user", "今天同事请我喝奶茶，突然觉得生活也挺好的，哈哈"),
            ("assistant", "哈哈，被惦记的感觉真好！这份小小的开心值得被记住，你今天一定过得挺暖的。"),
            ("user", "是的，心情特别好"),
            ("assistant", "看到你开心我也跟着高兴～把这份好心情存起来，遇到阴天的时候拿出来暖暖自己。"),
        ],
        "emotions": ["喜悦", "感恩"],
    },
]


FORUM_POSTS = [
    {"title": "今天也谢谢努力的自己", "content": "下班路上看到晚霞特别好看，突然觉得今天也没那么糟。想对还在一路坚持的自己说一句：辛苦了，你已经做得很好了。", "tags": ["自我鼓励", "治愈"]},
    {"title": "分享一个让我走出低谷的小习惯", "content": "每天睡前写下三件今天的小确幸，哪怕只是喝到一杯好喝的奶茶。坚持一个月，我发现自己的注意力慢慢从'缺什么'转向了'有什么'。", "tags": ["成长", "小确幸"]},
    {"title": "难过的时候，允许自己哭一会儿", "content": "以前总觉得哭是软弱，后来才明白，眼泪是情绪的出口。哭完洗把脸，天还是亮的。允许自己有低谷，也是一种温柔。", "tags": ["情绪", "自我接纳"]},
    {"title": "给正在焦虑的你：慢一点也没关系", "content": "焦虑往往是因为我们太想快点抵达。可人生不是百米冲刺，慢慢走，只要方向对，就一定会到。今天先照顾好自己，好吗？", "tags": ["焦虑", "鼓励"]},
    {"title": "被一朵花治愈的早晨", "content": "早上出门，楼下的花开了，粉粉的一片。生活里总有一些不期而遇的美好，提醒我们世界还爱着我们。", "tags": ["治愈", "生活"]},
    {"title": "谢谢你，陌生人", "content": "今天在地铁上差点摔倒，一个陌生姐姐扶了我一把，还笑着说'小心哦'。原来温柔真的会传染，我也想成为这样的人。", "tags": ["温暖", "善良"]},
    {"title": "一个人吃饭也可以很浪漫", "content": "给自己做了顿认真的一人食，摆了盘、点了蜡烛。独处不是孤独，是和自己好好相处的仪式感。", "tags": ["独处", "生活"]},
    {"title": "把'我不行'改成'我再试试'", "content": "语言会影响心态。同样一件事，说'我不行'就真的放弃了，说'我再试试'，往往就还有转机。从今天起，练习对自己说好听的话。", "tags": ["成长", "自我鼓励"]},
]

FORUM_COMMENTS = [
    "看完心里暖暖的，谢谢分享～",
    "抱抱你，也抱抱我自己。",
    "说得太对了，我也要试试！",
    "今天也被你治愈到了。",
    "一起加油鸭，我们都不孤单。",
]

# 角色使用分布（用于生成"热门角色"榜数据），权重让部分角色更热门
PERSONA_WEIGHTS = {
    "nuan": 10, "mama": 9, "sister": 7, "xiaomei": 6, "anime": 4, "succubus": 3,
    "hinata": 8, "naruto": 6, "sakura": 4, "kakashi": 4, "nezuko": 5,
    "paimon": 7, "ganyu": 6, "hutao": 8, "raiden": 5, "nahida": 5, "furina": 6,
    "zhongli": 4, "venti": 3, "klee": 5, "march7": 6, "danheng": 3,
}


def _polarity(et):
    if et in POSITIVE:
        return 1
    if et in NEGATIVE:
        return -1
    return 0


def _heal(et):
    if et in NEGATIVE:
        return round(random.uniform(0.4, 0.95), 2)
    return round(random.uniform(0.3, 0.9), 2)


def _intent(et):
    if et in NEGATIVE:
        return random.choice(["倾诉", "求助", "倾诉"])
    if et == "喜悦":
        return "分享"
    if et == "中性":
        return "闲聊"
    return "分享"


def clear_business_data(db):
    db.query(EmotionCalibration).delete()
    db.query(Message).delete()
    db.query(ChatSession).delete()
    db.query(EmotionRecord).delete()
    db.query(ForumLike).delete()
    db.query(ForumComment).delete()
    db.query(ForumPost).delete()
    db.query(User).filter(User.role != "admin").delete()
    db.commit()


def seed():
    init_db()
    db = SessionLocal()
    try:
        clear_business_data(db)

        # 1) 普通 mock 用户 + 长周期情绪档案（近 90 天）
        mock_users = []
        for phone, nickname, days_ago in MOCK_USERS:
            u = User(phone=phone, nickname=nickname,
                     password_hash=hash_password("123456"), role="user",
                     created_at=datetime.now(timezone.utc) - timedelta(days=days_ago))
            db.add(u)
            db.flush()
            mock_users.append(u)

            # 每个用户 25~45 条记录，铺满近 90 天（越近越密集）
            n = random.randint(25, 45)
            for _ in range(n):
                # 让近期记录更密集
                d = int(random.triangular(0, 89, 5))
                et = random.choices(
                    POSITIVE + NEGATIVE + NEUTRAL,
                    weights=[10, 8, 6, 6, 12, 12, 6, 4, 8, 6, 14, 10])[0]
                ts = datetime.now(timezone.utc) - timedelta(
                    days=d, hours=random.randint(6, 23), minutes=random.randint(0, 59))
                trig = random.choice(TRIGGERS) if et != "中性" else ""
                db.add(EmotionRecord(
                    user_id=u.id, session_id=None, emotion_type=et,
                    score=_heal(et), polarity=_polarity(et), source="rule",
                    intent=_intent(et), trigger=trig,
                    detail=json.dumps({"mock": True}, ensure_ascii=False),
                    created_at=ts,
                ))
        db.commit()

        # 2) 演示聊天账号
        demo = User(phone=DEMO_PHONE, nickname="演示用户",
                    password_hash=hash_password(DEMO_PWD), role="user",
                    created_at=datetime.now(timezone.utc) - timedelta(days=30))
        db.add(demo)
        db.flush()

        # 演示账号的长周期档案（让情绪档案页有内容）
        for _ in range(30):
            d = random.randint(0, 60)
            et = random.choice(POSITIVE + NEGATIVE + NEGATIVE + NEUTRAL + POSITIVE)
            ts = datetime.now(timezone.utc) - timedelta(
                days=d, hours=random.randint(7, 23), minutes=random.randint(0, 59))
            db.add(EmotionRecord(
                user_id=demo.id, session_id=None, emotion_type=et,
                score=_heal(et), polarity=_polarity(et), source="rule",
                intent=_intent(et),
                trigger=random.choice(TRIGGERS) if et in NEGATIVE else "",
                detail=json.dumps({"mock": True}, ensure_ascii=False),
                created_at=ts,
            ))

        for idx, s in enumerate(DEMO_SESSIONS):
            base = datetime.now(timezone.utc) - timedelta(days=s["days_ago"])
            persona_id = ["sister", "nuan", "xiaomei"][idx % 3]
            sess = ChatSession(user_id=demo.id, title=s["title"], persona_id=persona_id,
                               created_at=base, updated_at=base)
            db.add(sess)
            db.flush()

            for i, (role, content) in enumerate(s["dialog"]):
                ts = base + timedelta(minutes=i * 3)
                emo = None
                if role == "user":
                    et = s["emotions"][min(i // 2, len(s["emotions"]) - 1)]
                    emo = et
                    db.add(EmotionRecord(
                        user_id=demo.id, session_id=sess.id, emotion_type=et,
                        score=_heal(et), polarity=_polarity(et), source="rule",
                        intent=_intent(et),
                        trigger=(content[:40] + "…") if len(content) > 40 else content,
                        detail=json.dumps({"mock": True}, ensure_ascii=False),
                        created_at=ts,
                    ))
                db.add(Message(session_id=sess.id, role=role, content=content,
                               msg_type="text", emotion_type=emo or "中性",
                               emotion_score=_heal(emo) if emo else 0.0,
                               emotion_source="rule", created_at=ts))

            sess.updated_at = base + timedelta(minutes=len(s["dialog"]) * 3)

        # 3) 演示账号的情绪校准记录（展示「个人情绪校准」功能）
        db.add_all([
            EmotionCalibration(user_id=demo.id, original_emotion="焦虑",
                               corrected_emotion="悲伤", text="压力好大，有点喘不过气"),
            EmotionCalibration(user_id=demo.id, original_emotion="喜悦",
                               corrected_emotion="平静", text="还行吧，平平淡淡"),
        ])

        # 4) 正能量社区帖子 + 点赞 + 评论
        all_users = [demo] + mock_users
        covers = ["/uploads/cover1.svg", "/uploads/cover2.svg",
                  "/uploads/cover3.svg", "/uploads/cover4.svg"]
        posts = []
        for i, p in enumerate(FORUM_POSTS):
            author = demo if i == 0 else mock_users[i % len(mock_users)]
            base = datetime.now(timezone.utc) - timedelta(
                days=random.randint(0, 5), hours=random.randint(1, 20))
            imgs = [covers[i]] if i < len(covers) else []
            blocks = [{"type": "text", "text": p["content"]}]
            for u in imgs:
                blocks.append({"type": "image", "url": u})
            post = ForumPost(user_id=author.id, title=p["title"], content=p["content"],
                             tags=",".join(p["tags"]),
                             image_urls=json.dumps(imgs, ensure_ascii=False),
                             blocks=json.dumps(blocks, ensure_ascii=False),
                             created_at=base)
            db.add(post)
            db.flush()
            posts.append(post)
        for post in posts:
            for u in random.sample(all_users, k=random.randint(1, len(all_users))):
                db.add(ForumLike(post_id=post.id, user_id=u.id))
            for _ in range(random.randint(0, 3)):
                db.add(ForumComment(post_id=post.id, user_id=random.choice(all_users).id,
                                    content=random.choice(FORUM_COMMENTS)))

        # 5) 角色使用分布（为「热门角色」榜提供数据，仅给 mock 用户建会话）
        ids = list(PERSONA_WEIGHTS.keys())
        weights = [PERSONA_WEIGHTS[i] for i in ids]
        for u in mock_users:
            for _ in range(random.randint(1, 4)):
                pid = random.choices(ids, weights=weights)[0]
                db.add(ChatSession(user_id=u.id, title="和角色聊天", persona_id=pid))

        db.commit()
        print(f"✓ 演示数据已生成：{len(MOCK_USERS)} 个 mock 用户 + 1 个演示账号")
        print(f"  演示账号：{DEMO_PHONE} / {DEMO_PWD}")
        print(f"  管理员：  13800000000 / admin123")
        print(f"  情绪档案覆盖近 90 天；社区帖子 {len(posts)} 篇（含赞与评论）")
        print("  多智能体角色会话已内置（姐姐/小窝/妹妹）")
    finally:
        db.close()


if __name__ == "__main__":
    seed()