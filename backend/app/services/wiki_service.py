# -*- coding: utf-8 -*-
"""用户记忆维基服务（LLM Wiki 范式，参考 Karpathy 2026 提出的「知识编译器」思路）。

职责：把对话原始材料「编译」为结构化、可积累、用户可纠错的事实条目，
并渲染为注入角色提示词的记忆卡。

双通道（与项目既有双引擎一致）：
  - LLM 编译：配置大模型后，按批次抽取/合并/更新条目（新增、补强、修订）
  - 规则编译：未配置时兜底——自述句式抽取 + 高频话题沉淀，保证维基不空、开箱即用

设计原则：
  1. 事实必须带 evidence（原话片段），用户可核实可删除；
  2. 冲突以新信息修订旧信息（保留 evidence），不盲目堆叠；
  3. 编译异步执行，绝不阻塞聊天回复；
  4. 注入提示词时按 category 分组、限量，控制 token 成本。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ChatSession, Message, UserWikiEntry

CATEGORIES = ["基本情况", "学业职业", "重要他人", "喜好偏好", "目标计划", "健康情况", "情绪背景"]

# 每隔多少条用户消息触发一次编译
EXTRACT_EVERY = 6
# 注入提示词时每个分类的条目上限
INJECT_PER_CATEGORY = 3

# ---------------- 规则通道：自述句式抽取（离线兜底） ----------------
_PUNCT = "，。！？、；：,.!? "
_JOB_WORDS = ("老师|医生|护士|程序员|工程师|设计师|产品经理|会计|律师|销售|"
              "公务员|研究员|研究生|本科生|上班族|自由职业者|创业者")
_RULE_PATTERNS = [
    # (category, key, 正则, 说明模板：{0}=捕获组)
    ("基本情况", "年龄段", r"我(?:今年)?(\d{2})岁", "用户 {0} 岁左右"),
    ("基本情况", "居住地", r"(?:住在|生活在|坐标)([一-龥]{2,6}?)(?=[，。！？\s]|$)", "用户居住在{0}"),
    ("学业职业", "职业", rf"我是一?(?:名|个)?({_JOB_WORDS})", "用户的职业是{0}"),
    ("学业职业", "就读学校", r"我在([一-龥]{2,12}(?:大学|学院|中学|小学))(?:读书|上学|读研|念书)?", "用户就读于{0}"),
    ("学业职业", "备考方向", r"(?:准备|备考|在考|想考)(考研|考公|法考|托福|雅思|高考|教资|CPA|执业医师)", "用户正在备考{0}"),
    ("学业职业", "工作状态", r"(?:最近)?(?:刚|被|要)?(?:换了?工作|入职|离职|跳槽|升职|被裁|失业)", "用户近期工作有变动"),
    ("重要他人", "养的宠物", r"养了?一?(?:只|个)?(猫|狗|仓鼠|兔子|乌龟|鸟|鱼)", "用户养了{0}"),
    ("重要他人", "宠物名字", r"(?:猫|狗|仓鼠|兔子|它|名字)叫([\u4e00-\u9fa5A-Za-z]{1,6}?)(?=[，。！？\s]|$)", "用户的宠物叫{0}"),
    ("重要他人", "家庭角色", r"我(?:是(?:一个)?)?(宝妈|奶爸|妈妈|爸爸|独生女|独生子)", "用户是{0}"),
    ("重要他人", "婚恋状态", r"我(?:是)?(?:单身|未婚|已婚|在(?:谈)?恋爱)(?=[，。！？\s]|$)", "用户目前的感情状况曾提及"),
    ("重要他人", "在乎的人", r"我(?:的)(妈妈|爸爸|男朋友|女朋友|老公|老婆|室友|闺蜜|好友|导师|老板|领导)(?:[^，。！？]{0,10})", "用户提到过其{0}"),
    ("目标计划", "近期目标", r"我想(?:要|准备|打算)?([^，。！？]{2,18}?)(?=[，。！？\s]|$)", "用户想要{0}"),
    ("健康情况", "睡眠困扰", r"(?:睡不(?:着|好)|失眠|熬夜)", "用户存在睡眠困扰"),
    ("健康情况", "身体不适", r"([一-龥]{2,4}(?:头疼|头痛|胃疼|胃痛|腰疼|牙疼|不舒服))(?=[，。！？\s]|$)", "用户身体不适：{0}"),
    ("喜好偏好", "喜欢的事", r"我(?:很)?(?:喜欢|爱)([^，。！？、]{2,14}?)(?=[，。！？\s]|$)", "用户喜欢{0}"),
    ("喜好偏好", "讨厌的事", r"我(?:最)?(?:讨厌|不喜欢|受不了)([^，。！？、]{2,14}?)(?=[，。！？\s]|$)", "用户不喜欢{0}"),
]


def _rule_extract(text: str) -> list[dict]:
    """用自述句式抽取候选事实（离线兜底通道）。"""
    import re
    found = []
    for category, key, pattern, tpl in _RULE_PATTERNS:
        m = re.search(pattern, text)
        if not m:
            continue
        cap = m.group(1).strip() if m.groups() else ""
        if m.groups() and (not cap or cap in _PUNCT):
            continue
        value = tpl.format(cap) if cap else tpl.format(text[:12])
        found.append({
            "category": category,
            "key": key,
            "value": value,
            "evidence": text[:60],
            "confidence": 0.55,
        })
    return found


# ---------------- LLM 通道：结构化抽取与合并 ----------------
_LLM_PROMPT = """你是用户记忆维基的「知识编译器」。根据最近对话，抽取关于该用户的稳定事实（今天的心情不算，长期成立的才算）。

