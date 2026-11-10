# -*- coding: utf-8 -*-
"""紫微斗数引擎（十四主星简化盘）：定命宫身宫、五行局、安紫微天府星系、排十二宫。

排盘算法为传统安星规则（借数法安紫微、对称安天府、星系表安余星），
解读层为通俗模板，仅供娱乐参考。闰月按前半月计当月、后半月计下月的简化处理。
"""
from __future__ import annotations

from datetime import datetime

from lunar_python import Solar

from .bazi import GAN, ZHI, SHENGXIAO

# 十二宫（从命宫起逆布）
PALACES = ["命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
           "迁移宫", "交友宫", "事业宫", "田宅宫", "福德宫", "父母宫"]

PALACE_THEME = {
    "命宫": ("性格与人生主调", "它描绘你是谁、以什么姿态面对世界"),
    "兄弟宫": ("同辈与协作", "看与兄弟姐妹、朋友同事的缘分与相处模式"),
    "夫妻宫": ("亲密关系", "感情里的期待、模式与磨合课题"),
    "子女宫": ("下一代与创造", "与子女的缘分，也映射你的创造与表达"),
    "财帛宫": ("金钱与价值感", "赚钱方式与花钱习惯"),
    "疾厄宫": ("身体与情绪", "健康底色与压力易感的部位"),
    "迁移宫": ("远方与变化", "出行、变动、外部世界给你的反馈"),
    "交友宫": ("朋友圈与拥护者", "你吸引什么样的伙伴，如何经营社群"),
    "事业宫": ("成就与舞台", "适合的发展方向与奋斗姿态"),
    "田宅宫": ("家与安定感", "居住环境、家庭氛围与内心的安全感"),
    "福德宫": ("兴趣与内在", "精神世界的丰盈度、兴趣与福报"),
    "父母宫": ("长辈与庇护", "与父母长辈的关系，也代表贵人运"),
}

# 十四主星：星性（人设）与行为特征
STARS = {
    "紫微": {"element": "土", "role": "帝王", "trait": "沉稳有主见、天生领导气场，喜欢掌控全局",
             "hint": "把「我来安排」分一点给身边的人，会更受欢迎"},
    "天机": {"element": "木", "role": "军师", "trait": "心思灵巧、擅长分析谋划，脑子永远在转",
             "hint": "想得多時记得按暂停键，行动是焦虑的解药"},
    "太阳": {"element": "火", "role": "奉献者", "trait": "热情大方、乐于照亮别人，先照亮身边人",
             "hint": "学着接受别人的好意，付出也要留电给自己"},
    "武曲": {"element": "金", "role": "实干家", "trait": "刚毅果决、说干就干，执行力爆表",
             "hint": "钢铁直心之外，偶尔绕个弯表达会更暖"},
    "天同": {"element": "水", "role": "福星", "trait": "乐观知足、随遇而安，天生自带松弛感",
             "hint": "舒适圈很好，偶尔推自己一把会有惊喜"},
    "廉贞": {"element": "火", "role": "改革者", "trait": "敢爱敢拼、事业心强，不按常理出牌",
             "hint": "锋芒是魅力，收敛一分是智慧"},
    "天府": {"element": "土", "role": "财政大臣", "trait": "稳重务实、擅长理财守成，值得信赖",
             "hint": "守成为本，也记得偶尔投资一下诗和远方"},
    "太阴": {"element": "水", "role": "月亮", "trait": "温柔细腻、感受力强，安静的照顾者",
             "hint": "照顾别人之前，先把自己的情绪安顿好"},
    "贪狼": {"element": "木", "role": "欲望之星", "trait": "多才多艺、社交达人，好奇心旺盛",
             "hint": "兴趣太多没关系，留一件练到深"},
    "巨门": {"element": "水", "role": "口才之星", "trait": "口才好、爱钻研真相，天生的辩手",
             "hint": "话锋是利器，多说暖话福气自来"},
    "天相": {"element": "水", "role": "宰相", "trait": "端正热心、擅长协调平衡，天生的二把手",
             "hint": "帮人张罗之余，也别忘了自己的立场"},
    "天梁": {"element": "土", "role": "庇荫之星", "trait": "古道热肠、爱照顾人，老灵魂",
             "hint": "长辈式的关心很暖，注意别变成唠叨"},
    "七杀": {"element": "金", "role": "将星", "trait": "勇往直前、敢作敢当，天生的开拓者",
             "hint": "冲劲是天赋，留三分给复盘"},
    "破军": {"element": "水", "role": "先锋", "trait": "破旧立新、不惧改变，人生就是开荒",
             "hint": "推倒重来是你的风格，偶尔停一停清点战果"},
}

