# 架构文档 — 情绪感知聊天治愈助手

> 目标读者：**接手本项目的程序员**。读完能理清全貌，知道每个文件干嘛、改哪里、跑什么测试。
> 阅读时间约 15 分钟。先看目录树，再按"要改什么"跳读对应章节。

---

## 1. 技术栈速览

| 层 | 选型 | 运行条件 |
|---|---|---|
| 后端 | Python 3.12 + FastAPI + SQLite（SQLAlchemy ORM） | `backend/.venv` |
| 前端 | Vue 3 (Vite + Pinia + Vue Router) + ECharts + Three.js/three-vrm | Node ≥ 18 |
| 日历 | lunar-python（精确节气、农历、干支） | 已锁定 1.4.8 |
| LLM（可选） | 任何 OpenAI 兼容接口（`.env` 三行配置） | 不配也能跑 |
| 部署 | FastAPI 托管 `frontend/dist` 静态文件，单进程单端口 8000 | 无外部服务 |

---

## 2. 目录结构（关键文件标注）

```
emotion-healing-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口：注册全部路由、CORS、初始管理员、托管 dist
│   │   ├── config.py          # Settings（.env 读取：端口/JWT/LLM/管理员/DATABASE_URL）
│   │   ├── database.py        # 引擎（PostgreSQL 优先/SQLite 回落双驱动，池 5+5+pre_ping）+ get_db
│   │   ├── migrate_to_pg.py   # SQLite → PostgreSQL 一次性数据迁移（依赖序/bool转换/序列对齐/幂等）
│   │   ├── models.py          # 15 张表全部在这一个文件里（含 llm_models / llm_usage_logs / agent_trace_logs，见 §4）
│   │   ├── schemas.py         # Pydantic 入参模型
│   │   ├── security.py        # JWT 签发/校验 + PBKDF2 密码哈希
│   │   ├── deps.py            # get_current_user / require_admin 依赖注入
│   │   │
│   │   ├── emotion/           # ◆ 情绪引擎（自研，双引擎）
│   │   │   ├── lexicon.py     #   情感词典（12 类、强化词、否定词、高风险词）
│   │   │   ├── rule_engine.py #   规则打分
│   │   │   ├── llm.py         #   LLM 结构化 JSON 分析（可选）
│   │   │   ├── analyzer.py    #   双引擎组合器（规则必跑+LLM 增强+合法性校验）
│   │   │   └── intent.py      #   意图分类（倾诉/求助/分享/闲聊/危机）
│   │   │
│   │   ├── fortune/           # ◆ 测测专区引擎
│   │   │   ├── bazi.py        #   八字四柱、五行分布、日主、大运流年流月流日（任意日期交互分析）
│   │   │   ├── ziwei.py       #   紫微斗数安星、十二宫、三方四正、生年四化；流年盘（指定宫为流年命宫重排+流年四化落宫）
│   │   │   └── daily.py       #   每日运势（确定性种子）
│   │   │
│   │   ├── personas.py        # 角色人设加载/组装/在线编辑（数据外置见 prompts/personas.md，解析失败回退内置默认）
│   │   ├── prompts/            # ◆ 提示词数据目录（compose 挂载持久化）
│   │   │   ├── personas.md    #   30 位角色卡人设（唯一数据源，管理后台可在线编辑）
│   │   │   └── history/       #   每次修改自动备份（滚动保留 50 份，不进镜像）
│   │   ├── knowledge_data.py  # 情绪知识库 17 篇文章（首次启动自动入库）
│   │   │
│   │   ├── services/          # ◆ 业务逻辑层
│   │   │   ├── chat_service.py#   发消息主流程（情绪→意图→记忆→回复→落库→积分）
│   │   │   ├── emotion_service.py # 档案/校准/画像/每日小结/AI洞察
│   │   │   ├── dialog_flow.py #   会话轨迹升级 + 行动卡片 + 策略提示
│   │   │   ├── llm_reply.py   #   LLM 回复生成（系统提示组装 + 模型参数 + usage 回传）+ 模板降级
│   │   │   ├── llm_models.py  #   模型池：配置/默认解析/用户选择校验（首启种子 4 个通义千问）
│   │   │   ├── llm_usage.py   #   LLM token 用量落库（按模型/场景；无 usage 时文本估算兕底）
│   │   │   ├── tracer.py      #   Agent 链路追踪（参考 dsAgent @AgentTrace 的 Python 化：span 上下文管理器 + 异步落库）
│   │   │   ├── wiki_service.py#   记忆维基编译（LLM 通道 + 规则兜底）
│   │   │   ├── profile_service.py # 用户画像（统计派）
│   │   │   ├── healing_templates.py # 危机回复模板
│   │   │   └── ...
│   │   │
│   │   └── routers/           # ◆ API 路由（按功能分文件）
│   │       ├── auth.py        #   注册/登录/个人信息/退出
│   │       ├── chat.py        #   会话/消息/角色列表/上传
│   │       ├── emotion.py     #   情绪档案/校准/洞察/每日小结
│   │       ├── forum.py       #   社区帖子/评论/点赞/搜索
│   │       ├── knowledge.py   #   知识库文章
│   │       ├── fortune.py     #   测测专区
│   │       ├── points.py      #   积分
│   │       ├── profile.py     #   画像+记忆维基
│   │       └── admin.py       #   管理平台（看板/用户/情绪/疗愈室/审核/系统/模型池/提示词管理）
│   │
│   ├── tests/                 # 四个测试文件（见 §7）
│   ├── uploads/               # 用户上传的头像/帖子图 + personas/ 角色立绘
│   ├── data/                  # SQLite 数据库（gitignore）
│   └── requirements.txt
│
├── frontend/
│   ├── public/models/         # VRM 模型插槽（avatar.vrm > twist-sample.vrm）
│   ├── src/
│   │   ├── main.js            # Vue 入口
│   │   ├── style.css          # 全局样式变量
│   │   ├── assets/admin.css   # 管理平台设计系统
│   │   ├── api/index.js       # axios 封装（baseURL=/api，token 拦截器）
│   │   ├── stores/auth.js     # Pinia（token/role/nickname）
│   │   ├── router/index.js    # 全部路由 + admin 守卫
│   │   ├── components/
│   │   │   ├── VrmGirl.vue    # 3D 角色全引擎（骨骼/表情/待机/动作/口型）
│   │   │   ├── Pet.vue        # 桌面宠物
│   │   │   └── AdmIcon.vue    # 管理平台 SVG 图标
│   │   └── views/
│   │       ├── Chat.vue       # 核心聊天页（侧栏/消息/行动卡片/积分）
│   │       ├── VrmChat.vue    # 3D 陪伴聊天
│   │       ├── Fortune.vue    # 测测专区
│   │       ├── HealRoom.vue   # 心理疗愈室
│   │       ├── Knowledge*.vue # 知识库
│   │       ├── Forum*.vue     # 社区
│   │       ├── PostEditor.vue # 全页编辑器
│   │       ├── Emotion.vue    # 情绪档案（画像+维基）
│   │       ├── Account.vue    # 个人信息（积分/头像/手机号）
│   │       └── admin/         # 管理平台七页 + AdminLayout
│   └── vite.config.js         # 代理 /api → 8000
│
├── assets/personas/raw/       # 30 张角色立绘原图（2048×2048）
└── README.md                  # 产品文档
```

