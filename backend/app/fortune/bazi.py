# -*- coding: utf-8 -*-
"""八字命理引擎：四柱排盘、五行分布、日主分析。

日历层使用 lunar_python（精确节气定月柱），解读层为原创的通俗模板，
仅供娱乐与自我探索参考。
"""
from __future__ import annotations

from datetime import datetime

from lunar_python import Solar

GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

GAN_WUXING = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
              "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
ZHI_WUXING = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
              "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}

WUXING_ELEMENTS = ["金", "木", "水", "火", "土"]

SHENGXIAO = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

# 日主（日干）性格速写：十天干
DAY_MASTER_PROFILE = {
    "甲": ("阳木·参天大树", "正直有担当，认定的事很难被动摇；认死理时不妨学柳树的柔"),
    "乙": ("阴木·藤蔓花草", "柔韧适应力强，擅长借力打力；偶尔需要给自己一个主心骨"),
    "丙": ("阳火·太阳", "热情开朗自带光环，走到哪都亮堂；注意别把光全给别人，忘了自己"),
    "丁": ("阴火·烛光", "细腻温暖，擅长照顾人心思；敏感是你的天赋也是你的功课"),
    "戊": ("阳土·高山", "沉稳可靠厚德载物；有时过于固执，山也要允许溪流穿过"),
    "己": ("阴土·田园", "包容善养人，身边人都爱找你；记得留一点边界给自己"),
    "庚": ("阳金·刀剑", "果决有魄力，天生的行动派；锋利之外留一点钝感，朋友会更多"),
    "辛": ("阴金·珠宝", "精致自爱有品味，追求把事做到漂亮；放下完美主义会更轻盈"),
    "壬": ("阳水·江河", "聪明灵活格局大，哪里都能流过去；偶尔需要一条河道防止发散"),
    "癸": ("阴水·雨露", "安静通透共情力强，润物细无声；把需求说出口是你的一课"),
}

# 时辰对照
HOUR_BRANCH = [("子", "23-01"), ("丑", "01-03"), ("寅", "03-05"), ("卯", "05-07"),
               ("辰", "07-09"), ("巳", "09-11"), ("午", "11-13"), ("未", "13-15"),
               ("申", "15-17"), ("酉", "17-19"), ("戌", "19-21"), ("亥", "21-23")]


def _solar(dt: datetime) -> Solar:
    return Solar.fromYmdHms(dt.year, dt.month, dt.day,
                            dt.hour if dt.hour else 12, dt.minute or 0, 0)


