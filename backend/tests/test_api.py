# -*- coding: utf-8 -*-
"""端到端 API 测试（用 TestClient，无需启动真实服务）。"""
import os
import tempfile
import time

from fastapi.testclient import TestClient

# 使用临时数据库，避免污染正式库（必须在导入 app.main 之前设置）
os.environ["DB_PATH"] = os.path.join(
    tempfile.gettempdir(), f"test_healing_{int(time.time() * 1000)}.db")

from app.main import app  # noqa: E402


def _auth(client, phone, password="pass123"):
    r = client.post("/api/auth/register", json={
        "phone": phone, "password": password, "nickname": "测试者"})
    if r.status_code == 409:
        r = client.post("/api/auth/login", json={"phone": phone, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_full_chat_flow(client):
    token = _auth(client, "13900001111")
    h = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/chat/sessions", json={"title": "测试对话"}, headers=h)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    # 负面情绪
    r = client.post(f"/api/chat/sessions/{sid}/messages",
                    json={"content": "我今天很难过，心里很压抑，想哭"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["emotion"]["polarity"] == "negative"
    assert r.json()["reply"]["content"]

    # 正面情绪
    r = client.post(f"/api/chat/sessions/{sid}/messages",
                    json={"content": "老板夸我了，我今天特别开心！"}, headers=h)
    assert r.json()["emotion"]["polarity"] == "positive"

    # 高危（轻生意向）→ 应触发危机干预回复
    r = client.post(f"/api/chat/sessions/{sid}/messages",
                    json={"content": "我撑不下去了，不想活了"}, headers=h)
    assert r.json()["emotion"]["high_risk"]
    assert "心理援助" in r.json()["reply"]["content"]

    # 消息列表：3 用户 + 3 助手
    r = client.get(f"/api/chat/sessions/{sid}/messages", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 6

    # 非本人访问他人会话 404
    other = _auth(client, "13900003333")
    r = client.get(f"/api/chat/sessions/{sid}/messages",
                   headers={"Authorization": f"Bearer {other}"})
    assert r.status_code == 404


def test_admin_stats(client):
    _auth(client, "13900002222")
    token = _auth(client, "13900004444")
    h = {"Authorization": f"Bearer {token}"}
    sid = client.post("/api/chat/sessions", json={"title": "x"}, headers=h).json()["id"]
    client.post(f"/api/chat/sessions/{sid}/messages",
                json={"content": "好孤独，没人理解我"}, headers=h)

    # 管理员登录（由 lifespan 自动创建）
    r = client.post("/api/auth/login", json={"phone": "13800000000", "password": "admin123"})
    assert r.status_code == 200, r.text
    ah = {"Authorization": f"Bearer {r.json()['token']}"}

    r = client.get("/api/admin/stats", headers=ah)
    assert r.status_code == 200, r.text
    assert r.json()["totals"]["users"] >= 3

    r = client.get("/api/admin/users", headers=ah)
    assert r.status_code == 200

    # 普通用户访问管理端 → 403
    r = client.get("/api/admin/users", headers=h)
    assert r.status_code == 403


if __name__ == "__main__":
    with TestClient(app) as client:
        test_full_chat_flow(client)
        test_admin_stats(client)
    print("端到端 API 测试全部通过")