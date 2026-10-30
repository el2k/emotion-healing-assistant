# -*- coding: utf-8 -*-
"""论坛 + 多智能体角色 测试。"""
import os
import tempfile
import time

from fastapi.testclient import TestClient

os.environ["DB_PATH"] = os.path.join(
    tempfile.gettempdir(), f"test_forum_{int(time.time() * 1000)}.db")

from app.main import app  # noqa: E402


def _token(client, phone="13966660000"):
    r = client.post("/api/auth/register", json={"phone": phone, "password": "pass123",
                                                "nickname": "发帖人"})
    if r.status_code == 409:
        r = client.post("/api/auth/login", json={"phone": phone, "password": "pass123"})
    return r.json()["token"]


def test_personas(client):
    token = _token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/chat/personas", headers=h)
    assert r.status_code == 200, r.text
    plist = r.json()
    ids = [p["id"] for p in plist]
    for pid in ["nuan", "mama", "sister", "xiaomei", "anime", "succubus",
                "hinata", "naruto", "paimon", "ganyu", "hutao", "raiden",
                "nahida", "furina", "yui"]:
        assert pid in ids
    # 每个角色都带作品来源与分类
    assert all("work" in p and "category" in p for p in plist)
    assert any(p["work"] == "火影忍者" for p in plist)
    assert any(p["work"] == "原神" for p in plist)
    cats = set(p["category"] for p in plist)
    for c in ["治愈陪伴", "趣味互动", "3D 陪伴", "动漫角色", "游戏角色"]:
        assert c in cats
    # 3D 角色标记：柚子
    yui = next(p for p in plist if p["id"] == "yui")
    assert yui["model_3d"] is True
    assert yui["avatar"].startswith("/uploads/personas/yui")
    assert yui["category"] == "3D 陪伴"

    # 热门角色榜（按使用量排序）
    r = client.get("/api/chat/personas/popular?limit=6", headers=h)
    assert r.status_code == 200
    pop = r.json()
    assert len(pop) <= 6
    assert all("chat_count" in p for p in pop)

    # 用「雏田」角色建会话并发消息
    r = client.post("/api/chat/sessions", headers=h,
                    json={"title": "和雏田聊天", "persona_id": "hinata"})
    assert r.status_code == 200
    assert r.json()["persona_id"] == "hinata"
    hinata_sid = r.json()["id"]

    # 用「妹妹」角色建会话并发消息
    r = client.post("/api/chat/sessions", headers=h,
                    json={"title": "和妹妹聊天", "persona_id": "xiaomei"})
    assert r.status_code == 200
    sid = r.json()["id"]
    assert r.json()["persona_id"] == "xiaomei"
    # 会话列表带 persona_id
    sessions = client.get("/api/chat/sessions", headers=h).json()
    assert any(s["id"] == sid and s["persona_id"] == "xiaomei" for s in sessions)

    # 同一句难过的话，不同角色回复应来自各自"专属语料"（不是通用外壳）
    from app import personas as persona_mod
    r1 = client.post(f"/api/chat/sessions/{hinata_sid}/messages",
                     json={"content": "今天好难过"}, headers=h).json()
    r2 = client.post(f"/api/chat/sessions/{sid}/messages",
                     json={"content": "今天好难过"}, headers=h).json()
    hinata_reply = r1["reply"]["content"]
    xiaomei_reply = r2["reply"]["content"]
    assert hinata_reply in persona_mod.get("hinata")["voice"]["neg"]
    assert xiaomei_reply in persona_mod.get("xiaomei")["voice"]["neg"]
    assert hinata_reply != xiaomei_reply

    # 3D 角色柚子：建会话 + 专属语料回复
    r = client.post("/api/chat/sessions", headers=h,
                    json={"title": "和柚子的3D时光", "persona_id": "yui"})
    assert r.status_code == 200
    yui_sid = r.json()["id"]
    r3 = client.post(f"/api/chat/sessions/{yui_sid}/messages",
                     json={"content": "今天好难过"}, headers=h).json()
    assert r3["reply"]["content"] in persona_mod.get("yui")["voice"]["neg"]
    # 柚子的负向语料 ≠ 雏田（角色性格化，不是通用外壳）
    assert r3["reply"]["content"] != hinata_reply