---

## 3. 核心数据流：用户发一条消息后发生了什么

这是最重要的一个图，理解它就理解了整个后端：

```
用户 POST /api/chat/sessions/{id}/messages
         │
         ▼
    chat.py 路由层
         │ 先扣 2 积分（不足 → 402）
         ▼
    chat_service.send_user_message()
         │
         ├── 1. analyzer.analyze(content)          ← 本地规则必跑
         │      ├── rule_engine.analyze()           词典打分 → 12类情绪+强度+风险
         │      └── llm.analyze()                   LLM JSON（可选，增强层）
         │         → 合法性校验：非法类别回落规则、危机任一引擎命中即命中
         │
         ├── 2. apply_personal_calibration()         用户校准偏好修正
         │
         ├── 3. intent.detect()                     倾诉/求助/分享/闲聊/危机
         │
         ├── 4. build_memory_context()               最近12条消息（多轮记忆）
         │   profile_service.build_prompt_card()    用户画像卡（统计派）
         │   wiki_service.build_wiki_prompt()       记忆维基卡（积累派）
         │
         ├── 5. dialog_flow.compute_trajectory()    会话轨迹（连续负向N轮）
         │   │   → level 0/1/2（轻共情→稳定→深度）
         │   pick_action()                          行动卡片（呼吸/疗愈室/热线）
         │
         ├── 6. llm_reply.generate()                 生成回复
         │   ├── LLM 可用 → 组装系统提示（角色卡+画像卡+维基卡+轨迹策略+长度控制）→ 调 LLM
         │   └── LLM 不可用 → personas.fallback_reply()（角色专属语料 + 去重）
         │
         ├── 7. 落库：Message(user_msg + assistant_msg) + EmotionRecord
         │   会话标题更新
         │
         ├── 8. wiki_service.maybe_compile_async()  每6条消息触发后台维基编译
         │
         └── 返回 JSON: user_message + reply + emotion + flow + action + reply_source
```

