# 情绪感知聊天治愈助手

一个「感知情绪 → 温柔回应」的完整对话助手，包含：前端聊天端、后端服务、管理平台三大部分。

## 功能特性

- **情绪感知**：本地中文情感词典 + 规则打分，实时识别喜悦 / 悲伤 / 焦虑 / 愤怒 / 孤独 / 低落等 12 类情绪
- **个人情绪校准**（不完全依赖模型）：用户可点击消息情绪标签手动纠正；纠正结果会进入个人校准档案，并反向影响后续识别（相似原话匹配 + 纠正偏好学习）
- **意图识别**：判断倾诉 / 求助 / 分享 / 闲聊 / 危机，让回复更贴合（借鉴 emotional_chat 等项目）
- **治愈回复**：按情绪类别与强度，给出共情、温柔的回应；可接入大模型生成个性化回复
- **会话级陪伴策略升级（对话智能化 P0）**：系统追踪本会话的情绪轨迹，安慰会递进而非重复——
  - **轻共情 → 稳定陪伴 → 深度陪伴**：连续 2 轮负向升入稳定陪伴，连续 3 轮或高强度连续负向升入深度陪伴；正向消息出现即自然回落
  - **安抚去重**：同会话内不重复最近已说过的安慰句（模板模式轮换语料，LLM 模式在提示中注入「不要重复上一轮说法」）
  - **行动卡片**：进入深度陪伴时，回复下方自动出现可点击卡片（按主导情绪匹配：焦虑→4-7-8 呼吸 / 恐惧愤怒→5-4-3-2-1 着陆 / 悲伤低落→心理疗愈室 / 委屈→情绪日记），点击直达知识库文章或疗愈室；危机时切换为 12356 热线卡片
  - **长度自适应**：倾诉类回复 40 字内只接情绪不说教，求助类才展开步骤（对 LLM 与模板同时生效）