def test_forum_flow(client):
    token = _token(client)
    h = {"Authorization": f"Bearer {token}"}

    # 发帖
    r = client.post("/api/forum/posts", headers=h, json={
        "title": "今天也要加油鸭",
        "content": "记录一个温暖的小瞬间，谢谢陌生的善意。",
        "tags": ["治愈", "温暖"],
        "image_urls": [],
    })
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    # 列表 + 搜索
    r = client.get("/api/forum/posts?q=温暖", headers=h)
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json()["items"])
    r = client.get("/api/forum/posts?tag=温暖", headers=h)
    assert any(p["id"] == pid for p in r.json()["items"])

    # 详情
    r = client.get(f"/api/forum/posts/{pid}", headers=h)
    assert r.status_code == 200
    assert r.json()["title"] == "今天也要加油鸭"
    assert r.json()["comments"] == []

    # 点赞切换
    r = client.post(f"/api/forum/posts/{pid}/like", headers=h)
    assert r.json()["liked"] is True and r.json()["like_count"] == 1
    r = client.post(f"/api/forum/posts/{pid}/like", headers=h)
    assert r.json()["liked"] is False and r.json()["like_count"] == 0

    # 评论
    r = client.post(f"/api/forum/posts/{pid}/comments", headers=h,
                    json={"content": "抱抱你～"})
    assert r.status_code == 200
    cid = r.json()["id"]
    r = client.get(f"/api/forum/posts/{pid}", headers=h)
    assert len(r.json()["comments"]) == 1
    assert r.json()["comments"][0]["mine"] is True

    # 热标签
    r = client.get("/api/forum/tags", headers=h)
    assert any(t["name"] == "温暖" for t in r.json())

    # 删除自己的评论与帖子
    assert client.delete(f"/api/forum/comments/{cid}", headers=h).status_code == 200
    assert client.delete(f"/api/forum/posts/{pid}", headers=h).status_code == 200
    assert client.get(f"/api/forum/posts/{pid}", headers=h).status_code == 404


def test_forum_permission(client):
    t1 = _token(client, "13977770000")
    t2 = _token(client, "13988880000")
    h1 = {"Authorization": f"Bearer {t1}"}
    h2 = {"Authorization": f"Bearer {t2}"}
    pid = client.post("/api/forum/posts", headers=h1,
                      json={"title": "x", "content": "别人不能删我"}).json()["id"]
    # 他人删除 → 403
    assert client.delete(f"/api/forum/posts/{pid}", headers=h2).status_code == 403


def test_forum_media(client):
    import io
    token = _token(client, "13999990000")
    h = {"Authorization": f"Bearer {token}"}
    png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
           b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
           b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
    # 图片上传
    r = client.post("/api/forum/upload", headers=h,
                    files={"file": ("a.png", io.BytesIO(png), "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "image"
    img_url = r.json()["url"]
    # 视频上传（伪造字节，仅验证类型与存储）
    r = client.post("/api/forum/upload", headers=h,
                    files={"file": ("v.mp4", io.BytesIO(b"\x00\x00\x00\x18ftypmp42"), "video/mp4")})
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "video"
    vid_url = r.json()["url"]

    # 发布含图文的帖子
    r = client.post("/api/forum/posts", headers=h, json={
        "title": "图文贴", "content": "带图片和视频的帖子",
        "tags": ["生活"], "image_urls": [img_url, vid_url]})
    pid = r.json()["id"]

    # 列表返回媒体
    items = client.get("/api/forum/posts?q=图文贴", headers=h).json()["items"]
    post = next(p for p in items if p["id"] == pid)
    assert img_url in post["images"] and vid_url in post["images"]

    # 详情返回媒体
    d = client.get(f"/api/forum/posts/{pid}", headers=h).json()
    assert len(d["images"]) == 2

    # 媒体可访问
    assert client.get(img_url).status_code == 200
    assert client.get(vid_url).status_code == 200

    # 非法扩展名被拒
    r = client.post("/api/forum/upload", headers=h,
                    files={"file": ("x.exe", io.BytesIO(b"x"), "application/octet-stream")})
    assert r.status_code == 400

    # 图文混排 blocks：顺序保留
    r = client.post("/api/forum/posts", headers=h, json={
        "title": "混排", "tags": ["图文"], "blocks": [
            {"type": "text", "text": "第一段"},
            {"type": "image", "url": img_url},
            {"type": "text", "text": "第二段"},
        ]})
    pid2 = r.json()["id"]
    d = client.get(f"/api/forum/posts/{pid2}", headers=h).json()
    assert [b["type"] for b in d["blocks"]] == ["text", "image", "text"]
    assert d["blocks"][0]["text"] == "第一段"
    assert d["blocks"][2]["text"] == "第二段"


if __name__ == "__main__":
    with TestClient(app) as client:
        test_personas(client)
        test_forum_flow(client)
        test_forum_permission(client)
        test_forum_media(client)
    print("论坛 + 多智能体测试全部通过")