# ============================================================
# 星曜亮度（庙旺得利平不陷）——每星在各地支的亮度表
# 数据为通行的紫微斗数安星亮度表（各派系略有差异，取常见版本）
# ============================================================
BRIGHT_ORDER = ["庙", "旺", "得", "利", "平", "不", "陷"]
BRIGHT_DESC = {
    "庙": "能量巅峰状态，曜正面特质发挥到极致",
    "旺": "次强状态，亮度高，表现亮眼",
    "得": "亮度中上，能正常发挥",
    "利": "亮度中等，不功不过",
    "平": "亮度平平，特质趋于平淡",
    "不": "不得地，亮度偏暗，特质发挥受阻",
    "陷": "落陷，星曜至暗，多以功课与提醒的方式呈现",
}

BRIGHTNESS = {
    "紫微": {"子": "平", "丑": "庙", "寅": "庙", "卯": "旺", "辰": "得", "巳": "旺",
             "午": "庙", "未": "庙", "申": "旺", "酉": "平", "戌": "得", "亥": "旺"},
    "天机": {"子": "庙", "丑": "陷", "寅": "得", "卯": "旺", "辰": "利", "巳": "平",
             "午": "庙", "未": "陷", "申": "得", "酉": "旺", "戌": "利", "亥": "平"},
    "太阳": {"子": "陷", "丑": "陷", "寅": "旺", "卯": "庙", "辰": "旺", "巳": "旺",
             "午": "庙", "未": "得", "申": "得", "酉": "平", "戌": "陷", "亥": "陷"},
    "武曲": {"子": "旺", "丑": "庙", "寅": "得", "卯": "利", "辰": "庙", "巳": "平",
             "午": "旺", "未": "庙", "申": "得", "酉": "利", "戌": "庙", "亥": "平"},
    "天同": {"子": "旺", "丑": "陷", "寅": "利", "卯": "平", "辰": "平", "巳": "庙",
             "午": "陷", "未": "陷", "申": "旺", "酉": "平", "戌": "平", "亥": "庙"},
    "廉贞": {"子": "利", "丑": "利", "寅": "庙", "卯": "平", "辰": "利", "巳": "平",
             "午": "平", "未": "利", "申": "庙", "酉": "平", "戌": "利", "亥": "陷"},
    "天府": {"子": "庙", "丑": "庙", "寅": "庙", "卯": "得", "辰": "庙", "巳": "得",
             "午": "旺", "未": "庙", "申": "得", "酉": "旺", "戌": "庙", "亥": "得"},
    "太阴": {"子": "庙", "丑": "庙", "寅": "陷", "卯": "陷", "辰": "陷", "巳": "陷",
             "午": "陷", "未": "平", "申": "利", "酉": "旺", "戌": "旺", "亥": "庙"},
    "贪狼": {"子": "旺", "丑": "庙", "寅": "平", "卯": "利", "辰": "庙", "巳": "利",
             "午": "旺", "未": "庙", "申": "平", "酉": "利", "戌": "庙", "亥": "旺"},
    "巨门": {"子": "旺", "丑": "陷", "寅": "庙", "卯": "庙", "辰": "平", "巳": "利",
             "午": "旺", "未": "陷", "申": "庙", "酉": "庙", "戌": "平", "亥": "旺"},
    "天相": {"子": "庙", "丑": "庙", "寅": "庙", "卯": "陷", "辰": "得", "巳": "得",
             "午": "庙", "未": "庙", "申": "庙", "酉": "陷", "戌": "得", "亥": "得"},
    "天梁": {"子": "庙", "丑": "旺", "寅": "庙", "卯": "庙", "辰": "庙", "巳": "陷",
             "午": "庙", "未": "旺", "申": "陷", "酉": "得", "戌": "庙", "亥": "陷"},
    "七杀": {"子": "旺", "丑": "庙", "寅": "庙", "卯": "陷", "辰": "庙", "巳": "平",
             "午": "旺", "未": "庙", "申": "庙", "酉": "陷", "戌": "庙", "亥": "平"},
    "破军": {"子": "庙", "丑": "旺", "寅": "得", "卯": "陷", "辰": "旺", "巳": "平",
             "午": "庙", "未": "旺", "申": "得", "酉": "陷", "戌": "旺", "亥": "平"},
}