- **双引擎交叉校验（结构化输出）**：LLM 情绪分析返回结构化 JSON，与本地规则引擎互相校验——非法类别/极性回落规则结果，强度约束到 [0,1]，**危机信号任一引擎命中即命中**（宁误报不漏报）；并修复了 score 字段解析缺陷
- **词典加固**：验证中发现并补齐常用危机表达（想消失/自残/解脱等 12 个高风险词）与高频负向词（难受/崩溃/烦/慌/没动力等），意图层同步扩充
- **多轮对话记忆**：回复时携带最近对话历史 + 用户长期情绪画像 + 会话轨迹策略提示，聊得越久越「懂你」
- **多智能体角色**：30 位角色，按 **分类**（治愈陪伴 / 趣味互动 / 3D 陪伴 / 心理疗愈室 / 动漫角色 / 游戏角色）组织，支持**分类下拉筛选 + 搜索**，并有 **🔥 热门角色榜**（按使用量排序）。每位角色配 **原创同人立绘**（AI 绘制，贴合发色/瞳色/服饰气质，非版权方官方素材），角色广场与聊天页均以立绘形象展示。每个角色含**结构化人设卡**（性格/说话风格/口头禅/在意的事）驱动大模型真实扮演，同时内置**角色专属回复语料**——即使不接大模型也按角色性格说话，而非通用话术套壳。动漫游戏角色为**同人演绎**（原创人设、不复制官方台词），全部健康向
- **角色×情绪联动**：与任意角色的聊天都会写入同一份情绪档案，情绪档案页展示「角色陪伴」榜，做到角色陪伴与情绪记录相互联通
- **3D 陪伴角色**：元气少女「柚子」在 `/vrm` 页与你聊天互动——采用 **three-vrm 加载 GitHub 开源 VRM 模型**（pixiv/three-vrm 官方示例模型，人形骨骼 + 表情系统，加载失败自动降级为 Three.js 程序化建模兑底），12 套情绪反应动作、眨眼、眼神跟随、拖动旋转、点击互动、TTS 朗读同步口型；详见下方「3D 陪伴角色」章节
- **正能量社区（小红书风格）**：**图文混排块编辑器**（文字/图片/视频块自由穿插、可排序、实时预览），支持短视频、标签、点赞、评论、搜索，瀑布流卡片流；块模型参考 BlockNote / Tiptap 等 Notion 风格开源编辑器
- **长周期情绪档案**：90 天+ 情绪画像、情绪日历热力图、心情波动趋势、情绪波动事件（时间·事件）、易波动的时段
- **AI 情绪洞察**：基于情绪历史生成周报式个性化分析与建议（配置大模型走 LLM，否则本地规则生成）
- **每日情绪小结**：每次进入聊天展示当日情绪小结与贴心提示（每日推送）
- **多模态输入**：支持语音输入（浏览器语音识别）+ 图片发送（上传展示）
- **危机识别**：自动识别「轻生 / 绝望」等高危信号，触发严肃而有温度的心理援助引导
- **双引擎**：配置 LLM 后情绪分析更准、回复更自然；未配置自动降级为本地规则，永不中断
- **管理平台 v2（多页后台）**：采用主流后台的「侧边目录 + 多页面」结构，分为 **数据看板 / 用户管理 / 情绪分析 / 角色运营 / 社区审核 / 会话抽查 / 系统信息** 七个模块，互不堆叠：
  - 数据看板：KPI、消息与活跃趋势、情绪分布、高风险关注、角色热度、最新注册
  - 用户管理：搜索分页、使用统计、情绪画像抽屉（分布/趋势/波动事件）、禁用与删除
  - 情绪分析：周期切换、趋势组合图、情绪构成、记录流、高风险用户排行
  - 疗愈室数据：疗愈会话/参与用户/消息/高风险 KPI、疾病方向分布图、7 位专家使用表、高风险用户与最近高风险明细、最近疗愈会话（不含消息正文，保护隐私）
   - 角色运营：30 位角色立绘卡、按会话/消息/情绪排序、分类分布
  - 社区审核：帖子与评论双 Tab、搜索、缩略图预览、一键下架/删除
  - 会话抽查：角色、用户、消息数与时间线（不展示消息正文，保护隐私）
  - 系统信息：版本、数据库与上传体积、数据规模、LLM 接入状态、健康检查
- **心理疗愈室**（`/heal`）：面向「明确疾病状态」用户的专业陪伴专区。选择具体状态（抑郁状态 / 焦虑与惊恐 / 社交焦虑 / 强迫与反刍 / 创伤后应激 / 进食困扰 / 情绪起伏）后自动匹配对应方向的 7 位专家角色。专家配置**系统级专业守则**：不做诊断、不谈药物、适时引导就医、危机必转介 12356、不追问创伤细节；进入前需确认「不构成诊断或治疗」的知情提示。疗愈室角色仅从该入口进入，不混入角色广场。
- **情绪知识库**（`/knowledge`）：17 篇基于循证方法（CBT / MBSR / 行为激活 / 睡眠卫生等）整理的科普与实践文章，分 6 类（情绪认知 / 减压练习 / 焦虑应对 / 抑郁陪伴 / 睡眠作息 / 危机求助），支持分类筛选、全文搜索与阅读计数；内容参考 WHO / APA / NHS 等公众科普方向，仅供心理教育，不构成诊疗建议。
- **积分制度**：每条消息消耗 2 积分，每日可在「个人信息」页免费领取 100 积分；现有用户与管理员初始积分已拉满（999,999）。积分流水全量记录（每日签到 / 聊天消耗 / 管理员调整）便于审计；管理平台用户列表含积分列并可弹窗调整；积分不足时发送消息返回 402 并提示领取。
- **全页文章编辑器**（`/forum/new`）：发布文章从弹窗升级为独立全页：大标题输入、块式编辑（文字 / 图片 / 视频自由排序）、右侧实时预览、草稿自动保存与恢复，发布后直达文章页。
- **桌面宠物**：仿 DeepSeek「大肥鱼」桌宠（参考开源 dsh-pet）——**SVG 绘制 + 状态驱动动画**（漂浮、眨眼、摆尾、眼睛跟随鼠标、点击 Q 弹、爱心粒子、投喂喷水、哄睡 zzz），支持**自由拖拽移动**（位置本地持久化）、6 种造型（大肥鱼/奶牛猫/小白兔/企鹅/小恐龙/小鸡）与好感度养成
- **多用户**：注册登录 + JWT 认证，普通用户 / 管理员两种角色
- **个人信息中心**：头像（上传图片或选择 emoji/恢复默认）、昵称、手机号（改号需原密码确认 + 查重）、密码修改、使用统计、退出登录
- **会话管理**：新建 / 切换 / 删除 / **重命名**（点击标题旁的 ✎ 就地编辑，回车保存、Esc 取消）
- **轻量部署**：SQLite 单文件存储，零外部服务