def analyze(birth_date: str, birth_hour: int | None, birth_minute: int = 0,
            gender: str = "女") -> dict:
    """排八字。birth_date: YYYY-MM-DD；birth_hour: 0-23（未知传 None，默认按正午排盘）
    返回结构含：四柱、农历生日、生肖、日主分析、五行分布、通俗总结。"""
    dt = datetime.strptime(birth_date, "%Y-%m-%d")
    if birth_hour is None:
        birth_hour = 12  # 缺省按正午，避免子时跨日歧义
    dt = dt.replace(hour=birth_hour, minute=birth_minute or 0)
    solar = _solar(dt)
    lunar = solar.getLunar()

    pillars = {
        "year": lunar.getYearInGanZhi(),
        "month": lunar.getMonthInGanZhi(),
        "day": lunar.getDayInGanZhi(),
        "hour": lunar.getTimeInGanZhi(),
    }
    chars = list("".join(pillars.values()))

    # 五行统计（天干 + 地支主气）
    counts = {e: 0 for e in WUXING_ELEMENTS}
    for ch in chars:
        if ch in GAN_WUXING:
            counts[GAN_WUXING[ch]] += 1
        elif ch in ZHI_WUXING:
            counts[ZHI_WUXING[ch]] += 1

    missing = [e for e, n in counts.items() if n == 0]
    strongest = max(counts, key=counts.get)
    weakest = min(counts, key=counts.get)

    day_master = pillars["day"][0]
    profile = DAY_MASTER_PROFILE.get(day_master, ("未知", ""))
    # 生肖：由年支推（lunar_python 直接给出了干支，这里独立计算避免 API 差异）
    shengxiao = SHENGXIAO[ZHI.index(pillars["year"][1])]

    # 通俗解读（原创模板，仅供参考娱乐）
    parts = []
    parts.append(f"你的日主是「{day_master}」，属{profile[0]}。{profile[1]}。")
    if missing:
        parts.append(f"五行缺「{'、'.join(missing)}」——不必焦虑，命理里「缺」只是分布的描述，"
                     f"可以理解为：这方面是你更需要主动经营的领域。")
    parts.append(f"五行中最旺的是「{strongest}」（{counts[strongest]} 个），"
                 f"最弱的是「{weakest}」（{counts[weakest]} 个）。"
                 f"旺的方面你天然擅长，弱的地方多给自己一点耐心。")
    if "子" in pillars["month"] or "亥" in pillars["month"] or "丑" in pillars["month"]:
        parts.append("出生在冬季月令，底色偏沉稳内敛，情绪感受细腻是你的天赋。")
    elif "午" in pillars["month"] or "巳" in pillars["month"]:
        parts.append("出生在夏季月令，底色偏热烈直接，行动力是你的标签。")

    return {
        "pillars": [
            {"label": "年柱", "gz": pillars["year"], "desc": "祖辈与早年根基"},
            {"label": "月柱", "gz": pillars["month"], "desc": "父母与青年运势"},
            {"label": "日柱", "gz": pillars["day"], "desc": "自己与婚姻宫"},
            {"label": "时柱", "gz": pillars["hour"], "desc": "子女与晚年"},
        ],
        "lunar_date": f"农历{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
        "shengxiao": shengxiao,
        "day_master": {"gan": day_master, "wuxing": GAN_WUXING[day_master],
                       "profile": profile[0], "desc": profile[1]},
        "wuxing": {e: counts[e] for e in WUXING_ELEMENTS},
        "missing": missing,
        "strongest": strongest,
        "weakest": weakest,
        "summary": "\n\n".join(parts),
        "disclaimer": "八字解读为通俗命理模板，仅供娱乐与自我探索，不构成任何专业建议。",
    }


# ============================================================
# 干支交互：天干合化、地支冲合刑害（用于分析任意日期 vs 命局）
# ============================================================

# 天干五合（合化产物）
GAN_HE = {
    ("甲", "己"): "土", ("己", "甲"): "土",
    ("乙", "庚"): "金", ("庚", "乙"): "金",
    ("丙", "辛"): "水", ("辛", "丙"): "水",
    ("丁", "壬"): "木", ("壬", "丁"): "木",
    ("戊", "癸"): "火", ("癸", "戊"): "火",
}

# 地支六冲
ZHI_CHONG = {0: 6, 1: 7, 2: 8, 3: 9, 4: 10, 5: 11, 6: 0, 7: 1, 8: 2, 9: 3, 10: 4, 11: 5}

# 地支六合（合化产物）
ZHI_LIUHE = {
    (0, 1): "土", (2, 11): "木", (3, 10): "火", (4, 9): "金", (5, 8): "水", (6, 7): "土",
}
ZHI_LIUHE.update({(b, a): v for (a, b), v in list(ZHI_LIUHE.items())})

# 地支三合局
ZHI_SANHE_JU = {
    frozenset([8, 0, 4]): "水",   # 申子辰 → 水局
    frozenset([2, 6, 10]): "火",   # 寅午戌 → 火局
    frozenset([5, 9, 1]): "金",    # 巳酉丑 → 金局
    frozenset([11, 3, 7]): "木",   # 亥卯未 → 木局
}

# 地支相刑（对向）
ZHI_XING = [
    (2, 5), (5, 8), (8, 2),      # 寅巳申
    (1, 10), (10, 7), (7, 1),     # 丑戌未
    (0, 3), (3, 0),               # 子卯
    (4, 4), (6, 6), (9, 9), (11, 11),  # 自刑
]

# 地支相害
ZHI_HAI = {0: 7, 7: 0, 1: 6, 6: 1, 2: 5, 5: 2, 3: 4, 4: 3, 8: 11, 11: 8, 9: 10, 10: 9}


