# -*- coding: utf-8 -*-
"""命令行聊天客户端：在终端里与指定角色卡对话（连接运行中的后端服务）。

用法示例：
    python cli_chat.py --list                        # 列出全部角色
    python cli_chat.py -p nuan                       # 与小窝聊天（默认角色）
    python cli_chat.py -p 迷雾魅魔                    # 支持中文名（模糊匹配）
    python cli_chat.py -p succubus --once "你好呀"     # 单轮模式（适合脚本/测试）
    python cli_chat.py -p nuan --model qwen-flash     # 临时指定模型
    python cli_chat.py --phone 13900000000 --password 123456 -p 林静之

运行方式（两种都可以）：
    宿主机：cd backend && .venv\\Scripts\\python cli_chat.py -p nuan
    Docker：docker compose exec app python cli_chat.py -p nuan

交互命令：
    /help            查看命令
    /list            列出角色
    /persona <关键字>  切换角色（自动新建会话）
    /new             当前角色新开会话
    /exit            退出
"""
import argparse
import json
import sys

import httpx

# 兼容 Windows 控制台中文输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

USE_COLOR = True


def c(text: str, code: str) -> str:
    if not USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def dim(t):
    return c(t, "90")


def cyan(t):
    return c(t, "36")


def green(t):
    return c(t, "32")


def yellow(t):
    return c(t, "33")


def red(t):
    return c(t, "31")


def bold(t):
    return c(t, "1")


