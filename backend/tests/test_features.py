# -*- coding: utf-8 -*-
"""新功能测试：长周期画像、每日小结、AI洞察、图片上传。"""
import io
import os
import tempfile
import time

from fastapi.testclient import TestClient

os.environ["DB_PATH"] = os.path.join(
    tempfile.gettempdir(), f"test_feat_{int(time.time() * 1000)}.db")

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
    # 占用：先注册另一个账号
    client.post("/api/auth/register",
                json={"phone": "13966660002", "password": "pass123", "nickname": "占位"})
    assert client.put("/api/auth/me", headers=h,
                      json={"phone": "13966660002", "old_password": "pass123"}).status_code == 409

    # 正常修改并可用新手机号登录
    r = client.put("/api/auth/me", headers=h,
                   json={"phone": "13966660001", "old_password": "pass123"})
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "13966660001"
    assert client.post("/api/auth/login",
                       json={"phone": "13966660001", "password": "pass123"}).status_code == 200

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

    async def _fake_bad(text):
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
    async def _fake_miss_crisis(text):
        return {"emotion_type": "中性", "polarity": "neutral",
                "score": 0.1, "heal_score": 0.1, "high_risk": [],
                "suggestion": "", "source": "llm"}

    llm_mod.analyze = _fake_miss_crisis
    try:
        result = _asyncio.run(analyzer.analyze("我不想活了，好想消失"))
        assert result["high_risk"], "规则引擎的危机底线必须保留"
    finally:
        llm_mod.analyze = orig


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
    print("新功能测试全部通过")