def analyze_interactions(pillars: list[dict], query_pillars: list[dict]) -> list[dict]:
    """分析命局四柱与查询日期干支的交互关系。

    pillars: [{'label': '日柱', 'gz': '戊午'}] 命局四柱
    query_pillars: [{'label': '流年', 'gz': '丙午'}] 查询日期的年/月/日柱
    返回交互结果列表，每条含 source/target/type/detail/analysis
    """
    results = []

    def zhi_idx(c):
        return ZHI.index(c) if c in ZHI else -1

    for qp in query_pillars:
        q_gan, q_zhi = qp["gz"][0], qp["gz"][1]
        q_zhi_i = zhi_idx(q_zhi)
        if q_zhi_i < 0:
            continue
        for mp in pillars:
            m_gan, m_zhi = mp["gz"][0], mp["gz"][1]
            m_zhi_i = zhi_idx(m_zhi)

            # 天干五合
            he = GAN_HE.get((m_gan, q_gan))
            if he:
                results.append({
                    "source": f"{mp['label']}{m_gan}",
                    "target": f"{qp['label']}{q_gan}",
                    "type": "天干合化",
                    "detail": f"{m_gan}{q_gan}合化{he}",
                    "analysis": f"{mp['label']}的天干{m_gan}与{qp['label']}的天干{q_gan}合化"
                                f"为{he}——两种力量融合成新的{he}气，"
                                f"在此期间{he}属性的事务容易有突破或转机。",
                })

            # 地支六冲
            if ZHI_CHONG.get(m_zhi_i) == q_zhi_i:
                results.append({
                    "source": f"{mp['label']}{m_zhi}",
                    "target": f"{qp['label']}{q_zhi}",
                    "type": "地支相冲",
                    "detail": f"{m_zhi}{q_zhi}冲",
                    "analysis": f"{mp['label']}的地支{m_zhi}与{qp['label']}的地支{q_zhi}相冲——"
                                f"冲主动、主变，涉及{mp['label']}领域的事务在此时段可能有明显的变化、"
                                f"抉择或转折。冲不一定是坏事，它也可能打破僵局。",
                })

            # 地支六合
            liuhe = ZHI_LIUHE.get((m_zhi_i, q_zhi_i))
            if liuhe:
                results.append({
                    "source": f"{mp['label']}{m_zhi}",
                    "target": f"{qp['label']}{q_zhi}",
                    "type": "地支六合",
                    "detail": f"{m_zhi}{q_zhi}合化{liuhe}",
                    "analysis": f"{mp['label']}的地支{m_zhi}与{qp['label']}的地支{q_zhi}六合化{liuhe}——"
                                f"两种力量协调融合，合作、感情、谈判类事务在此期间顺遂。",
                })

            # 地支相刑
            if (m_zhi_i, q_zhi_i) in ZHI_XING:
                results.append({
                    "source": f"{mp['label']}{m_zhi}",
                    "target": f"{qp['label']}{q_zhi}",
                    "type": "地支相刑",
                    "detail": f"{m_zhi}刑{q_zhi}",
                    "analysis": f"{mp['label']}的地支{m_zhi}与{qp['label']}的地支{q_zhi}相刑——"
                                f"刑主磨、主纠结，涉及{mp['label']}领域的事务在此期间可能有些内耗或反复，"
                                f"多一分耐心即可渡过。",
                })

            # 地支相害
            if ZHI_HAI.get(m_zhi_i) == q_zhi_i:
                results.append({
                    "source": f"{mp['label']}{m_zhi}",
                    "target": f"{qp['label']}{q_zhi}",
                    "type": "地支相害",
                    "detail": f"{m_zhi}{q_zhi}害",
                    "analysis": f"{mp['label']}的地支{m_zhi}与{qp['label']}的地支{q_zhi}相害——"
                                f"暗中有些小阻力，注意{mp['label']}领域在此期间的小人是非，"
                                f"低调行可化解。",
                })

    return results