> 演示数据：运行 `python -m app.seed_demo` 可一键生成近 90 天的 mock 用户与情绪数据。
> 演示账号 `13900000000 / 123456`，管理员 `13800000000 / admin123`。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3 + FastAPI + SQLAlchemy + SQLite |
| 前端 | Vue 3 + Vite + Pinia + Vue Router + ECharts |
| 认证 | JWT（标准库实现）+ PBKDF2 密码哈希 |
| 可选 | 大模型 API（OpenAI 兼容）做深度情绪分析与个性化回复 |

## 目录结构

```
emotion-healing-assistant/
├── assets/
│   └── personas/
│       └── raw/              # 30 位角色立绘原图备份（2048×2048，AI 生成）
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口（托管前端 dist 与 /uploads 静态资源）
│   │   ├── config.py          # 配置中心
│   │   ├── database.py        # SQLite 引擎（含轻量列迁移）
│   │   ├── models.py          # 用户/会话/消息/情绪/社区 模型
│   │   ├── personas.py        # 30 位角色人设卡 + 立绘地址（含 3D 角色与疗愈室专家标记）
│   │   ├── knowledge_data.py  # 情绪知识库内置 17 篇文章（首次启动自动入库）
│   │   ├── security.py        # JWT + 密码哈希
│   │   ├── deps.py            # 认证依赖
│   │   ├── emotion/           # 情绪识别引擎
│   │   │   ├── lexicon.py     #   情感词典
│   │   │   ├── rule_engine.py #   本地规则分类
│   │   │   ├── llm.py         #   大模型深度分析(可选)
│   │   │   └── analyzer.py    #   组合器
│   │   ├── services/          # 业务服务（治愈回复 / LLM 回复 / 会话编排 / 情绪画像）
│   │   └── routers/           # 路由：auth / chat / emotion / forum / admin
│   ├── uploads/
│   │   └── personas/          # 立绘使用版（640×640，由 assets/personas/raw 压缩而来）
│   ├── tests/                 # 单元 + 端到端测试
│   ├── run.py                 # 后端启动入口
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── assets/admin.css   # 管理平台设计系统
│   │   ├── components/        # 桌面宠物、管理端图标
│   │   ├── views/             # 登录 / 聊天 / 情绪档案 / 个人信息 / 角色广场 / 社区
│   │   ├── views/admin/       # 管理平台七页：看板/用户/情绪/角色/审核/会话/系统
│   │   ├── stores/            # Pinia 状态
│   │   ├── api/               # axios 封装
│   │   └── router/            # 含 /admin 子路由与权限守卫
│   └── vite.config.js         # 开发代理 /api → 8000
└── README.md
```

## 快速启动

### 1. 启动后端

```bash
cd backend
python -m venv .venv                     # 首次
.venv\Scripts\activate                   # Windows；mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py                            # 默认 http://127.0.0.1:8000
```

首次启动会自动创建数据库，并生成默认管理员：