【已有维基条目】
{existing}

【最近对话】
{dialog}

只输出 JSON，不要解释：
{{"new": [{{"category": "基本情况|学业职业|重要他人|喜好偏好|目标计划|健康情况|情绪背景",
  "key": "简短标签(≤8字)", "value": "一句事实描述", "evidence": "原话片段", "confidence": 0.0到1.0}}],
 "update": [{{"existing_key": "已有条目的key", "value": "修订后的事实", "evidence": "新依据"}}]}}

要求：
- new 只收稳定事实（身份/关系/目标/偏好/健康习惯），不收临时情绪；
- 已有条目有新进展时放 update（如备考目标完成、换工作），不要重复新增；
- evidence 必须是对话原话片段（≤40字）；
- 没有可抽取的就输出 {{"new": [], "update": []}}。"""


def _llm_configured() -> bool:
    return bool(settings.LLM_ENABLED and settings.LLM_API_KEY)


async def _llm_extract(dialog: str, existing: str) -> dict | None:
    """调用 LLM 编译；失败返回 None（由规则通道兜底）。"""
    if not _llm_configured():
        return None
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": "你是严谨的信息抽取器，只输出 JSON。"},
            {"role": "user",
             "content": _LLM_PROMPT.format(existing=existing or "（空）", dialog=dialog)},
        ],
        "temperature": 0.2,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            return None
        data = json.loads(cleaned[start:end + 1])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


# ---------------- 写入合并 ----------------
def _merge_entry(db: Session, user_id: int, item: dict, source: str) -> None:
    """合并单条事实：已存在且一致则增强（hits+1 / confidence 上升），冲突则修订。"""
    key = (item.get("key") or "").strip()[:120]
    value = (item.get("value") or "").strip()
    if not key or not value:
        return
    category = item.get("category") if item.get("category") in CATEGORIES else "情绪背景"
    evidence = (item.get("evidence") or "").strip()[:200]

    old = (db.query(UserWikiEntry)
           .filter(UserWikiEntry.user_id == user_id, UserWikiEntry.key == key)
           .first())
    if old is None:
        db.add(UserWikiEntry(
            user_id=user_id, category=category, key=key, value=value,
            evidence=evidence, source=source,
            confidence=min(0.95, float(item.get("confidence", 0.6))),
        ))
        return
    # 同 key：新值不同 → 修订（保留新依据）；相同 → 增强置信度
    if old.value != value:
        old.value = value
        old.evidence = evidence or old.evidence
        old.updated_at = datetime.now(timezone.utc)
        old.source = source
    else:
        old.hits = (old.hits or 1) + 1
        old.confidence = min(0.95, (old.confidence or 0.6) + 0.06 * (old.hits / 10))


def apply_updates(db: Session, user_id: int, updates: list[dict]) -> None:
    for u in updates or []:
        key = (u.get("existing_key") or u.get("key") or "").strip()
        value = (u.get("value") or "").strip()
        if not key or not value:
            continue
        old = (db.query(UserWikiEntry)
               .filter(UserWikiEntry.user_id == user_id, UserWikiEntry.key == key)
               .first())
        if old:
            old.value = value
            old.evidence = (u.get("evidence") or old.evidence)[:200]
            old.updated_at = datetime.now(timezone.utc)


async def compile_wiki(db: Session, user_id: int) -> int:
    """编译一轮：取该用户最近对话窗口 → LLM/规则抽取 → 合并入库。返回新增/更新条数。"""
    messages = (db.query(Message)
                .join(ChatSession, ChatSession.id == Message.session_id)
                .filter(Message.role == "user", ChatSession.user_id == user_id)
                .order_by(Message.created_at.desc())
                .limit(24).all())
    messages.reverse()
    if not messages:
        return 0
    dialog = "\n".join(m.content for m in messages if m.content)[:2400]
    if not dialog.strip():
        return 0

    entries = (db.query(UserWikiEntry)
               .filter(UserWikiEntry.user_id == user_id)
               .order_by(UserWikiEntry.confidence.desc())
               .limit(40).all())
    existing = "\n".join(f"- [{e.category}] {e.key}：{e.value}" for e in entries)

    changed = 0
    data = await _llm_extract(dialog, existing)
    if data is not None:
        for item in data.get("new", []):
            _merge_entry(db, user_id, item, "llm")
            changed += 1
        apply_updates(db, user_id, data.get("update", []))
        changed += len(data.get("update", []) or [])
    else:
        # 规则兜底：只看最近几条，避免把已沉淀的旧句式反复抽取
        for m in messages[-4:]:
            for item in _rule_extract(m.content or ""):
                db_copy_ok = True  # 合并逻辑内部已防重复
                _merge_entry(db, user_id, item, "rule")
                changed += 1
    if changed:
        db.commit()
    return changed


def maybe_compile_async(db_session_factory, user_id: int, user_message_count: int) -> None:
    """每 EXTRACT_EVERY 条消息触发后台编译（不阻塞回复）。"""
    if user_message_count % EXTRACT_EVERY != 0:
        return

    async def _job():
        db = db_session_factory()
        try:
            await compile_wiki(db, user_id)
        except Exception:
            db.rollback()
        finally:
            db.close()

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_job())
    except RuntimeError:
        asyncio.run(_job())


# ---------------- 读取与注入 ----------------
def get_wiki(db: Session, user_id: int, limit: int = 60) -> list[dict]:
    rows = (db.query(UserWikiEntry)
            .filter(UserWikiEntry.user_id == user_id)
            .order_by(UserWikiEntry.pinned.desc(),
                      UserWikiEntry.confidence.desc(),
                      UserWikiEntry.updated_at.desc())
            .limit(limit).all())
    return [{
        "id": r.id, "category": r.category, "key": r.key, "value": r.value,
        "evidence": r.evidence, "source": r.source,
        "confidence": round(r.confidence or 0.6, 2),
        "pinned": bool(r.pinned), "hits": r.hits or 1,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    } for r in rows]


def render_wiki_markdown(db: Session, user_id: int) -> str:
    """渲染为 markdown（管理端/前端展示用）。"""
    entries = get_wiki(db, user_id)
    if not entries:
        return "_（记忆维基尚为空——多聊聊，与你有关的重要事实会沉淀在这里）_"
    lines = []
    for cat in CATEGORIES:
        items = [e for e in entries if e["category"] == cat]
        if not items:
            continue
        lines.append(f"## {cat}")
        for e in items[:INJECT_PER_CATEGORY * 2]:
            mark = "📌 " if e["pinned"] else ""
            lines.append(f"- {mark}{e['key']}：{e['value']}  \n  <sub>依据：{e['evidence']} · 置信 {e['confidence']}</sub>")
        lines.append("")
    return "\n".join(lines)


def build_wiki_prompt(db: Session, user_id: int) -> str:
    """渲染注入角色提示词的记忆卡（压缩版，控制 token）。"""
    entries = get_wiki(db, user_id, limit=36)
    if not entries:
        return ""
    by_cat: dict[str, list[dict]] = {}
    for e in entries:
        by_cat.setdefault(e["category"], []).append(e)
    lines = ["【用户记忆维基（长期事实，不是本次对话内容）】"]
    for cat, items in by_cat.items():
        shown = "；".join(f"{e['key']}：{e['value']}" for e in items[:INJECT_PER_CATEGORY])
        lines.append(f"- {cat}｜{shown}")
    lines.append("使用方式：像老朋友记事一样在合适时机自然引用（如「你家猫最近还闹吗」），不要罗列，不要说「根据你的资料」。若信息与用户当下说的冲突，以用户当下说的为准。")
    return "\n".join(lines)
