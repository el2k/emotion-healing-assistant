# -*- coding: utf-8 -*-
"""新功能测试：长周期画像、每日小结、AI洞察、图片上传。"""
import io
import os
import tempfile
import time

from fastapi.testclient import TestClient

os.environ["DB_PATH"] = os.path.join(
    tempfile.gettempdir(), f"test_feat_{int(time.time() * 1000)}.db")
# 测试隔离：禁用真实 LLM 调用（不消耗额度；LLM 链路用打桩单独测）
os.environ["LLM_ENABLED"] = "false"

# 测试环境放宽限流（TestClient 共享同一 IP，会触发注册/登录限流——
# 限流本身的正确性已在独立脚本中验证：第11次触发429）
from app.security.rate_limit import register_limiter, login_limiter, api_limiter  # noqa: E402
for _lim in (register_limiter, login_limiter, api_limiter):
    _lim.max_requests = 100000

from app.main import app  # noqa: E402


def _token(client, phone):
    r = client.post("/api/auth/register", json={"phone": phone, "password": "pass123",
                                                "nickname": "测试"})
    if r.status_code == 409:
        r = client.post("/api/auth/login", json={"phone": phone, "password": "pass123"})
    return r.json()["token"]


def test_profile_daily_insight(client):
    token = _token(client, "13911110000")
    h = {"Authorization": f"Bearer {token}"}
    sid = client.post("/api/chat/sessions", json={"title": "t"}, headers=h).json()["id"]

    for text in ["今天很焦虑，睡不着", "工作压力好大，好累", "老板夸我了，很开心！",
                 "一个人好孤独"]:
        client.post(f"/api/chat/sessions/{sid}/messages",
                    json={"content": text}, headers=h)

    r = client.get("/api/emotion/profile?days=90", headers=h)
    assert r.status_code == 200, r.text
    prof = r.json()
    assert prof["total_records"] >= 4
    assert len(prof["distribution"]) >= 2
    assert prof["heatmap"] and prof["timeline"]
    assert prof["time_of_day"]

    r = client.get("/api/emotion/daily", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["count"] >= 1
    assert r.json()["push_text"]

    r = client.get("/api/emotion/insight?days=30", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["text"]
    assert r.json()["source"] in ("rule", "llm")


def test_image_upload_and_message(client):
    token = _token(client, "13922220000")
    h = {"Authorization": f"Bearer {token}"}
    # 造一个 1x1 PNG
    png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
           b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
           b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
    r = client.post("/api/chat/upload", headers=h,
                    files={"file": ("t.png", io.BytesIO(png), "image/png")})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith("/uploads/")

    sid = client.post("/api/chat/sessions", json={"title": "img"}, headers=h).json()["id"]
    r = client.post(f"/api/chat/sessions/{sid}/messages", headers=h,
                    json={"content": "", "msg_type": "image", "image_url": url})
    assert r.status_code == 200, r.text
    assert r.json()["user_message"]["image_url"] == url
    # 图片消息不应因内容为空而报错，且有回复
    assert r.json()["reply"]["content"]

    # 图片可访问
    r2 = client.get(url)
    assert r2.status_code == 200


def test_delete_and_logout_flow(client):
    token = _token(client, "13933330000")
    h = {"Authorization": f"Bearer {token}"}
    sid = client.post("/api/chat/sessions", json={"title": "del"}, headers=h).json()["id"]
    r = client.delete(f"/api/chat/sessions/{sid}", headers=h)
    assert r.status_code == 200
    r = client.get(f"/api/chat/sessions/{sid}/messages", headers=h)
    assert r.status_code == 404


def test_me_endpoints(client):
    token = _token(client, "13944440000")
    h = {"Authorization": f"Bearer {token}"}

    # 获取个人信息 + 统计
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["phone"] == "13944440000"
    assert "stats" in me and "sessions" in me["stats"]

    # 改昵称
    r = client.put("/api/auth/me", headers=h, json={"nickname": "新昵称"})
    assert r.status_code == 200, r.text
    assert r.json()["nickname"] == "新昵称"
    r = client.get("/api/auth/me", headers=h)
    assert r.json()["nickname"] == "新昵称"

    # 改密码：原密码错误应失败
    r = client.put("/api/auth/me", headers=h,
                   json={"old_password": "wrong", "new_password": "newpass123"})
    assert r.status_code == 400
    # 正确修改
    r = client.put("/api/auth/me", headers=h,
                   json={"old_password": "pass123", "new_password": "newpass123"})
    assert r.status_code == 200, r.text

    # 新密码可登录，旧密码不行
    r = client.post("/api/auth/login",
                    json={"phone": "13944440000", "password": "newpass123"})
    assert r.status_code == 200
    r = client.post("/api/auth/login",
                    json={"phone": "13944440000", "password": "pass123"})
    assert r.status_code == 401

    # 退出接口
    r = client.post("/api/auth/logout", headers=h)
    assert r.status_code == 200


def test_calibration(client):
    token = _token(client, "13955550000")
    h = {"Authorization": f"Bearer {token}"}
    sid = client.post("/api/chat/sessions", json={"title": "cal"}, headers=h).json()["id"]

    # 发送一条焦虑消息
    r1 = client.post(f"/api/chat/sessions/{sid}/messages",
                     json={"content": "我好焦虑，睡不着"}, headers=h).json()
    assert r1["emotion"]["emotion_type"] == "焦虑"
    mid1 = r1["user_message"]["id"]

    # 校准为悲伤
    r = client.post("/api/emotion/calibrate", headers=h,
                    json={"message_id": mid1, "emotion_type": "悲伤"})
    assert r.status_code == 200, r.text
    assert r.json()["corrected"] == "悲伤"

    # 消息情绪已更新
    msgs = client.get(f"/api/chat/sessions/{sid}/messages", headers=h).json()
    assert next(m for m in msgs if m["id"] == mid1)["emotion_type"] == "悲伤"

    # 校准统计有记录
    cal = client.get("/api/emotion/calibration", headers=h).json()
    assert cal["total"] >= 1
    assert any(p["from"] == "焦虑" and p["to"] == "悲伤" for p in cal["pairs"])

    # 再校准一次「焦虑→悲伤」，累计到 2 次触发个性化偏好
    r2 = client.post(f"/api/chat/sessions/{sid}/messages",
                     json={"content": "最近压力好大，很焦虑"}, headers=h).json()
    assert r2["emotion"]["emotion_type"] == "焦虑"
    client.post("/api/emotion/calibrate", headers=h,
                json={"message_id": r2["user_message"]["id"], "emotion_type": "悲伤"})

    # 新消息再被判为焦虑时，应按用户偏好自动校准为悲伤
    r3 = client.post(f"/api/chat/sessions/{sid}/messages",
                     json={"content": "我又开始焦虑了"}, headers=h).json()
    assert r3["emotion"]["emotion_type"] == "悲伤", r3
    assert r3["emotion"]["source"] == "calibrated"
    assert r3["emotion"]["calibration"]["applied"] is True


def test_avatar_phone_and_session_rename(client):
    token = _token(client, "13966660000")
    h = {"Authorization": f"Bearer {token}"}

    # 默认头像为空字符串
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 200, r.text
    assert "avatar" in r.json()

    # emoji 头像
    r = client.put("/api/auth/me", headers=h, json={"avatar": "🌙"})
    assert r.status_code == 200, r.text
    assert r.json()["avatar"] == "🌙"
    assert client.get("/api/auth/me", headers=h).json()["avatar"] == "🌙"

    # 图片头像（复用上传接口）
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d4944415478da63f8ffff3f0005fe02fea736d9d10000000049454e44ae426082")
    r = client.post("/api/chat/upload", headers=h,
                    files={"file": ("av.png", png, "image/png")})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert client.put("/api/auth/me", headers=h, json={"avatar": url}).json()["avatar"] == url

    # 改手机号：缺密码 / 密码错 / 重复
    assert client.put("/api/auth/me", headers=h,
                      json={"phone": "13966660001"}).status_code == 400
    assert client.put("/api/auth/me", headers=h,
                      json={"phone": "13966660001", "old_password": "bad"}).status_code == 400
    # 占用：先注册另一个账号（随机尾号避免残留冲突；确保注册成功后再断言 409）
    import random as _rnd
    _occ = f"1396666{_rnd.randint(1000, 9999)}"
    rr = client.post("/api/auth/register",
                     json={"phone": _occ, "password": "pass123", "nickname": "占位"})
    assert rr.status_code == 200, f"占位账号注册失败: {rr.status_code} {rr.text[:100]}"
    # 占用手机号改号 → 409
    r409 = client.put("/api/auth/me", headers=h,
                      json={"phone": _occ, "old_password": "pass123"})
    assert r409.status_code == 409, f"预期409得到{r409.status_code}"

    # 正常修改：随机新号（避开 _occ）
    _new = _occ  # 循环直到拿到不同于 _occ 的号
    while _new == _occ:
        _new = f"1396666{_rnd.randint(1000, 9999)}"

    # 正常修改并可用新手机号登录
    r = client.put("/api/auth/me", headers=h,
                   json={"phone": _new, "old_password": "pass123"})
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == _new
    assert client.post("/api/auth/login",
                       json={"phone": _new, "password": "pass123"}).status_code == 200

    # 会话重命名
    sid = client.post("/api/chat/sessions", json={"title": "新的对话"}, headers=h).json()["id"]
    r = client.put(f"/api/chat/sessions/{sid}", headers=h, json={"title": "关于加班的烦恼"})
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "关于加班的烦恼"
    sessions = client.get("/api/chat/sessions", headers=h).json()
    assert {s["id"]: s["title"] for s in sessions}[sid] == "关于加班的烦恼"

    # 空标题 / 不存在会话
    assert client.put(f"/api/chat/sessions/{sid}", headers=h,
                      json={"title": ""}).status_code == 422
    assert client.put("/api/chat/sessions/999999", headers=h,
                      json={"title": "x"}).status_code == 404

    # 跨用户不可重命名
    other = _token(client, "13977770000")
    oh = {"Authorization": f"Bearer {other}"}
    assert client.put(f"/api/chat/sessions/{sid}", headers=oh,
                      json={"title": "hack"}).status_code == 404


def test_admin_extra(client):
    # 普通用户造数据：角色会话 + 情绪 + 论坛帖
    tok = _token(client, "13912120000")
    h = {"Authorization": f"Bearer {tok}"}
    sid = client.post("/api/chat/sessions", headers=h,
                      json={"title": "t", "persona_id": "hinata"}).json()["id"]
    client.post(f"/api/chat/sessions/{sid}/messages", json={"content": "好难过"}, headers=h)
    client.post("/api/forum/posts", headers=h,
                json={"title": "hi", "content": "正能量", "tags": ["治愈"]})

    # 管理员登录
    r = client.post("/api/auth/login", json={"phone": "13800000000", "password": "admin123"})
    assert r.status_code == 200
    ah = {"Authorization": f"Bearer {r.json()['token']}"}

    r = client.get("/api/admin/personas", headers=ah)
    assert r.status_code == 200, r.text
    data = r.json()
    assert any(p["persona_id"] == "hinata" and p["sessions"] >= 1 for p in data)
    assert all("category" in p and "emotions" in p for p in data)

    r = client.get("/api/admin/forum", headers=ah)
    assert r.status_code == 200
    assert r.json()["totals"]["posts"] >= 1
    assert "hot_tags" in r.json()

    r = client.get("/api/admin/stats", headers=ah)
    totals = r.json()["totals"]
    for k in ("posts", "likes", "comments", "calibrations"):
        assert k in totals


def test_admin_platform(client):
    """管理平台 v2：概览、用户、角色、社区审核、会话、系统信息与权限。"""
    r = client.post("/api/auth/login", json={"phone": "13800000000", "password": "admin123"})
    assert r.status_code == 200
    ah = {"Authorization": f"Bearer {r.json()['token']}"}

    # 概览
    r = client.get("/api/admin/overview?days=7", headers=ah)
    assert r.status_code == 200, r.text
    ov = r.json()
    assert len(ov["series"]) == 7
    for k in ("users", "sessions", "messages", "emotions", "posts", "high_risk"):
        assert k in ov["totals"]
    assert {"new_users", "messages", "active_users"} <= set(ov["today"])
    assert ov["system"]["version"] == "2.0.0"

    # 用户列表新结构
    r = client.get("/api/admin/users?page_size=50", headers=ah)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    if body["items"]:
        row = body["items"][0]
        assert {"avatar", "sessions", "messages", "last_active"} <= set(row)

    # 角色列表带头像与标签
    r = client.get("/api/admin/personas", headers=ah)
    plist = r.json()
    assert len(plist) == 30
    assert all(p["avatar"].startswith("/uploads/personas/") for p in plist)
    assert all("tagline" in p for p in plist)
    healers = [p for p in plist if p["category"] == "心理疗愈室"]
    assert len(healers) == 7
    assert all(p["heal_target"] for p in healers)

    # 前台角色接口也返回头像
    r = client.get("/api/chat/personas", headers=ah)
    assert all("avatar" in p for p in r.json())

    # 社区审核：发帖 → 评论 → 删除评论 → 下架帖子
    r = client.post("/api/forum/posts", headers=ah,
                    json={"title": "审核用帖", "content": "临时内容", "tags": ["测试"]})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    r = client.post(f"/api/forum/posts/{pid}/comments", headers=ah, json={"content": "临时评论"})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    r = client.get("/api/admin/posts?q=审核用帖", headers=ah)
    assert r.json()["total"] >= 1
    assert client.delete(f"/api/admin/comments/{cid}", headers=ah).status_code == 200
    assert client.get("/api/admin/comments?q=临时评论", headers=ah).json()["total"] == 0
    assert client.delete(f"/api/admin/posts/{pid}", headers=ah).status_code == 200
    assert client.delete("/api/admin/posts/999999", headers=ah).status_code == 404

    # 会话抽查
    r = client.get("/api/admin/sessions?page_size=20", headers=ah)
    assert r.status_code == 200
    assert "items" in r.json()

    # 系统信息
    r = client.get("/api/admin/system", headers=ah)
    assert r.status_code == 200
    sysinfo = r.json()
    assert {"db", "uploads", "llm", "counts"} <= set(sysinfo)
    assert sysinfo["counts"]["personas"] == 30

    # 普通用户越权访问 → 403
    ut = _token(client, "13988880000")
    uh = {"Authorization": f"Bearer {ut}"}
    for path in ("/api/admin/overview", "/api/admin/posts",
                 "/api/admin/comments", "/api/admin/system"):
        assert client.get(path, headers=uh).status_code == 403


def test_points_knowledge_healroom(client):
    """积分制度、知识库、心理疗愈室。"""
    token = _token(client, "13999990000")
    h = {"Authorization": f"Bearer {token}"}

    # ---- 积分 ----
    r = client.get("/api/points/me", headers=h)
    assert r.status_code == 200, r.text
    pts = r.json()
    assert pts["balance"] == 999999        # 初始拉满
    assert pts["daily_amount"] == 100 and pts["chat_cost"] == 2
    assert pts["claimed_today"] is False

    # 每日领取：第一次成功，第二次 409
    r = client.post("/api/points/claim", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["balance"] == 1000099
    r = client.post("/api/points/claim", headers=h)
    assert r.status_code == 409

    # 聊天消耗积分 + 流水记录
    sid = client.post("/api/chat/sessions", json={"title": "积分", "persona_id": "nuan"},
                      headers=h).json()["id"]
    before = client.get("/api/points/me", headers=h).json()["balance"]
    r = client.post(f"/api/chat/sessions/{sid}/messages",
                    json={"content": "今天有点累"}, headers=h)
    assert r.status_code == 200, r.text
    after = client.get("/api/points/me", headers=h).json()
    assert after["balance"] == before - 2
    assert after["history"][0]["delta"] == -2
    assert after["history"][0]["reason"] == "chat"
    assert after["history"][1]["reason"] == "daily_claim"

    # ---- 知识库 ----
    r = client.get("/api/knowledge/categories", headers=h)
    assert r.status_code == 200
    cats = r.json()
    assert len(cats) == 6
    assert sum(c["count"] for c in cats) >= 16

    r = client.get("/api/knowledge/articles", headers=h)
    assert r.json()["total"] >= 16
    r = client.get("/api/knowledge/articles?category=危机求助", headers=h)
    assert all(a["category"] == "危机求助" for a in r.json()["items"])
    r = client.get("/api/knowledge/articles?q=呼吸", headers=h)
    assert r.json()["total"] >= 1

    aid = client.get("/api/knowledge/articles", headers=h).json()["items"][0]["id"]
    r = client.get(f"/api/knowledge/articles/{aid}", headers=h)
    assert r.status_code == 200
    assert "content" in r.json() and "source" in r.json()
    v1 = r.json()["views"]
    r = client.get(f"/api/knowledge/articles/{aid}", headers=h)
    assert r.json()["views"] == v1 + 1
    assert client.get("/api/knowledge/articles/999999", headers=h).status_code == 404

    # ---- 心理疗愈室 ----
    personas_ = client.get("/api/chat/personas", headers=h).json()
    healers = [p for p in personas_ if p["category"] == "心理疗愈室"]
    assert len(healers) == 7
    assert all(p["avatar"].startswith("/uploads/personas/") for p in healers)

    # 专家会话 + 专属语料
    r = client.post("/api/chat/sessions",
                    json={"title": "抑郁状态支持", "persona_id": "heal_dep"}, headers=h)
    assert r.status_code == 200
    hsid = r.json()["id"]
    r = client.post(f"/api/chat/sessions/{hsid}/messages",
                    json={"content": "今天好难过"}, headers=h).json()
    from app import personas as pm
    assert r["reply"]["content"] in pm.get("heal_dep")["voice"]["neg"]

    # 疗愈室系统提示必须包含专业守则
    prompt = pm.system_prompt("heal_dep")
    for kw in ("心理疗愈室", "不进行任何诊断", "12356", "不追问创伤细节"):
        assert kw in prompt, kw
    # 普通角色不含疗愈守则
    assert "专业守则" not in pm.system_prompt("nuan")

    # ---- 疗愈室数据进入管理平台 ----
    r = client.post("/api/auth/login", json={"phone": "13800000000", "password": "admin123"})
    ah = {"Authorization": f"Bearer {r.json()['token']}"}
    r = client.get("/api/admin/heal?days=90", headers=ah)
    assert r.status_code == 200, r.text
    hd = r.json()
    # 会话与消息被记录
    assert hd["totals"]["sessions"] >= 1, hd["totals"]
    assert hd["totals"]["messages"] >= 1, hd["totals"]
    assert hd["totals"]["users"] >= 1
    # 7 位专家与对应疾病方向
    assert len(hd["experts"]) == 7
    assert any(e["persona_id"] == "heal_dep" and e["sessions"] >= 1 for e in hd["experts"])
    assert any(t["target"] == "抑郁状态" and t["sessions"] >= 1 for t in hd["by_target"])
    # 最近会话明细
    assert any(s["id"] == hsid and s["expert"] for s in hd["recent_sessions"])
    # 普通用户越权 → 403
    assert client.get("/api/admin/heal", headers=h).status_code == 403


def test_dialog_flow_intelligence(client):
    """对话智能化 P0：会话轨迹升级、安抚去重、行动卡片、双引擎校验。"""
    import asyncio as _asyncio

    token = _token(client, "13966661000")
    h = {"Authorization": f"Bearer {token}"}
    # 触发知识库入库（供行动卡片检索文章）
    client.get("/api/knowledge/categories", headers=h)

    r = client.post("/api/chat/sessions", json={"title": "轨迹测试", "persona_id": "hinata"},
                    headers=h)
    sid = r.json()["id"]

    # 1) 会话内去重：同一句难过话连发两次，回复不重复（雏田有两条负向语料）
    r1 = client.post(f"/api/chat/sessions/{sid}/messages",
                     json={"content": "今天好难过"}, headers=h).json()
    r2 = client.post(f"/api/chat/sessions/{sid}/messages",
                     json={"content": "今天好难过"}, headers=h).json()
    assert r1["flow"]["consecutive_neg"] == 1 and r1["flow"]["level"] == 0, r1["flow"]
    assert r2["flow"]["consecutive_neg"] == 2, r2["flow"]
    # 高强度连续负向允许提前升级（level ∈ {1, 2}）
    assert r2["flow"]["level"] in (1, 2), r2["flow"]
    assert r1["reply"]["content"] != r2["reply"]["content"], "连续安抚不应重复同一句"

    # 2) 第三轮负向 → 深度陪伴 + 行动卡片（可跳知识库文章）
    r3 = client.post(f"/api/chat/sessions/{sid}/messages",
                     json={"content": "我还是很难过，什么都不想做"}, headers=h).json()
    assert r3["flow"]["level"] == 2 and r3["flow"]["label"] == "深度陪伴", r3["flow"]
    assert r3["action"] and r3["action"]["kind"] in ("exercise", "heal"), r3["action"]
    assert r3["action"].get("article_ref"), r3["action"]

    # 3) 危机消息：行动卡片切换为热线，情绪仍命中高危
    r4 = client.post(f"/api/chat/sessions/{sid}/messages",
                     json={"content": "我好想消失"}, headers=h).json()
    assert r4["emotion"]["high_risk"], r4["emotion"]
    assert r4["action"]["kind"] == "crisis", r4["action"]

    # 4) 双引擎校验：LLM 返回非法值 → 规则引擎接管
    from app.emotion import analyzer, llm as llm_mod

    async def _fake_bad(text, model=None):
        return {"emotion_type": "不存在的情绪", "polarity": "positive",
                "score": 5.0, "heal_score": -1.0, "high_risk": [],
                "suggestion": "", "source": "llm"}

    orig = llm_mod.analyze
    llm_mod.analyze = _fake_bad
    try:
        result = _asyncio.run(analyzer.analyze("我今天特别开心，考试通过啦！"))
        assert result["emotion_type"] in analyzer.EMOTION_TYPES, result
        assert 0 <= result["score"] <= 1 and 0 <= result["heal_score"] <= 1, result
    finally:
        llm_mod.analyze = orig

    # 5) LLM 漏报危机 → 规则引擎兜底（宁误报不漏报）
    async def _fake_miss_crisis(text, model=None):
        return {"emotion_type": "中性", "polarity": "neutral",
                "score": 0.1, "heal_score": 0.1, "high_risk": [],
                "suggestion": "", "source": "llm"}

    llm_mod.analyze = _fake_miss_crisis
    try:
        result = _asyncio.run(analyzer.analyze("我不想活了，好想消失"))
        assert result["high_risk"], "规则引擎的危机底线必须保留"
    finally:
        llm_mod.analyze = orig


def test_user_portrait(client):
    """用户画像：结构化输出、话题提取、提示词注入。"""
    token = _token(client, "13966662000")
    h = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/chat/sessions", json={"title": "画像测试", "persona_id": "nuan"},
                    headers=h)
    sid = r.json()["id"]
    for msg in ["最近天天加班到很晚，好累", "老板又临时改需求，烦死了", "晚上总是睡不着，脑子停不下来"]:
        client.post(f"/api/chat/sessions/{sid}/messages", json={"content": msg}, headers=h)

    r = client.get("/api/profile/me/portrait?days=90", headers=h)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["basic"]["stage"] in ("新朋友", "熟悉的朋友", "老朋友")
    assert p["emotion"]["total_records"] >= 3, p["emotion"]
    assert p["summary"], p
    assert isinstance(p["facts"], list) and p["facts"], p["facts"]
    topics = {t["name"] for t in p["topics"]}
    assert "工作" in topics, topics
    assert p["emotion"]["dominant"], p["emotion"]

    # 画像卡注入角色提示词（含使用约束）
    from app.database import SessionLocal
    from app.services import profile_service
    uid = client.get("/api/auth/me", headers=h).json()["id"]
    db = SessionLocal()
    try:
        text = profile_service.build_prompt_card(db, uid)
        assert "用户画像卡" in text, text[:200]
        assert ("工作" in text) or ("加班" in text), text[:300]
        assert "不要机械罗列" in text
    finally:
        db.close()

    # 未登录不可访问
    assert client.get("/api/profile/me/portrait").status_code == 401


def test_user_memory_wiki(client):
    """记忆维基（LLM Wiki）：规则抽取、合并去重、修订、注入与用户纠错。"""
    import asyncio as _asyncio
    from app.services import wiki_service as ws

    token = _token(client, "13966663000")
    h = {"Authorization": f"Bearer {token}"}

    # 1) 发送含自述事实的消息（规则编译通道）
    r = client.post("/api/chat/sessions", json={"title": "维基测试", "persona_id": "nuan"}, headers=h)
    sid = r.json()["id"]
    r = client.post(f"/api/chat/sessions/{sid}/messages",
                    json={"content": "我今年24岁，住在杭州，养了一只猫"}, headers=h)
    assert r.status_code == 200, r.text

    # 2) 直接调用编译（不等 6 条阈值，先验证编译正确性）
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        uid = client.get("/api/auth/me", headers=h).json()["id"]
        _asyncio.run(ws.compile_wiki(db, uid))
        entries = ws.get_wiki(db, uid)
        keys = {e["key"] for e in entries}
        assert "年龄段" in keys or "居住地" in keys or "养的宠物" in keys, keys
        assert all(e["value"] for e in entries)
        assert all(e["evidence"] for e in entries), "每条事实必须带依据"

        # 3) 同一事实再次提及 → 不重复堆积
        n_before = len(entries)
        db2n = _asyncio.run(ws.compile_wiki(db, uid))
        entries2 = ws.get_wiki(db, uid)
        assert len(entries2) <= n_before + 2, (n_before, len(entries2))

        # 4) 修订：同类事实新说法覆盖旧说法
        ws.apply_updates(db, uid, [{"existing_key": "年龄段", "value": "用户25岁（刚过生日）",
                                    "evidence": "我25岁了"}])
        e = [x for x in ws.get_wiki(db, uid) if x["key"] == "年龄段"]
        if e:
            assert "25" in e[0]["value"]

        # 5) 提示词注入：含分类与使用约束
        prompt = ws.build_wiki_prompt(db, uid)
        assert "用户记忆维基" in prompt or "基本情况" in prompt, prompt[:200]
    finally:
        db.close()

    # 6) 接口：读取 / 用户补充 / 删除纠错
    r = client.get("/api/profile/me/wiki", headers=h)
    assert r.status_code == 200
    wk = r.json()
    assert "entries" in wk and "stats" in wk and "markdown" in wk

    r = client.post("/api/profile/me/wiki", headers=h,
                    json={"key": "养的宠物", "value": "一只叫团团的橘猫", "category": "重要他人"})
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    wk2 = client.get("/api/profile/me/wiki", headers=h).json()
    assert any(e["id"] == eid and e["pinned"] and e["source"] == "user" for e in wk2["entries"])

    assert client.delete(f"/api/profile/me/wiki/{eid}", headers=h).status_code == 200
    wk3 = client.get("/api/profile/me/wiki", headers=h).json()
    assert all(e["id"] != eid for e in wk3["entries"])
    assert client.delete("/api/profile/me/wiki/999999", headers=h).status_code == 404
    assert client.get("/api/profile/me/wiki").status_code == 401


def test_fortune_zone(client):
    """测测专区：每日运势（确定性）、八字锚点、紫微结构、鉴权。"""
    token = _token(client, "13966664000")
    h = {"Authorization": f"Bearer {token}"}

    # 1) 每日运势：确定性 + 结构
    r1 = client.get("/api/fortune/daily", headers=h)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert 20 <= d1["scores"]["overall"]["value"] <= 98, d1["scores"]["overall"]
    assert len(d1["do"]) == 3 and len(d1["avoid"]) == 2
    assert d1["lucky_color"] and d1["lucky_number"]
    assert d1["ganzhi"]["day"], d1["ganzhi"]
    r2 = client.get("/api/fortune/daily", headers=h)
    assert r2.json() == d1, "同一用户同一天的运势必须一致"
    # 不同用户结果可不同（至少字段结构稳定）
    token_b = _token(client, "13966664001")
    hb = {"Authorization": f"Bearer {token_b}"}
    db_ = client.get("/api/fortune/daily", headers=hb).json()
    assert db_["date"] == d1["date"]
    # 生肖参数参与种子
    dz = client.get("/api/fortune/daily?shengxiao=龙", headers=h).json()
    assert dz["shengxiao"] == "龙"
    # 非法生肖回落通用
    dx = client.get("/api/fortune/daily?shengxiao=xx", headers=h).json()
    assert dx["shengxiao"] is None

    # 2) 八字：锚点 2000-01-01 10:00 → 己卯 丙子 戊午 丁巳
    r = client.post("/api/fortune/bazi", headers=h,
                    json={"birth_date": "2000-01-01", "birth_hour": 10, "gender": "女"})
    assert r.status_code == 200, r.text
    b = r.json()
    pillars = [p["gz"] for p in b["pillars"]]
    assert pillars == ["己卯", "丙子", "戊午", "丁巳"], pillars
    assert b["shengxiao"] == "兔" and "农历" in b["lunar_date"]
    assert sum(b["wuxing"].values()) == 8
    assert b["day_master"]["gan"] == "戊"
    assert b["missing"] == ["金"], b["missing"]
    assert b["summary"]
    # 未知时辰也可排盘（默认午时）
    r = client.post("/api/fortune/bazi", headers=h,
                    json={"birth_date": "1995-06-15", "gender": "男"})
    assert r.status_code == 200 and len(r.json()["pillars"]) == 4
    # 非法日期
    assert client.post("/api/fortune/bazi", headers=h,
                       json={"birth_date": "2000-13-99"}).status_code in (400, 422)

    # 3) 紫微：12 宫 + 14 主星各一次 + 命宫信息
    r = client.post("/api/fortune/ziwei", headers=h,
                    json={"birth_date": "2000-01-01", "birth_hour": 10, "gender": "女"})
    assert r.status_code == 200, r.text
    z = r.json()
    assert len(z["board"]) == 12
    stars = [s for p in z["board"] for s in p["stars"]]
    assert len(stars) == 14 and len(set(stars)) == 14, stars
    assert z["ming"]["ju"] in ("水二局", "木三局", "金四局", "土五局", "火六局")
    assert z["ming"]["gong_zhi"] == "未" and z["ming"]["gong_gan_zhi"] == "辛未", z["ming"]
    assert z["ming"]["summary"]
    for p in z["board"]:
        assert p["interpretation"], p
    # 每宫解读含星名或空宫说明
    ming = z["board"][0]
    assert ming["is_ming"]

    # 4) 紫微多边界日期防回归（含之前触发 UnboundLocalError 的 2100-01-01）
    for bd in ["2100-01-01", "2000-02-29", "1900-01-01", "2026-11-05"]:
        for bh in [None, 0, 10, 23]:
            r = client.post("/api/fortune/ziwei", headers=h,
                            json={"birth_date": bd, "birth_hour": bh, "gender": "女"})
            assert r.status_code == 200, f"{bd} h={bh}: {r.status_code} {r.text[:100]}"
            assert r.json()["ming"]["summary"], bd

    # 4.5) 星曜亮度：每颗主星都带亮度标注
    from app.fortune.ziwei import star_brightness, BRIGHTNESS, BRIGHT_ORDER
    # 查表锚点
    assert star_brightness("太阳", "午")["level"] == "庙"
    assert star_brightness("太阳", "子")["level"] == "陷"
    assert star_brightness("太阴", "亥")["level"] == "庙"
    # 14 星 × 12 地支全部覆盖
    for star, table in BRIGHTNESS.items():
        assert len(table) == 12, star
        assert all(v in BRIGHT_ORDER for v in table.values()), star
    # 排盘结果每宫有 brightness
    for p in z["board"]:
        for b in p.get("brightness", []):
            assert b["level"] in BRIGHT_ORDER and 0 <= b["rank"] <= 6, b

    # 4.6) 三方四正 + 大限 + 流年
    from app.fortune.ziwei import ZHI as _ZHI
    bd = z["board"]
    for p in bd:
        # 对宫地支相隔 6
        dui = bd[p["sanfang"]["dui"]]
        assert (_ZHI.index(p["zhi"]) + 6) % 12 == _ZHI.index(dui["zhi"]), p["palace"]
        # 三合地支相隔 4/8
        for hi in p["sanfang"]["he"]:
            diff = (_ZHI.index(bd[hi]["zhi"]) - _ZHI.index(p["zhi"])) % 12
            assert diff in (4, 8), (p["palace"], diff)
        # 大限年龄段
        assert p["daxian"]["to"] - p["daxian"]["from"] == 9, p["palace"]
    # 12 步大限起点互不相同（无重叠）
    starts = sorted(p["daxian"]["from"] for p in bd)
    assert len(set(starts)) == 12
    assert starts[0] == {"水二局": 2, "木三局": 3, "金四局": 4, "土五局": 5, "火六局": 6}[z["ming"]["ju"]]
    # 恰有一个流年命宫（年支落一宫）
    ln = [p for p in bd if p["is_liunian"]]
    assert len(ln) == 1 and ln[0]["zhi"] == z["liunian"]["zhi"]
    # 大限方向随性别切换
    z_m = client.post("/api/fortune/ziwei", headers=h,
                      json={"birth_date": "2000-01-01", "birth_hour": 10, "gender": "男"}).json()
    dirs = {z["daxian"]["direction"], z_m["daxian"]["direction"]}
    assert dirs == {"顺行", "逆行"}, dirs

    # 4.7) 辅星（六吉六煞+禄存天马）：每盘约 16 颗、全部落宫且有解读
    from app.fortune.ziwei import AUX_STARS
    aux_total = sum(len(p.get("aux", [])) for p in bd)
    assert 14 <= aux_total <= 16, aux_total
    valid_aux = set(AUX_STARS)
    for p in bd:
        for a in p.get("aux", []):
            assert a["star"] in valid_aux
            assert a["type"] in ("吉", "煞")
        # 带辅星的宫，解读中应有"吉星相伴"或"煞星提醒"
        if p.get("aux"):
            assert ("吉星相伴" in p["interpretation"] or "煞星提醒" in p["interpretation"]), p["palace"]

    # 4.8) 八字大运：任意日期查询（对应“点击大运卡片跳转”场景）
    r = client.post("/api/fortune/dayun", headers=h,
                    json={"birth_date": "2000-01-01", "birth_hour": 10,
                          "gender": "女", "query_date": "2040-06-15"})
    assert r.status_code == 200, r.text
    dy = r.json()
    assert dy["query_date"] == "2040-06-15"
    cd = dy["current_dayun"]
    assert cd["gz"] and 0 <= cd["index"] < len(dy["dayun"]), cd
    # 2040-2000=40 岁，应落在 current_dayun 的年龄区间内
    assert cd["age_from"] <= 40 < cd["age_to"], cd
    assert isinstance(dy["interactions"], list)
    for it in dy["interactions"]:
        assert it["type"] and it["detail"] and it["analysis"], it
    # 8 步大运都有年龄区间与五行
    for d in dy["dayun"]:
        assert d["age_from"] < d["age_to"] and d["wuxing_gan"] and d["wuxing_zhi"], d
    # 默认当天也可查
    r2 = client.post("/api/fortune/dayun", headers=h,
                     json={"birth_date": "2000-01-01", "birth_hour": 10, "gender": "女"})
    assert r2.status_code == 200 and r2.json()["query_date"], r2.text

    # 4.9) 紫微流年盘：以指定宫为流年命宫重排十二宫
    qy_zhi = z["board"][6]["zhi"]  # 迁移宫地支
    r = client.post("/api/fortune/ziwei", headers=h,
                    json={"birth_date": "2000-01-01", "birth_hour": 10, "gender": "女",
                          "liunian_gong_zhi": qy_zhi, "liunian_year": 2026})
    assert r.status_code == 200, r.text
    lp = r.json()
    assert "liunian_pan" not in z  # 不带参数的老响应不受影响
    pan = lp["liunian_pan"]
    assert pan["ming_zhi"] == qy_zhi and pan["source_palace"] == "迁移宫", pan
    lbd = pan["board"]
    # 第 0 宫为流年命宫且地支正确；十二宫名从流年命宫起逆布
    assert lbd[0]["palace"] == "流年命宫" and lbd[0]["zhi"] == qy_zhi
    ln_zi = _ZHI.index(qy_zhi)
    for i, p in enumerate(lbd):
        assert (_ZHI.index(p["zhi"]) - (ln_zi - i)) % 12 == 0, (i, p["palace"])
    # 星曜按地支落位不动（与本命盘同地支宫的星一致）
    for p in z["board"]:
        for q in lbd:
            if p["zhi"] == q["zhi"]:
                assert p["stars"] == q["stars"], (p["palace"], q["palace"])
    # 流年盘三方四正：对宫隔 6、三合隔 4/8
    for p in lbd:
        dui = lbd[p["sanfang"]["dui"]]
        assert (_ZHI.index(p["zhi"]) + 6) % 12 == _ZHI.index(dui["zhi"]), p["palace"]
        for hi in p["sanfang"]["he"]:
            assert (_ZHI.index(lbd[hi]["zhi"]) - _ZHI.index(p["zhi"])) % 12 in (4, 8), p["palace"]
        assert p["interpretation"] and p["stars_label"] is not None
    # 流年四化：按流年天干查表，恰 4 条且与 SIHUA 表一致
    from app.fortune.bazi import SIHUA as _BZ_SIHUA
    expect = [f"{sname}{lab}" for lab, sname in zip(["化禄", "化权", "化科", "化忌"],
                                                    _BZ_SIHUA[pan["year_stem"]])]
    got = [it.split("（")[0].rstrip("：") for it in pan["sihua"]["items"]]
    assert got == expect, got
    # 非法宫位忽略；非法年份被 pydantic 拒绝；不带参数不生成流年盘
    r = client.post("/api/fortune/ziwei", headers=h,
                    json={"birth_date": "2000-01-01", "birth_hour": 10, "gender": "女",
                          "liunian_gong_zhi": "不是地支"})
    assert r.status_code == 200 and "liunian_pan" not in r.json()
    r = client.post("/api/fortune/ziwei", headers=h,
                    json={"birth_date": "2000-01-01", "birth_hour": 10, "gender": "女",
                          "liunian_gong_zhi": "午", "liunian_year": 9999})
    assert r.status_code == 422

    # 5) 鉴权：未登录 401
    assert client.get("/api/fortune/daily").status_code == 401
    assert client.post("/api/fortune/bazi", json={"birth_date": "2000-01-01"}).status_code == 401
    assert client.post("/api/fortune/ziwei", json={"birth_date": "2000-01-01"}).status_code == 401
    assert client.post("/api/fortune/dayun", json={"birth_date": "2000-01-01",
                                                    "query_date": "2026-01-01"}).status_code == 401


def test_llm_model_pool(client):
    """模型池：用户端可选模型 / 偏好保存 / 管理端额度与用量统计接口。"""
    token = _token(client, "13977770000")
    h = {"Authorization": f"Bearer {token}"}

    # 1) 用户端：可选模型列表（种子 4 个通义千问）
    r = client.get("/api/chat/models", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    ids = [m["id"] for m in data["models"]]
    assert len(ids) >= 4, ids
    assert {"qwen-plus", "qwen-flash", "qwen3.5-plus", "qwen3.5-flash"} <= set(ids), ids
    assert data["current"] in ids, (data["current"], ids)
    assert any(m["is_default"] for m in data["models"])
    assert all(m["name"] for m in data["models"])

    # 2) 选择模型并持久化
    assert client.post("/api/chat/model", headers=h,
                       json={"model": "qwen-flash"}).status_code == 200
    assert client.get("/api/chat/models", headers=h).json()["current"] == "qwen-flash"
    # 非法模型拒绝
    assert client.post("/api/chat/model", headers=h,
                       json={"model": "no-such-model"}).status_code == 400

    # 3) 未登录 401
    assert client.get("/api/chat/models").status_code == 401

    # 4) 管理端：模型总览（额度/已用/剩余字段齐全）
    a = client.post("/api/auth/login", json={"phone": "13800000000", "password": "admin123"})
    ah = {"Authorization": "Bearer " + a.json()["token"]}
    r = client.get("/api/admin/llm/models", headers=ah)
    assert r.status_code == 200, r.text
    ov = r.json()
    assert ov["summary"]["total_models"] >= 4
    for m in ov["models"]:
        for k in ("free_quota_tokens", "used_total", "used_today",
                  "remaining", "calls_today", "calls_total", "enabled", "is_default"):
            assert k in m, (k, m)
        # 剩余 = max(0, 额度 - 累计已用)
        assert m["remaining"] == max(0, m["free_quota_tokens"] - m["used_total"]), m

    # 5) 改额度 → 剩余同步
    target = next(m for m in ov["models"] if m["model_id"] == "qwen-flash")
    old_quota = target["free_quota_tokens"]
    assert client.put(f"/api/admin/llm/models/{target['id']}", headers=ah,
                      json={"free_quota_tokens": 5_000_000}).status_code == 200
    t2 = next(m for m in client.get("/api/admin/llm/models", headers=ah).json()["models"]
              if m["model_id"] == "qwen-flash")
    assert t2["free_quota_tokens"] == 5_000_000
    assert t2["remaining"] == max(0, 5_000_000 - t2["used_total"])
    assert client.put(f"/api/admin/llm/models/{target['id']}", headers=ah,
                      json={"free_quota_tokens": old_quota}).status_code == 200

    # 6) 新增 + 重复拒绝 + 删除
    r = client.post("/api/admin/llm/models", headers=ah,
                    json={"model_id": "test-model-x", "display_name": "测试模型",
                          "free_quota_tokens": 1000})
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    assert client.post("/api/admin/llm/models", headers=ah,
                       json={"model_id": "test-model-x"}).status_code == 400
    assert client.delete(f"/api/admin/llm/models/{tid}", headers=ah).status_code == 200

    # 7) 默认模型保护：不能停用/删除
    dflt = next(m for m in ov["models"] if m["is_default"])
    assert client.put(f"/api/admin/llm/models/{dflt['id']}", headers=ah,
                      json={"enabled": False}).status_code == 400
    assert client.delete(f"/api/admin/llm/models/{dflt['id']}", headers=ah).status_code == 400

    # 8) 用量接口结构 + 普通用户不可访问管理端
    r = client.get("/api/admin/llm/usage?days=7", headers=ah)
    assert r.status_code == 200
    u = r.json()
    assert {"days", "by_day", "by_model", "recent"} <= set(u.keys()), u
    assert client.get("/api/admin/llm/models", headers=h).status_code == 403


def test_llm_usage_recorded(client):
    """LLM 调用成功后 token 用量落库（打桩 LLM，不触真实 API）。"""
    from app.config import settings
    from app.services import llm_reply
    from app.emotion import llm as emotion_llm
    from app.models import LLMUsageLog
    from app.database import SessionLocal

    token = _token(client, "13977770001")
    h = {"Authorization": f"Bearer {token}"}
    uid = client.get("/api/auth/me", headers=h).json()["id"]
    sid = client.post("/api/chat/sessions", json={"title": "token测试"},
                      headers=h).json()["id"]

    async def fake_analyze(text, model=None):
        return {"emotion_type": "焦虑", "polarity": "negative", "score": 0.7,
                "heal_score": 0.6, "high_risk": [], "suggestion": "",
                "source": "llm", "model": model or "qwen-plus",
                "usage": {"prompt_tokens": 80, "completion_tokens": 20,
                          "total_tokens": 100}}

    async def fake_call_llm(emotion, user_message, history, profile_text, intent,
                            persona_id, strategy_text="", length_text="", model=None):
        return "打桩回复", {"prompt_tokens": 200, "completion_tokens": 50,
                            "total_tokens": 250}

    orig_enabled = settings.LLM_ENABLED
    orig_analyze = emotion_llm.analyze
    orig_call = llm_reply._call_llm
    try:
        settings.LLM_ENABLED = True
        emotion_llm.analyze = fake_analyze
        llm_reply._call_llm = fake_call_llm
        r = client.post(f"/api/chat/sessions/{sid}/messages",
                        json={"content": "压力大睡不着", "model": "qwen-flash"},
                        headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["emotion"]["source"] == "llm", body["emotion"]
        assert body["reply_source"] == "llm", body["reply_source"]
    finally:
        settings.LLM_ENABLED = orig_enabled
        emotion_llm.analyze = orig_analyze
        llm_reply._call_llm = orig_call

    # 两条用量：analyze(100) + reply(250)，模型为请求指定的 qwen-flash
    db = SessionLocal()
    try:
        rows = (db.query(LLMUsageLog)
                .filter(LLMUsageLog.user_id == uid)
                .order_by(LLMUsageLog.id).all())
        assert len(rows) == 2, [(r.scene, r.total_tokens) for r in rows]
        assert {r.scene for r in rows} == {"analyze", "reply"}
        assert sum(r.total_tokens for r in rows) == 350
        assert all(r.model == "qwen-flash" for r in rows), [r.model for r in rows]
    finally:
        db.close()

    # 管理端统计能反映这 350 token
    a = client.post("/api/auth/login", json={"phone": "13800000000", "password": "admin123"})
    ah = {"Authorization": "Bearer " + a.json()["token"]}
    ov = client.get("/api/admin/llm/models", headers=ah).json()
    flash = next(m for m in ov["models"] if m["model_id"] == "qwen-flash")
    assert flash["used_total"] >= 350, flash
    assert flash["calls_total"] >= 2, flash


def test_prompt_management(client):
    """提示词外置管理：markdown 加载 / 表单编辑热生效 / 预览 / 全文校验 / 备份恢复 / 权限。"""
    import pathlib
    import tempfile
    from copy import deepcopy
    from app import personas as P

    # 隔离：重定向到临时目录，不污染真实 prompts/personas.md
    orig_file, orig_hist = P.PROMPTS_FILE, P.HISTORY_DIR
    tmp = tempfile.mkdtemp(prefix="test_prompts_")
    P.PROMPTS_FILE = pathlib.Path(tmp) / "personas.md"
    P.HISTORY_DIR = pathlib.Path(tmp) / "history"
    try:
        P._reload(deepcopy(P.DEFAULT_PERSONAS))
        P._write_file_atomic(P.dump_markdown(P.PERSONAS))

        a = client.post("/api/auth/login", json={"phone": "13800000000", "password": "admin123"})
        ah = {"Authorization": "Bearer " + a.json()["token"]}

        # 1) 总览：30 角色 + 只读守则
        r = client.get("/api/admin/prompts/overview", headers=ah)
        assert r.status_code == 200, r.text
        ov = r.json()
        assert ov["file"]["personas"] == 30
        assert "12356" in ov["guards"]["global"] and "诊断" in ov["guards"]["heal"]
        assert any(p["id"] == "nuan" for p in ov["personas"])

        # 2) 单角色读取 + 表单编辑热生效（写盘 + 内存立即生效）
        r = client.get("/api/admin/prompts/persona/nuan", headers=ah)
        assert r.status_code == 200 and r.json()["system_prompt"].startswith("你现在扮演")
        before = client.get("/api/admin/prompts/source", headers=ah).json()["text"]
        r = client.put("/api/admin/prompts/persona/nuan", headers=ah,
                       json={"personality": "温柔（测试编辑）",
                             "voice": {"pos": ["测试正向语料"]}})
        assert r.status_code == 200, r.text
        assert "温柔（测试编辑）" in r.json()["system_prompt"]
        assert "温柔（测试编辑）" in P.system_prompt("nuan")
        assert P.get("nuan")["voice"]["pos"] == ["测试正向语料"]
        assert "温柔（测试编辑）" in P.PROMPTS_FILE.read_text(encoding="utf-8")  # 已落盘

        # 3) 预览不落盘
        r = client.post("/api/admin/prompts/preview", headers=ah,
                        json={"persona_id": "nuan", "patch": {"personality": "只预览不保存"}})
        assert "只预览不保存" in r.json()["system_prompt"]
        assert "只预览不保存" not in P.get("nuan")["personality"]

        # 4) 技术字段 422 / 角色不存在 404
        assert client.put("/api/admin/prompts/persona/nuan", headers=ah,
                          json={"id": "hack"}).status_code == 422
        assert client.put("/api/admin/prompts/persona/none", headers=ah,
                          json={"name": "x"}).status_code == 404

        # 5) 全文保存：字段缺失 400、删除角色被拒、正常保存 200
        bad = before.replace("- personality: ", "- personality_broken: ", 1)
        assert client.put("/api/admin/prompts/source", headers=ah,
                         json={"text": bad}).status_code == 400
        removed = "\n".join(l for l in before.splitlines() if "## 妈妈" not in l)
        r = client.put("/api/admin/prompts/source", headers=ah, json={"text": removed})
        assert r.status_code == 400 and "不能删除" in r.json()["detail"], r.text
        r = client.put("/api/admin/prompts/source", headers=ah, json={"text": before})
        assert r.status_code == 200 and r.json()["personas"] == 30
        assert "温柔（测试编辑）" not in P.system_prompt("nuan")   # 已回到编辑前

        # 6) 备份 + 恢复 + 路径穿越拒绝
        ov = client.get("/api/admin/prompts/overview", headers=ah).json()
        assert ov["backups"], "编辑与保存应自动产生备份"
        name = ov["backups"][0]["name"]
        assert client.post("/api/admin/prompts/restore", headers=ah,
                           json={"filename": name}).status_code == 200
        assert client.post("/api/admin/prompts/restore", headers=ah,
                           json={"filename": "../../etc/passwd"}).status_code == 400

        # 7) 权限：普通用户 403、未登录 401
        token = _token(client, "13955557000")
        uh = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/admin/prompts/source", headers=uh).status_code == 403
        assert client.get("/api/admin/prompts/overview").status_code == 401

        # 8) markdown round-trip：规范化往返一致
        text = P.get_prompt_source()["text"]
        items = [P._normalize(x) for x in P.parse_markdown(text)]
        assert len(items) == 30
        assert P.dump_markdown(items) == text
    finally:
        # 恢复真实路径并从真实文件重载（真实文件全程未被本测试触碰）
        P.PROMPTS_FILE, P.HISTORY_DIR = orig_file, orig_hist
        P._reload([P._normalize(x) for x in
                   P.parse_markdown(P.PROMPTS_FILE.read_text(encoding="utf-8"))])


if __name__ == "__main__":
    with TestClient(app) as client:
        test_profile_daily_insight(client)
        test_image_upload_and_message(client)
        test_delete_and_logout_flow(client)
        test_me_endpoints(client)
        test_avatar_phone_and_session_rename(client)
        test_calibration(client)
        test_admin_extra(client)
        test_admin_platform(client)
        test_points_knowledge_healroom(client)
        test_dialog_flow_intelligence(client)
        test_user_portrait(client)
        test_user_memory_wiki(client)
        test_fortune_zone(client)
        test_llm_model_pool(client)
        test_llm_usage_recorded(client)
        test_prompt_management(client)
    print("新功能测试全部通过")