- 管理员手机号：`13800000000`
- 管理员密码：`admin123`

> 生产环境请务必通过 `.env` 修改 `ADMIN_PASSWORD` 与 `JWT_SECRET`。

### 2. 启动前端（开发模式）

```bash
cd frontend
npm install
npm run dev                              # http://localhost:5173（已代理 /api 到 8000）
```

浏览器打开 `http://localhost:5173`，注册账号即可开始聊天。

### 3. 生产部署（可选）

将前端构建产物托管到 FastAPI：

```bash
cd frontend
npm run build                            # 生成 dist/
# 重启后端后，直接访问 http://127.0.0.1:8000 即为完整应用
```

## 配置大模型（可选，强烈推荐）

编辑 `backend/.env`（参照 `.env.example`）：

```ini
LLM_ENABLED=true
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-xxxx
LLM_MODEL=gpt-4o-mini
```

配置后：情绪深度分析 + 个性化共情回复均走大模型；若 Key 无效或超时，**自动降级**到本地规则，服务不中断。

## 运行测试

```bash
cd backend
python -m tests.test_analyzer    # 情绪引擎单测
python -m tests.test_api         # 端到端 API 测试
```

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/register | 注册 |
| POST | /api/auth/login | 登录 |
| GET  | /api/auth/me | 个人信息 + 使用统计 |
| PUT  | /api/auth/me | 修改昵称/头像/手机号/密码（改手机号与密码需原密码） |
| POST | /api/auth/logout | 退出登录（前端清除本地凭证） |
| POST | /api/chat/sessions | 新建会话 |
| GET  | /api/chat/sessions | 会话列表 |
| PUT  | /api/chat/sessions/{id} | 重命名会话 |
| DELETE | /api/chat/sessions/{id} | 删除会话 |
| GET  | /api/chat/sessions/{id}/messages | 消息列表 |
| POST | /api/chat/sessions/{id}/messages | 发送消息（支持 text/image，触发情绪分析+意图+回复） |
| POST | /api/chat/upload | 上传图片 |
| GET  | /api/emotion/profile | 长周期情绪画像（?days=90） |
| GET  | /api/emotion/daily | 今日情绪小结（每日推送） |
| GET  | /api/emotion/insight | AI 情绪洞察（?days=30） |
| GET  | /api/emotion/calibration | 个人情绪校准统计 |
| POST | /api/emotion/calibrate | 校准某条消息的情绪 |
| GET  | /api/chat/personas | 多智能体角色列表（含分类、使用量） |
| GET  | /api/chat/personas/popular | 热门角色榜（按使用量） |
| POST | /api/chat/sessions | 新建会话（可带 persona_id 选择角色） |
| GET  | /api/forum/posts | 社区文章列表/搜索（?q=&tag=&page=） |
| POST | /api/forum/posts | 发布文章（支持 image_urls 图片/视频，或 blocks 图文混排块） |
| POST | /api/forum/upload | 上传图片或短视频 |
| GET  | /api/forum/posts/{id} | 文章详情+评论 |
| POST | /api/forum/posts/{id}/like | 点赞/取消 |
| POST | /api/forum/posts/{id}/comments | 发表评论 |
| GET  | /api/forum/tags | 热门标签 |
| GET  | /api/admin/stats | 管理统计（用户/会话/消息/帖子/点赞/校准/高风险） |
| GET  | /api/admin/overview | 看板概览（KPI、按天趋势、风险用户、角色热度、系统状态） |
| GET  | /api/admin/users | 用户列表（搜索/分页，含头像、会话消息数、最后活跃） |
| PUT  | /api/admin/users/{id} | 修改用户（昵称/密码/启用禁用） |
| DELETE | /api/admin/users/{id} | 删除用户及其数据 |
| GET  | /api/admin/users/{id}/profile | 单用户情绪画像 |
| GET  | /api/admin/emotions | 情绪记录（?days=&user_id=） |
| GET  | /api/admin/personas | 角色使用数据（含立绘、标签） |
| GET  | /api/admin/sessions | 会话抽查（搜索/分页，含角色与消息数） |
| GET  | /api/admin/posts | 社区帖子审核列表（搜索/分页） |
| DELETE | /api/admin/posts/{id} | 下架帖子（连同点赞评论） |
| GET  | /api/admin/comments | 评论审核列表 |
| DELETE | /api/admin/comments/{id} | 删除评论 |
| GET  | /api/admin/forum | 论坛数据（总量/热门标签/热门帖子） |
| GET  | /api/admin/heal | 疗愈室数据（总量/疾病方向分布/专家使用/高风险用户，不含消息正文） |
| GET  | /api/admin/system | 系统信息（版本/存储/数据规模/LLM 状态） |
| POST | /api/admin/users/{id}/points | 管理员调整用户积分（记入流水） |