def compute_dayun_for_date(birth_date: str, birth_hour: int | None, gender: str,
                            query_date: str | None = None) -> dict:
    """计算指定日期的大运/流年/流月/流日（默认当天） + 命局交互分析。"""
    from datetime import datetime as _dt
    from lunar_python import Solar as _Solar

    base = compute_dayun(birth_date, birth_hour, gender)

    # 查询日期的干支
    qd = _dt.strptime(query_date, "%Y-%m-%d") if query_date else _dt.now()
    q_solar = _Solar.fromYmd(qd.year, qd.month, qd.day)
    q_lunar = q_solar.getLunar()
    q_year_gz = q_lunar.getYearInGanZhi()
    q_month_gz = q_lunar.getMonthInGanZhi()
    q_day_gz = q_lunar.getDayInGanZhi()

    # 大运定位（根据查询日期的年龄）
    age = qd.year - _dt.strptime(birth_date, "%Y-%m-%d").year
    current_dayun = None
    for i, d in enumerate(base["dayun"]):
        if d["age_from"] <= age < d["age_to"]:
            current_dayun = dict(d)
            current_dayun["index"] = i
            break
    if current_dayun is None and base["dayun"]:
        current_dayun = dict(base["dayun"][-1])
        current_dayun["index"] = len(base["dayun"]) - 1

    # 命局四柱
    from lunar_python import Solar
    b_dt = _dt.strptime(birth_date, "%Y-%m-%d")
    if birth_hour is None:
        birth_hour = 12
    b_solar = Solar.fromYmdHms(b_dt.year, b_dt.month, b_dt.day, birth_hour, 0, 0)
    b_lunar = b_solar.getLunar()
    pillars = [
        {"label": "年柱", "gz": b_lunar.getYearInGanZhi()},
        {"label": "月柱", "gz": b_lunar.getMonthInGanZhi()},
        {"label": "日柱", "gz": b_lunar.getDayInGanZhi()},
        {"label": "时柱", "gz": b_lunar.getTimeInGanZhi()},
    ]

    # 查询日期三柱
    query_pillars = [
        {"label": "流年", "gz": q_year_gz},
        {"label": "流月", "gz": q_month_gz},
        {"label": "流日", "gz": q_day_gz},
    ]

    # 交互分析
    interactions = analyze_interactions(pillars, query_pillars)

    # 加上大运柱的交互
    if current_dayun:
        interactions += analyze_interactions(pillars,
            [{"label": "大运", "gz": current_dayun["gz"]}])

    return {
        "query_date": qd.strftime("%Y-%m-%d"),
        "direction": base["direction"],
        "start_age": base["start_age"],
        "dayun": base["dayun"],
        "current_dayun": current_dayun,
        "current_year": {"gz": q_year_gz, "gan": q_year_gz[0], "zhi": q_year_gz[1],
                         "wuxing_gan": GAN_WUXING[q_year_gz[0]],
                         "wuxing_zhi": ZHI_WUXING[q_year_gz[1]]},
        "current_month": {"gz": q_month_gz},
        "current_day": {"gz": q_day_gz},
        "interactions": interactions,
    }

_YANG_GAN = {"甲", "丙", "戊", "庚", "壬"}

# 十天干四化表（化禄/化权/化科/化忌）—— 紫微斗数通用，八字流年也用
SIHUA = {
    "甲": ["廉贞", "破军", "武曲", "太阳"],
    "乙": ["天机", "天梁", "紫微", "太阴"],
    "丙": ["天同", "天机", "文昌", "廉贞"],
    "丁": ["太阴", "天同", "天机", "巨门"],
    "戊": ["贪狼", "太阴", "右弼", "天机"],
    "己": ["武曲", "贪狼", "天梁", "文曲"],
    "庚": ["太阳", "武曲", "太阴", "天同"],
    "辛": ["巨门", "太阳", "文曲", "文昌"],
    "壬": ["天梁", "紫微", "左辅", "武曲"],
    "癸": ["破军", "巨门", "太阴", "贪狼"],
}

# 五行生克
_WX_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}  # A生B
_WX_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}    # A克B

# 生肖三合/六合/冲/刑/害
_SANHE = {0: [4, 8], 1: [5, 9], 2: [6, 10], 3: [7, 11],
          4: [8, 0], 5: [9, 1], 6: [10, 2], 7: [11, 3],
          8: [0, 4], 9: [1, 5], 10: [2, 6], 11: [3, 7]}