# 生年四化 / 流年四化通用标签与含义（十天干四化表见 bazi.SIHUA）
SIHUA_LABELS = ["化禄", "化权", "化科", "化忌"]
SIHUA_MEANING = {
    "化禄": "财富与福气（主收获、人缘）",
    "化权": "权力与能力（主事业、进取）",
    "化科": "名声与贵人（主学业、口碑）",
    "化忌": "执着与课题（主消耗、学会放手）",
}


def star_brightness(star: str, zhi: str) -> dict:
    """查询星曜在某地支的亮度。返回 {level, rank, desc}（rank 0最亮）"""
    raw = (BRIGHTNESS.get(star) or {}).get(zhi, "平")
    level = raw if raw in BRIGHT_ORDER else "平"
    rank = BRIGHT_ORDER.index(level)
    return {"level": level, "rank": rank, "desc": BRIGHT_DESC[level]}

# 五行局速查：纳音五行 → 局数
_JU = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
_JU_NAME = {2: "水二局", 3: "木三局", 4: "金四局", 5: "土五局", 6: "火六局"}

# 六十甲子纳音（每两组干支配一条）
_NAYIN = ["金", "火", "木", "土", "金", "火", "木", "土", "金", "木",
          "水", "土", "火", "木", "水", "金", "火", "水", "土", "金",
          "木", "水", "土", "金", "木", "水", "土", "火", "木", "水"]


# ============================================================
# 辅星系统：六吉星 / 六煞星 / 禄存 / 天马
# ============================================================
AUX_STARS = {
    # 六吉星
    "文昌": {"type": "吉", "role": "文星", "trait": "聪明好学、文书逻辑强", "hint": "才华要落在输出上"},
    "文曲": {"type": "吉", "role": "艺星", "trait": "口才艺术、感受力细腻", "hint": "感性是你的第二引擎"},
    "左辅": {"type": "吉", "role": "辅佐", "trait": "有贵人缘、乐于助人有分寸", "hint": "接受帮助也是修炼"},
    "右弼": {"type": "吉", "role": "辅佐", "trait": "温和圆融、暗中支持他人", "hint": "被看见前先自己肯定自己"},
    "天魁": {"type": "吉", "role": "贵人", "trait": "长辈贵人运、逢难有助", "hint": "贵人在灯火阑珊处"},
    "天钺": {"type": "吉", "role": "贵人", "trait": "平辈贵人运、机遇自来", "hint": "留一次机会给主动"},
    # 六煞星
    "擎羊": {"type": "煞", "role": "刀刃", "trait": "冲劲强、刀子嘴的行动派", "hint": "锋利留给事，温柔留给人"},
    "陀罗": {"type": "煞", "role": "纠缠", "trait": "韧性固执、事情容易拖磨", "hint": "区分坚持与内耗"},
    "火星": {"type": "煞", "role": "爆发", "trait": "急性子、说来就来的火", "hint": "火用来点灯不用来烧桥"},
    "铃星": {"type": "煞", "role": "隐火", "trait": "闷烧型焦虑、暗自较劲", "hint": "把担忧写下来就小了一半"},
    "地空": {"type": "煞", "role": "空亡", "trait": "想法天马行空、易踩空", "hint": "想象力落地才是资产"},
    "地劫": {"type": "煞", "role": "劫夺", "trait": "得失波动、不按常理", "hint": "破而后立是另一种节奏"},
    # 禄存 / 天马
    "禄存": {"type": "吉", "role": "财禄", "trait": "稳财、坐守型资源", "hint": "守成的底气"},
    "天马": {"type": "吉", "role": "驿马", "trait": "奔波变动、动中得利", "hint": "走出去才有故事"},
}

# 禄存：年干 → 地支（禄前一位）
_LUCUN = {0: 1, 1: 3, 2: 5, 3: 7, 4: 9, 5: 11, 6: 1, 7: 3, 8: 5, 9: 7}
# 擎羊（禄前）/陀罗（禄后）
# 天马：年支三合局 → 驿马位（申子辰马在寅，寅午戌马在申，巳酉丑马在亥，亥卯未马在巳）
_TIANMA = {8: 2, 0: 2, 4: 2, 2: 8, 6: 8, 10: 8, 5: 11, 9: 11, 1: 11, 11: 5, 3: 5, 7: 5}
# 文昌：戌起子时逆数；文曲：辰起子时顺数
# 左辅：辰起正月顺数；右弼：戌起正月逆数
# 天魁/天钺：年干起重磅贵人位（通行口诀：甲戊庚牛羊，乙己鼠猴乡，丙丁猪鸡位，壬癸兔蛇藏，六辛逢马虎）
_KUI = {0: 1, 4: 1, 6: 1, 1: 0, 5: 0, 2: 11, 3: 11, 8: 3, 9: 3, 7: 6}   # 天魁地支
_YUE = {0: 7, 4: 7, 6: 7, 1: 8, 5: 8, 2: 9, 3: 9, 8: 5, 9: 5, 7: 2}     # 天钺地支