### 知识库 / 积分

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | /api/knowledge/categories | 分类统计（首次启动自动入库 17 篇） |
| GET  | /api/knowledge/articles | 文章列表（分类/搜索/分页） |
| GET  | /api/knowledge/articles/{id} | 文章详情（含正文与来源，阅读计数） |
| GET  | /api/points/me | 我的积分（余额/今日是否已领/流水） |
| POST | /api/points/claim | 每日领取 100 积分（重复领取 409） |

> 发送消息消耗 2 积分（`POST /api/chat/sessions/{id}/messages`），余额不足返回 **402** 并提示领取；新用户初始积分 999,999。

## 3D 陪伴角色（柚子 · /vrm）

首位 **3D 聊天角色**：元气少女「柚子」，进入 `http://127.0.0.1:8000/vrm` 即可与她对话、互动。

**技术实现**（调研了 pixiv/three-vrm、pixiv/ChatVRM、moeru-ai/airi 等开源方案后选型）：

- **建模（开源 VRM）**：`frontend/src/components/VrmGirl.vue` 通过 `three` + `@pixiv/three-vrm` 加载 **pixiv/three-vrm 官方开源示例模型**（`frontend/public/models/twist-sample.vrm`，10.8MB，二次元少女，人形骨骼 + 标准表情），比程序化建模质量高一个量级。**加载失败自动降级**为内置的 Three.js 程序化建模兑底，页面永不空白。
- **驱动**：直接操作 VRM 的 **normalized humanoid 骨骼**（head / spine / chest / upperArm / lowerArm / upperLeg…）与**表情系统**（happy / sad / angry / surprised / aa 口型 / blink 眨眼），动作 = 每帧「待机姿态 + 动作偏移」，天然平滑过渡；`vrm.lookAt` 驱动眼神跟随鼠标。
- **动作系统**：12 套情绪动作，聊天回复按识别结果自动触发：

| 情绪 | 动作 | 情绪 | 动作 |
|---|---|---|---|
| 喜悦 / 期待 | 开心跳跃 / 搓手期待 | 悲伤 / 低落 / 孤独 | 低头垂马尾、坐到身边 |
| 感恩 / 平静 | 拍手 / 挥手 | 焦虑 / 委屈 | 轻微颤抖、抱臂 |
| 愤怒 | 跺脚安抚 | 恐惧 | 缩肩、挡在身前 |
| 中性 | 点头 | **高风险危机** | 双手向前、认真守护 + 热线提示 |

- **互动**：拖动旋转、鼠标眼神跟随、点击她会有「被戳」反应；快捷按钮：打招呼 / 点点头 / 开心跳 / 摸摸头 / 转个圈。
- **说话**：回复可选用浏览器 TTS 朗读，同步**张嘴口型动画**（VRM `aa` 表情）与轻微点头。
- **聊天**：复用现有会话与情绪引擎（persona_id=`yui`），柚子有专属人设卡与回复语料，情绪同样写入情绪档案。
- **换模型**：把任意 VRM 文件放到 `frontend/public/models/` 并更新 `VrmGirl.vue` 里的 `MODEL_URL` 即可（例如 VRoid Studio 制作的 JK 制服模型）；动作接口 `playAnim()` 不需要任何改动。