_LIUHE = {0: 1, 1: 0, 2: 11, 3: 10, 4: 9, 5: 8, 6: 7, 7: 6, 8: 5, 9: 4, 10: 3, 11: 2}
_CHONG = {0: 6, 1: 7, 2: 8, 3: 9, 4: 10, 5: 11, 6: 0, 7: 1, 8: 2, 9: 3, 10: 4, 11: 5}


def compute_dayun(birth_date: str, birth_hour: int | None, gender: str) -> dict:
    """计算大运：阳男阴女顺排 / 阴男阳女逆排，起运按节气差折算（3天=1岁）。
    返回 {dayun: [...], current_dayun: {...}, current_year, current_month, current_day}
    """
    from datetime import datetime as _dt, timedelta as _td
    from lunar_python import Solar as _Solar

    dt = _dt.strptime(birth_date, "%Y-%m-%d")
    if birth_hour is None:
        birth_hour = 12
    dt = dt.replace(hour=birth_hour)
    solar = _Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)
    lunar = solar.getLunar()

    year_gan = lunar.getYearInGanZhi()[0]
    month_gz = lunar.getMonthInGanZhi()
    is_yang_year = year_gan in _YANG_GAN
    # 阳男阴女顺，阴男阳女逆
    forward = (is_yang_year and gender == "男") or (not is_yang_year and gender == "女")

    # 起运：从出生时刻数到下一个/上一个节气（节，非气）
    jieqi_table = lunar.getJieQiTable()
    # 找出生日期前后最近的"节"
    from lunar_python import Lunar as _Lunar
    l = lunar
    prev_jie = l.getPrevJie()
    next_jie = l.getNextJie()
    if forward:
        target_jie = next_jie
        days = (target_jie.getSolar().getYear(), target_jie.getSolar().getMonth(),
                target_jie.getSolar().getDay())
        target_dt = _dt(days[0], days[1], days[2])
        diff_days = (target_dt - dt).days
    else:
        target_jie = prev_jie
        target_dt = _dt(target_jie.getSolar().getYear(),
                        target_jie.getSolar().getMonth(),
                        target_jie.getSolar().getDay())
        diff_days = (dt - target_dt).days

    diff_days = max(0, diff_days)
    start_age = diff_days / 3.0  # 3天=1岁
    if start_age < 0.1:
        start_age = 0.1

    # 排 8 步大运（每步 10 年），从月柱起
    dayun = []
    month_gan_idx = GAN.index(month_gz[0])
    month_zhi_idx = ZHI.index(month_gz[1])
    for i in range(8):
        if forward:
            gi = (month_gan_idx + i + 1) % 10
            zi = (month_zhi_idx + i + 1) % 12
        else:
            gi = (month_gan_idx - i - 1) % 10
            zi = (month_zhi_idx - i - 1) % 12
        gz = GAN[gi] + ZHI[zi]
        age_from = start_age + i * 10
        age_to = age_from + 10
        dayun.append({
            "gz": gz, "age": f"{age_from:.0f}~{age_to:.0f}",
            "age_from": round(age_from), "age_to": round(age_to),
            "gan": GAN[gi], "zhi": ZHI[zi],
            "wuxing_gan": GAN_WUXING[GAN[gi]], "wuxing_zhi": ZHI_WUXING[ZHI[zi]],
        })

    # 当前大运（根据今年年份与出生年份的差）
    now = _dt.now()
    age = now.year - dt.year
    current_dayun = None
    for i, d in enumerate(dayun):
        if d["age_from"] <= age < d["age_to"]:
            current_dayun = d
            current_dayun["index"] = i
            break
    if current_dayun is None and dayun:
        current_dayun = dayun[-1]
        current_dayun["index"] = len(dayun) - 1

    # 流年（当前年干支）
    now_solar = _Solar.fromYmd(now.year, now.month, now.day)
    now_lunar = now_solar.getLunar()
    year_gz = now_lunar.getYearInGanZhi()
    month_gz_now = now_lunar.getMonthInGanZhi()
    day_gz_now = now_lunar.getDayInGanZhi()

    return {
        "direction": "顺排" if forward else "逆排",
        "start_age": round(start_age, 1),
        "dayun": dayun,
        "current_dayun": current_dayun,
        "current_year": {"gz": year_gz, "gan": year_gz[0], "zhi": year_gz[1],
                         "wuxing_gan": GAN_WUXING[year_gz[0]], "wuxing_zhi": ZHI_WUXING[year_gz[1]]},
        "current_month": {"gz": month_gz_now},
        "current_day": {"gz": day_gz_now},
    }