def _place_aux_stars(year_stem_i: int, year_zhi_i: int, hour_z: int, l_month: int) -> dict:
    """安辅星。返回 地支序 -> [星名] 的映射。"""
    aux: dict[int, list[str]] = {}

    def put(z, star):
        aux.setdefault(z % 12, []).append(star)

    # 文昌（戌=10 起子时，逆数到生时）
    put(10 - hour_z, "文昌")
    # 文曲（辰=4 起子时，顺数到生时）
    put(4 + hour_z, "文曲")
    # 左辅（辰=4 起正月，顺数到生月）
    put(4 + (l_month - 1), "左辅")
    # 右弼（戌=10 起正月，逆数到生月）
    put(10 - (l_month - 1), "右弼")
    # 天魁/天钺（按年干）
    put(_KUI.get(year_stem_i, 1), "天魁")
    put(_YUE.get(year_stem_i, 7), "天钺")
    # 禄存与擎羊/陀罗
    lucun = _LUCUN.get(year_stem_i, 1)
    put(lucun, "禄存")
    put(lucun + 1, "擎羊")
    put(lucun - 1, "陀罗")
    # 火星/铃星（年支起子时顺数至生时；申子辰人起寅、寅午戌起申、巳酉丑起卯、亥卯未起酉——通行简化：按年支三合的庙旺位起）
    fire_base = {8: 2, 0: 2, 4: 2, 2: 8, 6: 8, 10: 8,
                 5: 3, 9: 3, 1: 3, 11: 9, 3: 9, 7: 9}[year_zhi_i]
    put(fire_base + hour_z, "火星")
    put(fire_base - hour_z, "铃星")
    # 地空/地劫（亥=11 起子时，顺数至生时：地劫；逆数：地空）
    put(11 + hour_z, "地劫")
    put(11 - hour_z, "地空")
    # 天马（年支三合 → 驿马位）
    put(_TIANMA.get(year_zhi_i, 2), "天马")
    return aux


def _jieqi_year_stem(lunar) -> str:
    """取节气年干（以立春为界的年干支首位）"""
    return lunar.getYearInGanZhi()[0]