## 角色形象一览（30 位）

立绘为 AI 绘制的原创同人形象（详见下方「角色立绘说明」），存储于 `backend/uploads/personas/`，替换同名文件即可更换形象（建议 640×640）。

### 治愈陪伴

| 立绘 | 角色 | 出自 | 定位 | 人设简介 | 文件 |
|:---:|---|---|---|---|---|
| <img src="backend/uploads/personas/nuan.jpg" width="120" alt="小窝"> | **小窝** 🌿 | 原创治愈 | 治愈倾听者 | 温柔、耐心，安静地接住你的每一份情绪。 | `nuan.jpg` |
| <img src="backend/uploads/personas/mama.jpg" width="120" alt="妈妈"> | **妈妈** 👩 | 原创治愈 | 温柔妈妈 | 像妈妈一样唠唠叨叨，却句句都是心疼。 | `mama.jpg` |
| <img src="backend/uploads/personas/sister.jpg" width="120" alt="姐姐"> | **姐姐** 👧 | 原创治愈 | 知心姐姐 | 成熟可靠的大姐姐，给你建议，也给你肩膀。 | `sister.jpg` |
| <img src="backend/uploads/personas/xiaomei.jpg" width="120" alt="妹妹"> | **妹妹** 🐰 | 原创治愈 | 元气妹妹 | 黏人又可爱的妹妹，用活力治愈你。 | `xiaomei.jpg` |

### 趣味互动

| 立绘 | 角色 | 出自 | 定位 | 人设简介 | 文件 |
|:---:|---|---|---|---|---|
| <img src="backend/uploads/personas/anime.jpg" width="120" alt="二次元少女"> | **二次元少女** 🌸 | 原创治愈 | 萌系 | 自带萌系结界，说话带着二次元的元气。 | `anime.jpg` |
| <img src="backend/uploads/personas/succubus.jpg" width="120" alt="迷雾魅魔"> | **迷雾魅魔** 😈 | 原创治愈 | 神秘俏皮 · 健康向 | 神秘又爱逗你，但永远只给你温柔的陪伴。 | `succubus.jpg` |

### 3D 陪伴

| 立绘 | 角色 | 出自 | 定位 | 人设简介 | 文件 |
|:---:|---|---|---|---|---|
| <img src="backend/uploads/personas/yui.jpg" width="120" alt="柚子"> | **柚子** 🎀 | 原创治愈 | JK 元气少女 · 3D | 穿水手服的元气高中女生，有 3D 身体，会挥手、点头、跳跃回应你。 | `yui.jpg` |

> 柚子的 3D 形象见下方「3D 陪伴角色」章节，在 `/vrm` 页面与她实时互动。

### 心理疗愈室（仅从 /heal 入口进入，不混入角色广场）

| 立绘 | 专家 | 专业方向 | 对应状态 | 陪伴风格 |
|:---:|---|---|---|---|
| <img src="backend/uploads/personas/heal_dep.jpg" width="100" alt="林静之"> | **林静之** 🌤 | 精神科背景 · 抑郁方向 | 抑郁状态 | 沉稳温和，先问睡眠与吃饭 |
| <img src="backend/uploads/personas/heal_anx.jpg" width="100" alt="陈以宁"> | **陈以宁** 🍃 | CBT 治疗师 · 焦虑与惊恐 | 焦虑与惊恐 | 清晰可靠，先稳呼吸再给小步骤 |
| <img src="backend/uploads/personas/heal_soc.jpg" width="100" alt="方岚"> | **方岚** 🌿 | 社交焦虑方向 | 社交焦虑 | 松弛不评判，小步暴露 |
| <img src="backend/uploads/personas/heal_ocd.jpg" width="100" alt="周明远"> | **周明远** 🧭 | 强迫方向 · ERP 视角 | 强迫与反刍 | 稳定耐心，「看见它但不跟着走」 |
| <img src="backend/uploads/personas/heal_ptsd.jpg" width="100" alt="苏晚晴"> | **苏晚晴** 🌙 | 创伤知情 · 应激方向 | 创伤后应激 | 极温柔稳定，从不追问细节 |
| <img src="backend/uploads/personas/heal_eat.jpg" width="100" alt="温言"> | **温言** 🍮 | 进食与身材焦虑方向 | 进食困扰 | 完全去评判化，不谈数字 |
| <img src="backend/uploads/personas/heal_bip.jpg" width="100" alt="柯一帆"> | **柯一帆** ⛵ | 双相与睡眠节律方向 | 情绪起伏 | 务实稳定，睡眠优先 |