class ChatCLI:
    def __init__(self, base_url: str, phone: str, password: str,
                 persona: str = "nuan", model: str | None = None, stream: bool = True):
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=180)
        self.phone = phone
        self.password = password
        self.model = model
        self.stream = stream
        self.token = ""
        self.user = {}
        self.personas = []
        self.persona = None
        self.session_id = None
        self.persona_selector = persona

    # ---------- 基础 ----------
    def login(self):
        try:
            r = self.client.post("/api/auth/login",
                                 json={"phone": self.phone, "password": self.password})
        except httpx.HTTPError as e:
            raise SystemExit(red(f"无法连接后端 {self.client.base_url}：{e}\n"
                                 "请确认服务已启动（docker compose ps 应为 healthy）"))
        if r.status_code != 200:
            detail = r.json().get("detail", r.text[:100]) if r.text else ""
            raise SystemExit(red(f"登录失败（{self.phone}）：{detail}"))
        self.token = r.json()["token"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"
        self.user = self.client.get("/api/auth/me").json()
        # 积分不足时自动领每日积分
        pts = self.client.get("/api/points/me").json()
        if (pts.get("balance") or 0) < 10 and not pts.get("claimed_today"):
            try:
                self.client.post("/api/points/claim")
            except Exception:
                pass

    def load_personas(self):
        self.personas = self.client.get("/api/chat/personas").json()

    def resolve_persona(self, keyword: str | None):
        kw = (keyword or "").strip().lower()
        if not kw:
            kw = "nuan"
        for p in self.personas:
            if p["id"].lower() == kw:
                return p
        matches = [p for p in self.personas
                   if kw in p["name"].lower() or kw in (p.get("tag") or "").lower()]
        if not matches:
            names = "、".join(f"{p['name']}({p['id']})" for p in self.personas[:6])
            raise SystemExit(red(f"没找到角色「{keyword}」。可用的如：{names} …（用 --list 查看全部）"))
        return matches[0]

    def open_session(self, persona: dict):
        self.persona = persona
        r = self.client.post("/api/chat/sessions",
                             json={"title": f"CLI · {persona['name']}",
                                   "persona_id": persona["id"]})
        if r.status_code != 200:
            raise SystemExit(red(f"创建会话失败：{r.text[:120]}"))
        self.session_id = r.json()["id"]

    def print_header(self):
        p = self.persona
        model = self.model or "默认模型"
        print()
        print(bold(f"{p['emoji']} {p['name']}") + dim(f"（{p['id']}）") +
              dim(f" · {p['category']} · {p.get('tag') or ''}"))
        print(dim(f"连接 {self.client.base_url} · 会话 #{self.session_id} · 模型 {model}"
                  f" · 用户 {self.user.get('nickname') or self.phone}"))
        print(dim("输入消息开始聊天；/help 查看命令，/exit 退出"))
        print()

    # ---------- 聊天 ----------
    def send_stream(self, text: str):
        payload = {"content": text}
        if self.model:
            payload["model"] = self.model
        meta = {}
        print(cyan(f"{self.persona['name']} > "), end="", flush=True)
        with self.client.stream("POST",
                                f"/api/chat/sessions/{self.session_id}/messages/stream",
                                json=payload) as resp:
            if resp.status_code != 200:
                resp.read()
                raise RuntimeError(resp.text[:160])
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    evt = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if evt.get("type") == "meta":
                    meta = evt
                elif evt.get("type") == "chunk":
                    print(evt.get("content", ""), end="", flush=True)
                elif evt.get("type") == "done":
                    break
        print()
        self.show_emotion(meta)

    def send_once(self, text: str):
        payload = {"content": text}
        if self.model:
            payload["model"] = self.model
        r = self.client.post(f"/api/chat/sessions/{self.session_id}/messages", json=payload)
        if r.status_code != 200:
            raise RuntimeError(r.text[:160])
        data = r.json()
        print(cyan(f"{self.persona['name']} > ") + data["reply"]["content"])
        self.show_emotion({"emotion": data.get("emotion", {}),
                           "action": data.get("action")})

    def show_emotion(self, meta: dict):
        emo = (meta or {}).get("emotion") or {}
        if not emo:
            return
        parts = [f"情绪 {emo.get('emotion_type', '—')}"]
        polarity = {"positive": "正向", "negative": "负向", "neutral": "中性"}.get(
            emo.get("polarity"), "")
        if polarity:
            parts.append(polarity)
        if emo.get("heal_score") is not None:
            parts.append(f"安抚度 {emo.get('heal_score'):.2f}")
        heart = []
        if emo.get("high_risk"):
            heart.append(red("⚠ 高风险：已触发危机引导（12356）"))
        action = (meta or {}).get("action") or {}
        if action.get("kind"):
            heart.append(dim(f"建议行动：{action.get('title') or action.get('kind')}"))
        print(dim("   · " + " · ".join(parts)))
        for h in heart:
            print("   " + h)

    # ---------- 命令 ----------
    def print_list(self):
        print()
        cur_cat = None
        for p in self.personas:
            if p["category"] != cur_cat:
                cur_cat = p["category"]
                print(bold(f"[{cur_cat}]"))
            mark = " ←" if self.persona and p["id"] == self.persona["id"] else ""
            print(f"  {p['emoji']} {p['name']:<8} {dim(p['id']):<18} {dim(p.get('tag') or '')}{mark}")
        print()

    def switch_persona(self, keyword: str):
        p = self.resolve_persona(keyword)
        self.open_session(p)
        print(green(f"✓ 已切换到 {p['emoji']} {p['name']}（会话 #{self.session_id}）"))

    def repl(self):
        while True:
            try:
                raw = input(cyan("你 > ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                print(dim("再见，好好照顾自己 ☾"))
                return
            if not raw:
                continue
            if raw in ("/exit", "/quit", ":q"):
                print(dim("再见，好好照顾自己 ☾"))
                return
            if raw == "/help":
                print(dim("  /list 列出角色 · /persona <关键字> 切换角色 · /new 新会话 · /exit 退出"))
                continue
            if raw == "/list":
                self.print_list()
                continue
            if raw == "/new":
                self.open_session(self.persona)
                print(green(f"✓ 已新开会话 #{self.session_id}"))
                continue
            if raw.startswith("/persona"):
                kw = raw[len("/persona"):].strip()
                if not kw:
                    print(yellow("用法：/persona <角色名或id>，例如 /persona 迷雾魅魔"))
                else:
                    self.switch_persona(kw)
                continue
            # 正常消息
            try:
                if self.stream:
                    self.send_stream(raw)
                else:
                    self.send_once(raw)
            except RuntimeError as e:
                print(red(f"发送失败：{e}"))
            except httpx.HTTPError as e:
                print(red(f"网络错误：{e}"))


def main():
    global USE_COLOR
    parser = argparse.ArgumentParser(
        description="命令行聊天客户端：在终端里与指定角色卡对话",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("运行方式")[0])
    parser.add_argument("-p", "--persona", default="nuan",
                        help="角色 id 或中文名（模糊匹配），默认 nuan")
    parser.add_argument("--list", action="store_true", help="列出全部角色")
    parser.add_argument("--once", metavar="TEXT", help="单轮模式：发送一条消息后退出")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000",
                        help="后端地址，默认 http://127.0.0.1:8000")
    parser.add_argument("--phone", default="13900000000", help="登录手机号（默认演示账号）")
    parser.add_argument("--password", default="123456", help="登录密码")
    parser.add_argument("--model", default=None, help="临时指定模型（如 qwen-flash / qwen-plus）")
    parser.add_argument("--no-stream", action="store_true", help="关闭流式逐字输出")
    parser.add_argument("--no-color", action="store_true", help="关闭颜色（适合重定向/日志）")
    args = parser.parse_args()

    USE_COLOR = not args.no_color

    cli = ChatCLI(args.base_url, args.phone, args.password,
                  persona=args.persona, model=args.model, stream=not args.no_stream)
    cli.login()
    cli.load_personas()

    if args.list:
        cli.print_list()
        return

    persona = cli.resolve_persona(args.persona)
    cli.open_session(persona)
    cli.print_header()

    if args.once:
        try:
            if cli.stream:
                cli.send_stream(args.once)
            else:
                cli.send_once(args.once)
        except Exception as e:
            raise SystemExit(red(f"发送失败：{e}"))
        return

    cli.repl()


if __name__ == "__main__":
    main()