def _hour_branch(hour: int) -> int:
    """小时 → 时支序（子=0）；23 点归子时（次日由 lunar 处理）"""
    return ((hour + 1) // 2) % 12


# ============================================================
# 流年盘：以指定宫位为流年命宫重排十二宫
# ============================================================

def _build_liunian_pan(board: list[dict], liunian_gong_zhi: str,
                       liunian_year: int, source_palace: str = "") -> dict:
    """以指定宫位为流年命宫重排十二宫（流年盘）。

    传统规则：星曜按地支落位固定不动，十二宫名从流年命宫起逆布
    （与本命盘同向）；流年天干起四化，标注四化星落入流年盘哪一宫。
    解读切换为「某年」的时间视角，星情复用本命盘的安星结果。
    """
    from lunar_python import Solar as _Solar

    ln_zhi_i = ZHI.index(liunian_gong_zhi)

    # 流年干支（取该年年中的年柱，规避立春边界歧义）
    ln_gz = _Solar.fromYmd(liunian_year, 6, 1).getLunar().getYearInGanZhi()
    ln_stem = ln_gz[0]

    # 地支 -> 本命盘宫数据；星名 -> 所落地支（主星 + 辅星）
    by_zhi = {p["zhi"]: p for p in board}
    star_zhi: dict[str, str] = {}
    for p in board:
        for s in p["stars"]:
            star_zhi[s] = p["zhi"]
        for a in p.get("aux", []):
            star_zhi.setdefault(a["star"], p["zhi"])

    # 流年四化（流年天干查表）
    from .bazi import SIHUA as _SIHUA
    hua_stars = _SIHUA.get(ln_stem, [])
    sihua_by_zhi: dict[str, list[str]] = {}   # 地支 -> [「星名+化X」]
    sihua_items: list[str] = []
    for j, sname in enumerate(hua_stars):
        hua = SIHUA_LABELS[j]
        tag = f"{sname}{hua}"
        z = star_zhi.get(sname, "")
        if z:
            sihua_by_zhi.setdefault(z, []).append(tag)
            sihua_items.append(f"{tag}（落{z}宫）：{SIHUA_MEANING[hua]}")
        else:
            sihua_items.append(f"{tag}：{SIHUA_MEANING[hua]}")

    # 流年十二宫：从流年命宫起逆布（board 下标 i ↔ 地支序 ln_zhi_i - i）
    ln_board = []
    for i, name in enumerate(PALACES):
        zhi_idx = (ln_zhi_i - i) % 12
        zhi_char = ZHI[zhi_idx]
        src = by_zhi.get(zhi_char, {})
        stars = src.get("stars", [])
        bright = src.get("brightness", [])
        aux = src.get("aux", [])
        theme = PALACE_THEME[name]

        # 三方四正（基于流年盘自身下标：下标 = (ln_zhi_i - 地支序) % 12）
        he1 = (ln_zhi_i - (zhi_idx + 4) % 12) % 12
        he2 = (ln_zhi_i - (zhi_idx + 8) % 12) % 12
        dui = (ln_zhi_i - (zhi_idx + 6) % 12) % 12

        # 流年语境解读
        if stars:
            lead = STARS[stars[0]]
            interp = f"今年你的{theme[0]}走「{lead['role']}」路线——{lead['trait']}。"
            if bright:
                top = min(bright, key=lambda b: b["rank"])
                if top["rank"] <= 1:
                    interp += f"{top['star']}{top['level']}入此宫，状态在线，全年可持续发力。"
                elif any(b["level"] == "陷" for b in bright):
                    dim = next(b for b in bright if b["level"] == "陷")
                    interp += f"{dim['star']}落陷于此，今年这一格偏慢热，属于「慢工出细活」的领域。"
            tips = " ".join(STARS[s]["hint"] for s in stars[:2])
        else:
            dui_src = by_zhi.get(ZHI[(zhi_idx + 6) % 12], {})
            dui_label = "、".join(dui_src.get("stars", [])) or "对宫"
            interp = (f"今年{theme[0]}无主星坐镇，节奏随大环境与身边人起伏；"
                      f"可参考对宫（{dui_label}）的动向，顺势而为。")
            tips = "今年这一格以稳为主，不必刻意强求。"

        # 四化落宫说明
        hua_here = sihua_by_zhi.get(zhi_char, [])
        if hua_here:
            interp += (" 流年" + "、".join(hua_here) + "落此宫——"
                       + "；".join(SIHUA_MEANING[t[-2:]] for t in hua_here)
                       + "，是今年有明确事件感的一格。")

        # 辅星温和提示
        if aux:
            lucky = [a for a in aux if a["type"] == "吉"]
            harsh = [a for a in aux if a["type"] == "煞"]
            aux_parts = []
            if lucky:
                aux_parts.append("吉星相伴（" + "、".join(a["star"] for a in lucky) + "）添助力")
            if harsh:
                aux_parts.append("煞星提醒（" + "、".join(a["star"] for a in harsh) + "）注意别被冲劲带偏")
            interp += " " + "；".join(aux_parts) + "。"

        ln_board.append({
            "palace": f"流年{name}", "zhi": zhi_char, "stars": stars,
            "stars_label": "、".join(stars) if stars else "空宫",
            "theme": theme[0], "interpretation": interp, "tips": tips,
            "brightness": bright, "aux": aux,
            "index": i,
            "sanfang": {"he": [he1, he2], "dui": dui},
            "sihua": hua_here,
            "is_ming": i == 0,
        })

    return {
        "year": liunian_year,
        "gz": ln_gz,
        "year_stem": ln_stem,
        "ming_zhi": ZHI[ln_zhi_i],
        "source_palace": source_palace,
        "note": (f"流年盘以{ZHI[ln_zhi_i]}宫为流年命宫，十二宫围绕它重排；星曜仍按地支落位，"
                 f"解读切换为「{liunian_year}年（{ln_gz}）」的时间视角。"),
        "sihua": {"items": sihua_items, "by_zhi": sihua_by_zhi},
        "board": ln_board,
    }


def analyze(birth_date: str, birth_hour: int | None, gender: str = "女",
            liunian_gong_zhi: str | None = None,
            liunian_year: int | None = None) -> dict:
    """排紫微命盘（简化主星盘）。返回：命宫信息、五行局、十二宫、解读。"""
    dt = datetime.strptime(birth_date, "%Y-%m-%d")
    if birth_hour is None:
        birth_hour = 12
    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, birth_hour, 0, 0)
    lunar = solar.getLunar()

    l_month = abs(lunar.getMonth())  # 闰月简化取当月
    l_day = lunar.getDay()
    hour_z = _hour_branch(birth_hour)
    year_stem = GAN.index(_jieqi_year_stem(lunar))
    shengxiao = SHENGXIAO[ZHI.index(lunar.getYearInGanZhi()[1])]

    # 命宫 / 身宫：寅起正月，顺数至生月；再从生月起子时，逆（命）/ 顺（身）数至生时
    ming_off = (2 + (l_month - 1) - hour_z) % 12    # 以子=0 计的地支序
    shen_off = (2 + (l_month - 1) + hour_z) % 12
    ming_zhi = ming_off                              # 地支序即下标

    # 命宫天干：五虎遁（甲己年丙寅起）
    yin_stem = (year_stem % 5) * 2 + 2               # 寅月天干
    ming_gan = (yin_stem + (ming_off - 2)) % 10
    mgz = GAN[ming_gan] + ZHI[ming_zhi]

    # 五行局：命宫干支纳音
    No = None
    for i in range(60):
        if GAN[i % 10] == GAN[ming_gan] and ZHI[i % 12] == ZHI[ming_zhi]:
            No = i
            break
    nayin = _NAYIN[No // 2] if No is not None else "水"
    ju = _JU[nayin]

    # 安紫微（借数法）
    d, j = l_day, ju
    if d % j == 0:
        base = d // j - 1
    else:
        borrow = j - (d % j)
        base = (d + borrow) // j - 1
        base = base - borrow if borrow % 2 == 1 else base + borrow
    ziwei_off = (2 + base) % 12                      # 地支序

    # 安星
    positions: dict[str, list[str]] = {}             # 地支序 -> 星列表
    def put(zhi_idx, star):
        positions.setdefault(zhi_idx % 12, []).append(star)

    tianfu_off = (2 + (-(ziwei_off - 2))) % 12
    put(ziwei_off, "紫微")
    put(ziwei_off - 1, "天机")
    put(ziwei_off - 3, "太阳")
    put(ziwei_off - 4, "武曲")
    put(ziwei_off - 5, "天同")
    put(ziwei_off - 8, "廉贞")
    put(tianfu_off, "天府")
    put(tianfu_off + 1, "太阴")
    put(tianfu_off + 2, "贪狼")
    put(tianfu_off + 3, "巨门")
    put(tianfu_off + 4, "天相")
    put(tianfu_off + 5, "天梁")
    put(tianfu_off + 6, "七杀")
    put(tianfu_off + 10, "破军")

    # 辅星（六吉六煞 + 禄存天马）：单独映射，主星与辅星分层存储
    year_zhi = ZHI.index(lunar.getYearInGanZhi()[1])
    aux_positions = _place_aux_stars(year_stem, year_zhi, hour_z, l_month)

    # 大限方向与流年信息（供卡片标记）
    year_stem_char_pre = _jieqi_year_stem(lunar)
    _YANG = {"甲", "丙", "戊", "庚", "壬"}
    is_yang_stem = year_stem_char_pre in _YANG
    # 阳男阴女顺行（board 序号递减方向），阴男阳女逆行（序号递增）
    daxian_forward = (is_yang_stem and gender == "男") or (not is_yang_stem and gender == "女")

    # 流年（真实当前年份的干支）
    from datetime import datetime as _dt
    from lunar_python import Solar as _Solar
    _now = _dt.now()
    _now_lunar = _Solar.fromYmd(_now.year, _now.month, _now.day).getLunar()
    liunian_gz = _now_lunar.getYearInGanZhi()
    liunian_zhi = liunian_gz[1]
    birth_year = int(birth_date[:4])
    now_age = _now.year - birth_year
    # 出生年的地支序（用于推算各宫的流年年龄，按公历年支轮转）
    birth_year_zhi_i = (birth_year - 4) % 12

    # 十二宫（命宫起逆布：地支序递减）
    board = []
    ming_stars = None

    def _board_idx_of(zhi_val: int) -> int:
        """地支序 → board 下标"""
        return (ming_zhi - zhi_val) % 12

    for i, name in enumerate(PALACES):
        zhi_idx = (ming_zhi - i) % 12
        stars = positions.get(zhi_idx, [])
        if i == 0:
            ming_stars = stars
        theme = PALACE_THEME[name]
        zhi_char = ZHI[zhi_idx]

        # 三方四正：本宫 + 两三合（zhi±4）+ 对宫（zhi±6），存 board 下标
        he1_i = _board_idx_of((zhi_idx + 4) % 12)
        he2_i = _board_idx_of((zhi_idx + 8) % 12)
        dui_i = _board_idx_of((zhi_idx + 6) % 12)

        # 大限：第 d 步大限落在本宫，年龄段 [ju+10d, ju+10d+9]
        d = ((12 - i) % 12) if daxian_forward else i
        dx_from = ju + 10 * d
        dx_to = dx_from + 9

        # 每颗星带亮度
        bright_list = []
        aux_here = aux_positions.get(zhi_idx, [])
        aux_info = [{"star": s, "type": AUX_STARS[s]["type"],
                     "role": AUX_STARS[s]["role"], "trait": AUX_STARS[s]["trait"]}
                    for s in aux_here]
        if stars:
            names = "、".join(stars)
            readings = []
            for s in stars:
                st = STARS[s]
                br = star_brightness(s, zhi_char)
                bright_list.append({"star": s, **br})
                bright_tag = f"{s}{br['level']}"
                readings.append(f"{bright_tag}（{st['role']}）的「{st['trait']}」落在{theme[0]}上")
            interp = "；".join(readings) + "。"
            # 亮度备注
            top_br = sorted(bright_list, key=lambda b: b["rank"])[0]
            if top_br["rank"] <= 1:
                interp += f" 其中{top_br['star']}{top_br['level']}——{top_br['desc']}，这颗星的良好特质是该领域的亮点。"
            elif any(b["level"] == "陷" for b in bright_list):
                dim = [b for b in bright_list if b["level"] == "陷"][0]
                interp += f" 其中{dim['star']}落陷——不必担心，这更多是一份提醒：该领域需要你多花一点耐心经营。"
            tips = " ".join(STARS[s]["hint"] for s in stars[:2])
        else:
            names = "空宫"
            interp = (f"此宫无主星，性质偏向单纯直接，{theme[1]}；"
                      f"解读时可参考对宫（{PALACE_THEME[PALACES[(i + 6) % 12]][0]}）的星情。")
            tips = "不必刻意填满，简单也是一种礼物。"
        # 辅星解读（吉星助力 / 煞星提醒，均温和表述）
        if aux_info:
            lucky = [a for a in aux_info if a["type"] == "吉"]
            harsh = [a for a in aux_info if a["type"] == "煞"]
            aux_parts = []
            if lucky:
                aux_parts.append("吉星相伴：" + "、".join(
                    f"{a['star']}（{a['trait']}）" for a in lucky) + "，为这个领域添助力")
            if harsh:
                aux_parts.append("煞星提醒：" + "、".join(
                    f"{a['star']}（{a['trait']}）" for a in harsh) + "，注意别被冲劲带偏")
            interp += " " + "；".join(aux_parts) + "。"
        # 流年年龄：此宫每隔 12 年轮一次流年命宫
        first_ln_age = (zhi_idx - birth_year_zhi_i) % 12
        liunian_ages = [first_ln_age + 12 * k for k in range(8)
                        if first_ln_age + 12 * k <= 96]
        liunian_upcoming = [a for a in liunian_ages if a >= now_age][:3]

        board.append({
            "palace": name, "zhi": zhi_char, "stars": stars,
            "stars_label": names, "theme": theme[0], "interpretation": interp, "tips": tips,
            "brightness": bright_list,
            "aux": aux_info,
            "aux_label": "、".join(aux_here) if aux_here else "",
            "index": i,
            # 三方四正（board 下标，含本宫共四宫）
            "sanfang": {"he": [he1_i, he2_i], "dui": dui_i},
            # 大限
            "daxian": {"range": f"{dx_from}-{dx_to}", "from": dx_from, "to": dx_to,
                       "current": dx_from <= now_age <= dx_to},
            # 流年命宫标记（年支落此宫）
            "is_liunian": zhi_char == liunian_zhi,
            # 流年年龄（该宫成为流年命宫的年龄列表，12 年一循环）
            "liunian_ages": liunian_ages,
            "liunian_upcoming": liunian_upcoming,
            "is_ming": i == 0, "is_body": zhi_idx == shen_off,
        })

    # 生年四化（从年天干查表，标注每颗星附带哪个化）
    year_stem_char = _jieqi_year_stem(lunar)
    from .bazi import SIHUA as _SIHUA
    sihua_stars = _SIHUA.get(year_stem_char, [])  # [禄星,权星,科星,忌星] 的星名
    # 给每颗星标注四化
    for zhi_idx, stars in positions.items():
        for star in stars:
            for j, sname in enumerate(sihua_stars):
                if star == sname:
                    # 在解读中加入四化标注
                    pass

    # 构建每颗星的四化映射 {星名: 化X}
    star_sihua = {}
    for j, sname in enumerate(sihua_stars):
        if sname:
            star_sihua[sname] = SIHUA_LABELS[j]

    # 在 board 中标注四化
    for p in board:
        for s in p.get("stars", []):
            if s in star_sihua:
                hua = star_sihua[s]
                p.setdefault("sihua", []).append(f"{s}{hua}")
                p["interpretation"] += (
                    f" 此星带{hua}：{SIHUA_MEANING[hua]}。"
                    if hua == "化忌" else
                    f" 此星带{hua}（{SIHUA_MEANING[hua]}），能量有加持。"
                )

    # 生年四化摘要
    sihua_summary = []
    for j, sname in enumerate(sihua_stars):
        if sname and sname in STARS:
            sihua_summary.append(f"{sname}{SIHUA_LABELS[j]}：{SIHUA_MEANING[SIHUA_LABELS[j]]}")
        elif sname:
            sihua_summary.append(f"{sname}{SIHUA_LABELS[j]}（非主星，影响辅助面向）")

    # 命宫主格速写（先构建基础文案，再附加四化说明）
    if ming_stars:
        lead = STARS[ming_stars[0]]
        ming_summary = (f"命宫{ZHI[ming_zhi]}宫坐{'、'.join(ming_stars)}，"
                        f"核心气质是「{lead['role']}型」——{lead['trait']}。{lead['hint']}。")
    else:
        ming_summary = (f"命宫{ZHI[ming_zhi]}宫为空宫，性格底色灵活多变，"
                        f"容易受环境与身边人影响，适应性是你的天赋。")
    if len(ming_stars or []) > 1:
        ming_summary += "（主星成对，性格层次更丰富，不同面向在不同场合切换。）"

    # 命宫四化附加说明（放在 ming_summary 定义之后，避免 UnboundLocalError）
    ming_sihua = [f"{s}{star_sihua[s]}" for s in (ming_stars or []) if s in star_sihua]
    if ming_sihua:
        ming_summary += f" 命宫带生年{'、'.join(ming_sihua)}，是本命的先天资源与课题。"

    result = {
        "meta": {
            "solar_date": birth_date,
            "lunar_date": f"农历{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
            "hour_zhi": ZHI[hour_z],
            "gender": gender,
            "shengxiao": shengxiao,
        },
        "sihua": {
            "year_stem": year_stem_char,
            "items": sihua_summary,
            "stars": star_sihua,
        },
        "ming": {
            "gong_zhi": ZHI[ming_zhi],
            "gong_gan_zhi": mgz,
            "body_zhi": ZHI[shen_off],
            "ju": _JU_NAME[ju],
            "stars": ming_stars or [],
            "summary": ming_summary,
        },
        "daxian": {
            "direction": "顺行" if daxian_forward else "逆行",
            "start_age": ju,          # 起运岁数 = 局数
            "age": now_age,
        },
        "liunian": {
            "gz": liunian_gz,
            "zhi": liunian_zhi,
            "age": now_age,
        },
        "board": board,
        "disclaimer": "紫微排盘为传统安星规则的简化主星盘，解读是通俗模板，仅供娱乐参考。",
    }

    # 流年盘：指定宫位为流年命宫时重排十二宫（点击宫位触发）
    ln_gong = (liunian_gong_zhi or "").strip()
    if ln_gong in ZHI:
        from datetime import datetime as _dt2
        ln_year = int(liunian_year) if liunian_year else _dt2.now().year
        if not (1850 <= ln_year <= 2100):
            ln_year = _dt2.now().year
        src_name = next((p["palace"] for p in board if p["zhi"] == ln_gong), "")
        result["liunian_pan"] = _build_liunian_pan(board, ln_gong, ln_year, src_name)

    return result