> 7 位专家均受**系统级专业守则**约束（不做诊断 / 不谈药物 / 引导就医 / 危机转介 12356 / 不追问创伤细节），立绘为 AI 绘制的原创职业形象。

### 动漫角色

| 立绘 | 角色 | 出自 | 定位 | 人设简介 | 文件 |
|:---:|---|---|---|---|---|
| <img src="backend/uploads/personas/hinata.jpg" width="120" alt="雏田"> | **雏田** 🌙 | 火影忍者 | 温柔坚定 | 日向一族的大小姐，害羞内向，却有一颗无比坚定的心。 | `hinata.jpg` |
| <img src="backend/uploads/personas/naruto.jpg" width="120" alt="鸣人"> | **鸣人** 🍥 | 火影忍者 | 热血乐观 | 木叶的吊车尾忍者，永远相信『说到做到』。 | `naruto.jpg` |
| <img src="backend/uploads/personas/sakura.jpg" width="120" alt="小樱"> | **小樱** 🌸 | 火影忍者 | 要强温柔 | 医疗忍者，直率要强，也有细腻温柔的一面。 | `sakura.jpg` |
| <img src="backend/uploads/personas/kakashi.jpg" width="120" alt="卡卡西"> | **卡卡西** 🥷 | 火影忍者 | 慵懒可靠 | 旗木卡卡西，看起来慵懒，关键时刻最可靠。 | `kakashi.jpg` |
| <img src="backend/uploads/personas/nezuko.jpg" width="120" alt="祢豆子"> | **祢豆子** 🎋 | 鬼灭之刃 | 温柔护人 | 灶门祢豆子，话不多，却用行动守护身边的人。 | `nezuko.jpg` |

### 游戏角色

