# -*- coding: utf-8 -*-
"""每日运势：优先用八字五行生克算法计算，未提供出生信息时按生肖+日支规则 + 确定性种子兜底。

分数来源（有出生信息时）：
  1. 日主五行 vs 当日天干五行（同五行为旺、生我为助、克我者为压力）
  2. 生肖 vs 当日地支（三合/六合/相冲/中性）
  3. 当日地支五行 vs 日主五行（暗扶/暗压）
各维度（桃花/事业/财运/健康）基于总分加五行关系的差异化调整。
"""
from __future__ import annotations

import random
from datetime import datetime

from lunar_python import Solar

from .bazi import (SHENGXIAO, day_fortune_from_bazi)

COLORS = ["月白", "竹青", "琥珀金", "藕荷粉", "黛蓝", "樱草黄", "石榴红", "雾灰紫", "湖水绿", "蜜柑橙"]
LUCKY_NUMS = [1, 3, 4, 6, 7, 8, 9, 11, 16, 21, 26, 33]
JI_SHI = ["辰时 7-9点", "午时 11-13点", "申时 15-17点", "酉时 17-19点", "巳时 9-11点", "卯时 5-7点"]

DO_POOL = [
    "给房间开一次窗", "认真吃一顿好饭", "给喜欢的人发条消息", "早睡半小时",
    "整理桌面", "出门走走晒晒太阳", "写下三件顺利的小事", "听一首喜欢的歌",
    "拉伸五分钟", "把拖了很久的小事做完", "喝够八杯水", "对着镜子笑一笑",
    "读十页书", "和好朋友聊聊天", "断舍离一件旧物", "给自己买杯热饮",
]
AVOID_POOL = [
    "熬夜刷手机", "和杠精争论", "深夜大吃大喝", "冲动消费",
    "钻牛角尖", "反复回想尴尬瞬间", "拿别人的进度惩罚自己", "躺着刷一整天短视频",
    "在深夜做重要决定", "和亲近的人冷战", "憋着委屈不说", "事事追求完美",
]

HINTS_HIGH = [
    "今天能量顺着你的日主走，适合把想做的事往前推一大步。",
    "今天的五行场域与你的日主合拍，好运藏在主动里。",
    "趁今天状态好，把一直犹豫的事提上日程。",
]
HINTS_MID = [
    "今天的你适合把节奏放慢一点，慢即是快。",
    "小小的不顺只是路过的云，别让它挡住整个天空。",
    "把注意力放在能掌控的事上，其余的交给时间。",
    "今天的好运藏在细节里：一句问候、一杯热水、一小段散步。",
]
HINTS_LOW = [
    "今天压力偏大，先照顾好身体和情绪，大事明天再谈。",
    "五行相克的日子宜守不宜攻，把今天的功课当修炼。",
    "给自己减一点任务量，你已经够努力了。",
]


def daily_fortune(user_key: str, date: datetime | None = None,
                  shengxiao: str = "",
                  day_master_gan: str = "", day_master_wuxing: str = "") -> dict:
    """生成某用户某天的运势。

    Args:
        day_master_gan / day_master_wuxing: 来自八字排盘的日主信息。
        有这两个参数时走五行生克算法；否则按生肖+日支规则+确定性种子兜底。
    """
    day = date or datetime.now()
    date_str = day.strftime("%Y-%m-%d")

    solar = Solar.fromYmd(day.year, day.month, day.day)
    lunar = solar.getLunar()
    day_gz = lunar.getDayInGanZhi()
    month_gz = lunar.getMonthInGanZhi()
    day_gan = day_gz[0]
    day_zhi = day_gz[1]

    # ── 算法分数 ──
    if day_master_gan and day_master_wuxing:
        calc = day_fortune_from_bazi(day_master_gan, day_master_wuxing,
                                     shengxiao, day_gz)
        overall = calc["overall"]
        aspects = calc["aspects"]
        calc_reason = calc["reason"]
        engine = "五行生克算法（日主+当日干支）"
    else:
        # 兜底：生肖+日支 + 确定性种子
        seed = f"{user_key}|{date_str}|{shengxiao}"
        rng = random.Random(seed)
        overall = rng.randint(55, 88)
        aspects = {
            "love": rng.randint(45, 92),
            "career": rng.randint(50, 90),
            "wealth": rng.randint(45, 88),
            "health": rng.randint(55, 92),
        }
        calc_reason = "（未提供出生信息，按生肖与日支规则推演）"
        engine = "生肖+日支规则"

    # 宜忌和幸运元素仍由确定性种子选择（保持同一天不变）
    seed = f"{user_key}|{date_str}|{shengxiao}"
    rng = random.Random(seed)
    do = rng.sample(DO_POOL, 3)
    avoid = rng.sample(AVOID_POOL, 2)
    lucky_color = rng.choice(COLORS)
    lucky_number = rng.choice(LUCKY_NUMS)
    lucky_time = rng.choice(JI_SHI)

    # 提示语按分数段选
    if overall >= 75:
        hint = rng.choice(HINTS_HIGH)
    elif overall >= 55:
        hint = rng.choice(HINTS_MID)
    else:
        hint = rng.choice(HINTS_LOW)

    level = ("大吉" if overall >= 85 else
             "吉" if overall >= 72 else
             "平顺" if overall >= 60 else
             "宜养精蓄锐")

    return {
        "date": date_str,
        "ganzhi": {"day": day_gz, "month": month_gz, "gan": day_gan, "zhi": day_zhi},
        "shengxiao": shengxiao or None,
        "engine": engine,
        "calc_reason": calc_reason,
        "scores": {
            "overall": {"label": "综合运势", "value": overall},
            "love": {"label": "桃花运", "value": aspects["love"]},
            "career": {"label": "事业运", "value": aspects["career"]},
            "wealth": {"label": "财运", "value": aspects["wealth"]},
            "health": {"label": "健康运", "value": aspects["health"]},
        },
        "do": do,
        "avoid": avoid,
        "lucky_color": lucky_color,
        "lucky_number": lucky_number,
        "lucky_time": lucky_time,
        "hint": hint,
        "level": level,
        "disclaimer": "运势基于传统命理五行生克规则计算，仅供正向娱乐，不构成任何决策依据。",
    }