---

## 4. 数据模型（16 张表）

所有表定义在 `models.py`，用 SQLAlchemy Declarative。**生产库为 PostgreSQL**（接入已有实例，`DATABASE_URL` 配置；SQLite 仅作开发/测试回落，测试用例强制隔离）。`init_db()` 时 `create_all`；SQLite 模式另跑轻量列迁移（新增列不删库）。

**时间约定**：所有时间列 `DateTime(timezone=True)`（PG 为 timestamptz），库内存 UTC；接口输出带 `+00:00`，前端按 Asia/Shanghai 渲染。

| 表名 | 关键字段 | 用途 |
|---|---|---|
| `users` | phone(唯一), nickname, avatar, role, points, is_active | 注册/登录/角色/积分 |
| `chat_sessions` | user_id, title, persona_id | 会话与角色绑定 |
| `messages` | session_id, role, content, emotion_type, emotion_score | 消息及情绪标签 |
| `emotion_records` | user_id, session_id, emotion_type, score, polarity, trigger | 情绪档案（趋势/热力图/波动） |
| `emotion_calibrations` | user_id, original_emotion, corrected_emotion, text | 用户校准 |
| `forum_posts` | user_id, title, content, tags, blocks | 社区帖子 |
| `forum_likes` | post_id, user_id | 点赞 |
| `forum_comments` | post_id, user_id, content | 评论 |
| `points_ledger` | user_id, delta, reason, balance | 积分流水 |
| `knowledge_articles` | title, category, content, views | 知识库（seed_data.py 自动入库） |
| `user_wiki_entries` | user_id, category, key, value, evidence, source, pinned | 记忆维基 |

**新增表的步骤**：models.py 加 class → `init_db()` 自动 create_all → 相关 router/service 使用。不需要手工迁移脚本。

---

## 5. 关键设计模式

### 5.1 双引擎降级（所有 LLM 相关功能通用）

```
配置 LLM → 走 LLM 路径（更智能）
未配置 / 调用失败 → 自动降级到本地路径（保证不中断）
```

| 功能 | LLM 路径 | 本地兜底 |
|---|---|---|
| 情绪分析 | 结构化 JSON 增强层 | 词典+规则 |
| 回复生成 | 角色+画像+策略提示词 | 角色专属语料+去重 |
| 记忆维基 | LLM 抽取合并修订 | 16 类自述句式正则 |
| AI 洞察 | LLM 周报 | 规则摘要 |

**配置方式**：`backend/.env` 三行 → 重启生效。代码不需要改。

### 5.2 危机安全底线（多条防线冗余）

1. **词典层**：`lexicon.py HIGH_RISK_WORDS` 覆盖 20+ 个危机关键词
2. **规则引擎**：命中 → `high_risk` 非空列表
3. **LLM 层**：LLM 也能输出 `high_risk: true`（双引擎任一命中即命中）
4. **回复层**：`healing_templates.get_reply()` 硬编码 12356 热线
5. **疗愈室守则**：`personas.py _HEAL_GUARD` 系统提示注入专业底线
6. **行动卡片**：危机时自动切换为热线卡片
7. **前端**：Chat.vue 和 VrmChat.vue 渲染危机提示横幅

### 5.3 积分消耗链