| 立绘 | 角色 | 出自 | 定位 | 人设简介 | 文件 |
|:---:|---|---|---|---|---|
| <img src="backend/uploads/personas/paimon.jpg" width="120" alt="派蒙"> | **派蒙** 🧚 | 原神 | 话痨向导 | 旅行者最好的伙伴，爱吃、话多，自称『派蒙』。 | `paimon.jpg` |
| <img src="backend/uploads/personas/ganyu.jpg" width="120" alt="甘雨"> | **甘雨** ❄️ | 原神 | 温柔认真 | 璃月七星秘书，温柔又认真，总是默默承担很多。 | `ganyu.jpg` |
| <img src="backend/uploads/personas/hutao.jpg" width="120" alt="胡桃"> | **胡桃** 🦋 | 原神 | 古灵精怪 | 往生堂第七十七代堂主，爱写打油诗、爱开玩笑，其实很珍惜生命。 | `hutao.jpg` |
| <img src="backend/uploads/personas/raiden.jpg" width="120" alt="雷电将军"> | **雷电将军** ⚡ | 原神 | 冷静威严 | 稻妻的雷电将军，威严冷静，内心却渴望安宁。 | `raiden.jpg` |
| <img src="backend/uploads/personas/nahida.jpg" width="120" alt="纳西妲"> | **纳西妲** 🍀 | 原神 | 智慧温柔 | 须弥的草神小吉祥草王，智慧又温柔，像一位耐心的老师。 | `nahida.jpg` |
| <img src="backend/uploads/personas/furina.jpg" width="120" alt="芙宁娜"> | **芙宁娜** 🎭 | 原神 | 戏剧傲娇 | 枫丹的水神，戏剧化、爱表演，骄傲外表下藏着柔软的心。 | `furina.jpg` |
| <img src="backend/uploads/personas/zhongli.jpg" width="120" alt="钟离"> | **钟离** 🍂 | 原神 | 沉稳博学 | 往生堂客卿，沉稳博学，说话慢条斯理，见多识广。 | `zhongli.jpg` |
| <img src="backend/uploads/personas/venti.jpg" width="120" alt="温迪"> | **温迪** 🎐 | 原神 | 自在潇洒 | 蒙德的吟游诗人，爱自由、爱诗歌，无拘无束。 | `venti.jpg` |
| <img src="backend/uploads/personas/klee.jpg" width="120" alt="可莉"> | **可莉** 🎈 | 原神 | 天真活泼 | 蒙德的小小爆破专家，天真活泼，元气满满。 | `klee.jpg` |
| <img src="backend/uploads/personas/march7.jpg" width="120" alt="三月七"> | **三月七** 📸 | 崩坏：星穹铁道 | 元气拍照 | 星穹列车的少女，爱拍照、元气开朗。 | `march7.jpg` |
| <img src="backend/uploads/personas/danheng.jpg" width="120" alt="丹恒"> | **丹恒** 🐉 | 崩坏：星穹铁道 | 冷静沉稳 | 星穹列车的护卫，冷静寡言，却值得信赖。 | `danheng.jpg` |

## 角色立绘说明

- 23 位角色的立绘均为 **AI 绘制的原创同人形象**，仅参考角色的发色、瞳色、服饰配色与气质进行原创演绎，**不使用、不复制版权方官方美术素材**。
- 动漫 / 游戏角色为**同人演绎**，人设描述与台词均为原创，不代表官方设定；如相关权利方提出异议，可替换为纯原创角色。
- 立绘使用版位于 `backend/uploads/personas/{角色ID}.jpg`（640×640，供前台与后台页面加载）；**2048×2048 原图备份**统一存放在 `assets/personas/raw/{角色ID}.jpg`。
- 更换形象：直接覆盖 `backend/uploads/personas/` 下的同名文件即可（建议 640×640）；如需重新裁切或换尺寸，从 `assets/personas/raw/` 取原图处理。

## 管理平台入口

登录管理员账号（默认 `13800000000 / admin123`）后，访问 `http://127.0.0.1:8000/admin`，会自动进入多页后台：

| 菜单 | 路径 | 说明 |
|------|------|------|
| 数据看板 | /admin/dashboard | KPI、趋势、情绪分布、风险与角色热度 |
| 用户管理 | /admin/users | 搜索分页、画像抽屉、禁用/删除 |
| 情绪分析 | /admin/emotions | 周期趋势、情绪构成、记录流、风险排行 |
| 疗愈室数据 | /admin/heal | 疾病方向分布、专家使用、高风险用户关注（不含消息正文） |
| 角色运营 | /admin/personas | 角色立绘与使用数据 |
| 社区审核 | /admin/forum | 帖子/评论审核与下架 |
| 会话抽查 | /admin/sessions | 会话列表（不含正文，保护隐私） |
| 系统信息 | /admin/system | 版本、存储、LLM 状态、健康检查 |

## 安全提示

- 本项目定位为**情绪陪伴工具，不替代专业心理咨询**。
- 高危情绪（自伤倾向）会引导用户联系心理援助热线（全国 12356），请勿删除该引导。
- 生产环境请修改 `JWT_SECRET`、`ADMIN_PASSWORD`，并考虑限制 CORS 来源。

> AI生成