def day_fortune_from_bazi(day_master_gan: str, day_master_wuxing: str,
                          shengxiao: str, day_gz: str) -> dict:
    """基于八字日主五行 + 生肖 + 当日干支 的五行生克关系计算运势分。

    返回 {overall: 0-100, aspects: {love/career/wealth/health}, reason: str}
    """
    dm_gan = GAN.index(day_master_gan) if day_master_gan in GAN else 0
    day_gan = day_gz[0]
    day_zhi = day_gz[1]
    day_gan_wx = GAN_WUXING[day_gan]
    day_zhi_wx = ZHI_WUXING[day_zhi]

    # 1. 日主 vs 当日天干五行
    score = 50
    reason_parts = []
    if day_gan_wx == day_master_wuxing:
        score += 15
        reason_parts.append(f"当日天干属{day_gan_wx}，与你的日主同五行，如鱼得水")
    elif _WX_SHENG.get(day_gan_wx) == day_master_wuxing:
        score += 10
        reason_parts.append(f"当日{day_gan_wx}生{day_master_wuxing}，有助力")
    elif _WX_KE.get(day_master_wuxing) == day_gan_wx:
        score -= 10
        reason_parts.append(f"你的{day_master_wuxing}克当日{day_gan_wx}，主动权在你")
    elif _WX_KE.get(day_gan_wx) == day_master_wuxing:
        score -= 15
        reason_parts.append(f"当日{day_gan_wx}克你的{day_master_wuxing}，压力偏大")

    # 2. 生肖 vs 当日地支
    sx_idx = SHENGXIAO.index(shengxiao) if shengxiao in SHENGXIAO else -1
    day_zhi_idx = ZHI.index(day_zhi)
    if sx_idx >= 0:
        if day_zhi_idx in _SANHE.get(sx_idx, []):
            score += 12
            reason_parts.append(f"你的生肖{shengxiao}与当日地支{day_zhi}成三合，协作顺利")
        elif _LIUHE.get(sx_idx) == day_zhi_idx:
            score += 10
            reason_parts.append(f"生肖{shengxiao}与{day_zhi}六合，贵人缘佳")
        elif _CHONG.get(sx_idx) == day_zhi_idx:
            score -= 15
            reason_parts.append(f"生肖{shengxiao}与{day_zhi}相冲，注意变动")
        else:
            reason_parts.append(f"生肖{shengxiao}与当日{day_zhi}中性相处")

    # 3. 当日地支五行 vs 日主五行
    if _WX_SHENG.get(day_zhi_wx) == day_master_wuxing:
        score += 5
        reason_parts.append(f"地支{day_zhi}（{day_zhi_wx}）暗中滋养你的日主")
    elif _WX_KE.get(day_zhi_wx) == day_master_wuxing:
        score -= 5
        reason_parts.append(f"地支{day_zhi}（{day_zhi_wx}）与日主略有压制")

    score = max(20, min(98, score))

    # 各维度微调（由总分派生，加上五行关系的小差异）
    base = score
    # 财运：日主克者为财
    wealth_wx = _WX_KE.get(day_master_wuxing, "")
    if wealth_wx == day_gan_wx or wealth_wx == day_zhi_wx:
        wealth = min(98, base + 8)
    else:
        wealth = max(25, base - 5)
    # 事业：同五行者帮身
    career = min(98, base + 3) if day_gan_wx == day_master_wuxing else base
    # 桃花：三合日加成
    love = max(25, min(98, base + (10 if sx_idx >= 0 and day_zhi_idx in _SANHE.get(sx_idx, []) else -3)))
    # 健康：地支生扶日主则好
    health = max(25, min(98, base + (5 if _WX_SHENG.get(day_zhi_wx) == day_master_wuxing else -3)))

    return {
        "overall": score,
        "aspects": {"love": love, "career": career, "wealth": wealth, "health": health},
        "reason": "\n".join(reason_parts),
    }