```
用户发消息 → chat.py 先检查余额 → try_consume(2) → 不够返回 402
领取 → points.py claim() → 每日 100，重复 409
管理端 → admin.py adjust_points() → 写入流水表
```

---

## 6. 常见修改场景（想改 X 该动哪些文件）

| 场景 | 动哪些文件 |
|---|---|
| **加一个聊天角色** | `backend/prompts/personas.md` 加一个角色块（或管理后台「提示词管理」页新增）→ 自动有 avatar（放 `uploads/personas/{id}.jpg`）→ 热生效无需重启 → 测试 `test_features.py` 更新角色数断言 |
| **加一个管理页** | `routers/admin.py` 加 endpoint → `views/admin/` 新建 Vue 页 → `AdminLayout.vue` 加侧栏菜单 → `router/index.js` 加 admin 子路由 |
| **加一个前台页面** | `views/` 新建 Vue 页 → `router/index.js` 加路由 → `Chat.vue` 侧栏加链接 |
| **改情绪识别** | 加词 → `emotion/lexicon.py`；改权重 → `rule_engine.py`；加类别 → 两个文件同步 |
| **加 LLM 提示词** | `personas.system_prompt()` 或 `llm_reply._build_messages()` |
| **改知识库文章** | `knowledge_data.py` 加 dict → 首次启动自动入库（或删 `.db` 重建） |
| **换 3D 模型** | 把 VRM 命名 `avatar.vrm` 放 `frontend/public/models/` → 刷新生效 |
| **加积分消耗场景** | `routers/chat.py` 已有示例（2 分/条）→ 调用 `points.try_consume()` |
| **改危机关键词** | `emotion/lexicon.py HIGH_RISK_WORDS` → 跑 `test_analyzer` |
| **加测试用例** | `tests/test_features.py` 加函数 → `__main__` 里追加调用 |

---

## 7. 测试体系

```
python -m tests.test_analyzer    # 8 项：情绪引擎单元测试（词典/否定/强化/危机）
python -m tests.test_api         # 端到端：注册→登录→聊天→管理→403
python -m tests.test_features    # 全功能回归（~20 个函数，~90 个断言）
python -m tests.test_forum       # 论坛 + 多智能体角色
```

**运行方式**：直接跑 `python -m tests.xxx`（临时 DB，不污染线上数据）。输出全中文。
**CI 建议**：四个文件串行跑，任何一个 FAIL 就是回退了。

---

## 8. 部署与运维

```bash
# 首次
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd ../frontend && npm install && npm run build

# 日常启动（单进程）
cd backend
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动后：`http://127.0.0.1:8000` = 前端，`/api/*` = 后端，`/uploads/*` = 静态文件。

- 演示账号 `13900000000 / 123456`；管理员 `13800000000 / admin123`
- 演示数据 `python -m app.seed_demo`
- 数据库在 `backend/data/healing.db`，删除后重启会自动重建 + 灌入知识库

---

## 9. .env 配置项

```bash
# 大模型（不配也能跑）
LLM_ENABLED=true
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-xxxx
LLM_MODEL=gpt-4o-mini

# 管理
ADMIN_PHONE=13800000000
ADMIN_PASSWORD=admin123
JWT_SECRET=change-me-in-production
TOKEN_EXPIRE_MINUTES=1440

# 数据库（默认 backend/data/healing.db）
DB_PATH=sqlite:///backend/data/healing.db
```

---

## 10. 本项目的分层原则

| 层 | 职责 | 不应该做的事 |
|---|---|---|
| `routers/` | 参数校验、鉴权、调 service、返回 JSON | 不写业务逻辑 |
| `services/` | 业务逻辑、数据查询与写入 | 不直接读 request/response |
| `emotion/` `fortune/` | 纯计算引擎（无 IO） | 不依赖 FastAPI / Session |
| `models.py` | 只定义表结构 | 不写查询 |
| `personas.py` | 人设加载/组装/在线编辑逻辑 | 角色卡数据在 `prompts/personas.md`，不要写在代码里 |

**数据流单一方向**：`routers → services → models/DB`，引擎模块（emotion/fortune）被 services 调用但不反向依赖。

---

*文档基于 v2.x 代码，若功能有大变动请同步更新本文件。*

> AI生成
