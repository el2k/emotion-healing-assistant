# 情绪感知聊天治愈助手

一个「感知情绪 → 温柔回应」的完整对话助手，包含：前端聊天端、后端服务、管理平台三大部分。

> 🔧 **程序员请看**：[ARCHITECTURE.md](./ARCHITECTURE.md) — 详细架构文档（目录结构、数据流图、数据模型、常见修改场景速查表、测试体系、部署指南），15 分钟理清全貌。
> 🔒 **安全与压测**：[SECURITY.md](./SECURITY.md) — 攻防测试结果（9 类攻击 0 漏洞）、限流设计、加固清单。

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
- **多轮对话记忆**：回复时携带最近对话历史 + 用户长期画像卡 + 会话轨迹策略提示，聊得越久越「懂你」
- **用户画像（长期记忆中枢）**：每个用户自动生成一份结构化画像，展示在「情绪档案」页顶部，同时作为长期记忆注入每个角色的提示词：
  - 基础：陪伴天数 / 活跃天数 / 连续记录 / 关系阶段（新朋友 / 熟悉的朋友 / 老朋友）
  - 情绪：主导情绪、基线心情、负向占比、波动性、高峰倾诉时段（凌晨/深夜…）、高风险次数、近期趋势（回升/走低/平稳）
  - 话题：从最近 200 条消息与情绪触发词中统计工作 / 学习 / 家庭 / 关系 / 健康 / 经济 / 自我 / 未来 八大类
  - 校准偏好：用户亲手纠正过的情绪识别（「原判→纠正」），提醒角色不要照字面下判断
  - 摘要与事实卡：自动生成的画像摘要 + 供角色使用的事实清单（含「像朋友一样自然提及、不要机械罗列」的使用约束）
  - 隐私：画像完全在本地计算，不上传任何第三方面；管理端看板只展示聚合数据
- **记忆维基（LLM Wiki）**：采用 Karpathy 2026 提出的「知识编译器」范式——LLM 把对话持续编译为结构化、可积累的事实条目，而非 RAG 式临时检索。与统计画像互补（画像答「情绪模式如何」，维基答「用户是谁、在意哪些具体的人和事」）：
  - **双通道编译**：配置大模型后由 LLM 做结构化抽取与合并（新增/补强/修订三档）；未配置时规则通道兜底（16 类自述句式：年龄/居住地/职业/备考/宠物/家庭角色/目标/睡眠/好恶等），开箱即用
  - **每 6 条消息自动编译一次**（后台异步执行，不阻塞回复）；同类事实重复提及增强置信度、新说法修订旧说法，靠积累而非堆叠
  - **每条事实带依据**（原话片段），用户在「情绪档案」页可查看、补充（置顶高置信）、删除纠错——记忆的所有权在用户手里
  - **注入角色提示词**：按 7 大分类（基本情况/学业职业/重要他人/喜好偏好/目标计划/健康情况/情绪背景）分组限量注入，并带「自然引用、冲突以当下为准」的使用约束
  - 数据模型：`user_wiki_entries` 表（category/key/value/evidence/source/confidence/pinned/hits），接口 `GET/POST /api/profile/me/wiki`、`DELETE /api/profile/me/wiki/{id}`
- **多智能体角色**：30 位角色，按 **分类**（治愈陪伴 / 趣味互动 / 3D 陪伴 / 心理疗愈室 / 动漫角色 / 游戏角色）组织，支持**分类下拉筛选 + 搜索**，并有 **🔥 热门角色榜**（按使用量排序）。每位角色配 **原创同人立绘**（AI 绘制，贴合发色/瞳色/服饰气质，非版权方官方素材），角色广场与聊天页均以立绘形象展示。每个角色含**结构化人设卡**（性格/说话风格/口头禅/在意的事）驱动大模型真实扮演，同时内置**角色专属回复语料**——即使不接大模型也按角色性格说话，而非通用话术套壳。动漫游戏角色为**同人演绎**（原创人设、不复制官方台词），全部健康向；人设卡**外置于 `backend/prompts/personas.md`**（数据与代码分离），可在管理后台「提示词管理」页**在线编辑并热生效**（详见下方「角色提示词在线管理」）
- **角色提示词在线管理**（管理后台 `/admin/prompts`，三页签）：
  - **角色提示词（默认页签）**：左侧 30 位角色分类列表；点开任一角色 → **单角色 Markdown 编辑**：左侧编辑该角色源码（仅一个 `## 角色名` 块，不是全部角色混在一起），右侧**实时渲染该角色卡**（250ms 防抖：角色名 + id/分类/疗愈方向徽章 + 字段名内容 + 口头禅/语料 chips）；**逐行格式校验实时标注**（异常行标红并提示会拒绝保存）；可展开「最终系统提示词」面板预览注入大模型的完整文本（含安全底线与疗愈室守则）；保存即**校验→备份→写盘→热重载**（无需重启）
  - **安全守则（只读）**：全局底线（12356 危机引导）与疗愈室专业守则仅展示不开放编辑，防止误改导致危机处置失效
  - **历史版本**：每次修改前**自动备份**（滚动保留 50 份），一键恢复任意版本；恢复前也会先备份当前
  - 技术字段保护：单角色编辑中 `id/category/work/heal_target` 不可修改、不可删除现有角色（防历史会话悬空）；文件损坏时自动回退内置默认，服务永不中断
- **Agent 处理链路（LLM 不再是黑盒）**：每条 AI 回复带「🔬 处理链路」按钮，点开即可查看这次回复是**怎么一步步生成**的——8 个节点（规则情绪分析 → LLM 深度情绪分析 → 意图识别 → 记忆与画像上下文 → 会话轨迹策略 → **知识库检索（RAG）** → LLM 回复生成 → 落库）按时间轴排列，每个节点显示类型徽章、耗时、模型与 token 消耗，且**入参出参完整透明**：
  - 意图识别：判定路径（关键词命中/高风险直判/默认兜底）+ 全部命中关键词及所属意图
  - 记忆与画像：注入的历史消息（逐条 role+内容）、**实际注入 LLM 的用户画像卡全文**、记忆维基条目、内部情绪摘要（标注未注入）
  - 会话策略：陪伴等级判定、行动卡片及其关联的知识库文章（article_ref：id/标题/分类/检索词）、注入给 LLM 的策略文本与长度要求
  - 知识库检索（RAG）：触发条件（求助或连续负向≥2 轮）、检索词、命中文章与截取段落、未命中原因——**闲聊/轻共情不检索不耗 token**
  - LLM 回复生成：**发给模型的完整消息数组**（含注入的参考资料）与出参
  - **轨迹持久化**：trace_id 存在 assistant 消息上，刷新页面/重开会话后历史消息仍可点开回看
  轨迹仅本人与管理员可见，异步落库不影响回复速度（设计参考 dsAgent 的 Agent 链路追踪，Python 化实现）
- **角色×情绪联动**：与任意角色的聊天都会写入同一份情绪档案，情绪档案页展示「角色陪伴」榜，做到角色陪伴与情绪记录相互联通
- **3D 陪伴角色**：元气少女「柚子」在 `/vrm` 页与你聊天互动——采用 **three-vrm 加载 GitHub 开源 VRM 模型**（pixiv/three-vrm 官方示例模型，人形骨骼 + 表情系统，加载失败自动降级为 Three.js 程序化建模兑底），12 套情绪反应动作、眨眼、眼神跟随、拖动旋转、点击互动、TTS 朗读同步口型；详见下方「3D 陪伴角色」章节
- **正能量社区（小红书风格）**：**图文混排块编辑器**（文字/图片/视频块自由穿插、可排序、实时预览），支持短视频、标签、点赞、评论、搜索，瀑布流卡片流；块模型参考 BlockNote / Tiptap 等 Notion 风格开源编辑器
- **长周期情绪档案**：90 天+ 情绪画像、情绪日历热力图、心情波动趋势、情绪波动事件（时间·事件）、易波动的时段
- **AI 情绪洞察**：基于情绪历史生成周报式个性化分析与建议（配置大模型走 LLM，否则本地规则生成）
- **每日情绪小结**：每次进入聊天展示当日情绪小结与贴心提示（每日推送）
- **多模态输入**：支持语音输入（浏览器语音识别）+ 图片发送（上传展示）
- **危机识别**：自动识别「轻生 / 绝望」等高危信号，触发严肃而有温度的心理援助引导
- **双引擎**：配置 LLM 后情绪分析更准、回复更自然；未配置自动降级为本地规则，永不中断
- **多模型可选与 Token 统计**：模型池默认预置 20 个实测可用的主流文本模型——通义千问（Plus / Flash / 3.5 / 3.6 / 3.7 / 3.8 / Max / Long / 27B 系列）、DeepSeek V4 Pro / V4.1 Flash、智谱 GLM-5.3、Kimi K3 / K3.1 Pro、MiniMax M2.5（阿里云百炼 OpenAI 兼容接口，管理后台可增删改、设默认、启停、填额度），用户可在聊天页顶端下拉切换模型（偏好持久化到账号）；每次调用的 token 用量按**模型/场景（情绪分析/回复生成/流式）**落库，管理后台「模型管理」页实时查看每模型 **额度 / 已用 / 剩余 / 今日消耗 / 累计调用**、近 7/14/30 天消耗趋势与最近调用明细
- **测测专区**（`/fortune`）：命理趣味板块——
  - **每日运势**：五维指数 + 宜忌 + 幸运元素；**五行生克算法驱动**（日主 vs 当日干支生克 + 生肖三合/六合/冲，附推演依据说明）；未填八字时按生肖+日支规则兜底，同一天结果稳定
  - **八字**：精确节气排四柱（lunar-python），五行分布 + 日主分析；**大运排盘**（阳男阴女顺排/阴男阳女逆排，3天折1岁起运，8步大运，每步标注公元年份区间）；**大运卡片可点击**（一键跳到该大运起始年的出生月日，自动加载那年运势并高亮当前大运）；**流年/流月/流日**（年/月/日三级下拉选日期，自动分析命局四柱与该日干支的合化冲刑害交互，如戊癸合化火、子午冲，并附解读，可一键回到今天）
  - **紫微斗数**：**传统 4×4 方形命盘**（十二宫环绕 + 中心信息盘：五行局/命宫身宫/大限/流年/四化摘要）；**主星 14 + 辅星 16**（六吉星：文昌文曲左辅右弼天魁天钺；六煞星：擎羊陀罗火星铃星地空地劫；禄存天马——按年干年支月时安星，命盘小标签区分吉星青绿/煞星砖红，解读含"吉星相伴/煞星提醒"）；**星曜亮度**（庙/旺/得/利/平/不/陷七级，彩色标签）；**三方四正**（点击任意宫位，本宫紫+两三合绿+对宫橙四宫联动，详情列出四宫星曜辅星）；**大限**（顺逆行按性别，每宫标注年龄段，当前高亮）+ **流年**（年支落宫标记）；**流年盘**（点击任意宫可"以此宫为流年命宫"重排十二宫：星曜按地支落位不动、宫名从流年命宫起逆布，流年天干四化标落到哪个流年宫，年份可切换，支持返回本命盘）；**生年四化**（命盘标注 + 独立区块）
  - 免责声明常驻：仅供娱乐参考，不构成任何决策依据
- **路由级页面图标与标题**：全站 20+ 个页面各有自己的 favicon（Canvas 动态生成，无需图片文件）与标题——聊天 💬、社区 🌱、角色 🎭、3D 🎀、知识库 📖、疗愈室 🩺、测测 🔮、写文章 ✏️、管理后台各页 🛠👥💗🩺🎭🧹🗂⚙️，切路由即切换；配合导航与标签页历史一眼可辨
- **切页小互动**：切出浏览器标签页时，标题轮换为想你的话（🌙 你走了…小窝想你了 等），favicon 变 🌙；切回时恢复**当前路由**的图标与标题——参考常见的标题闪烁 + Canvas 动态 favicon 实现
- **管理平台 v2（多页后台）**：采用主流后台的「侧边目录 + 多页面」结构，分为 **数据看板 / 用户管理 / 情绪分析 / 角色运营 / 提示词管理 / 社区审核 / 会话抽查 / 可观测性 / 模型管理 / 系统信息** 十个模块，互不堆叠：
  - 数据看板：KPI、消息与活跃趋势、情绪分布、高风险关注、角色热度、最新注册
  - 用户管理：搜索分页、使用统计、情绪画像抽屉（分布/趋势/波动事件）、禁用与删除
  - 情绪分析：周期切换、趋势组合图、情绪构成、记录流、高风险用户排行
  - 疗愈室数据：疗愈会话/参与用户/消息/高风险 KPI、疾病方向分布图、7 位专家使用表、高风险用户与最近高风险明细、最近疗愈会话（不含消息正文，保护隐私）
    - 角色运营：30 位角色立绘卡、按会话/消息/情绪排序、分类分布
  - 提示词管理：角色卡 Markdown 外置 + 在线编辑热生效 + 实时预览 + 历史备份与恢复（详见「角色提示词在线管理」）
  - 社区审核：帖子与评论双 Tab、搜索、缩略图预览、一键下架/删除
  - 会话抽查：角色、用户、消息数与时间线（不展示消息正文，保护隐私）
  - 模型管理：模型池配置（展示名/描述/额度/启停/默认）、每模型 token 额度与已用/剩余进度条、今日消耗与调用次数、近 7/14/30 天趋势图、按模型汇总与最近 50 条调用明细（含场景与成功状态）
  - 系统信息：版本、数据库与上传体积、数据规模、LLM 接入状态、健康检查
- **心理疗愈室**（`/heal`）：面向「明确疾病状态」用户的专业陪伴专区。选择具体状态（抑郁状态 / 焦虑与惊恐 / 社交焦虑 / 强迫与反刍 / 创伤后应激 / 进食困扰 / 情绪起伏）后自动匹配对应方向的 7 位专家角色。专家配置**系统级专业守则**：不做诊断、不谈药物、适时引导就医、危机必转介 12356、不追问创伤细节；进入前需确认「不构成诊断或治疗」的知情提示。疗愈室角色仅从该入口进入，不混入角色广场。
- **知识库驱动回复（轻量 RAG）**：17 篇情绪知识库文章不再只是「延伸阅读」——当用户**主动求助**或**连续负向 2 轮以上**时，按情绪类型与意图自动检索（焦虑→呼吸/着陆、低落→行为激活、求助→专业帮助自查…），截取最相关段落（每篇≤420 字、最多 2 篇）作为「参考资料」注入角色提示词，让角色在**保持人设与风格**的同时能自然借鉴文章中的方法（呼吸法步骤、着陆技术、睡眠卫生等）；闲聊/分享/轻共情完全不检索，不增加 token 成本。检索全程在轨迹中透明可查
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
│   │   ├── personas.py        # 角色人设加载/组装（数据外置，见 prompts/personas.md）
│   │   ├── prompts/personas.md # ◆ 30 位角色卡人设（唯一数据源，可在线编辑）
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
│   │   ├── views/admin/       # 管理平台十页：看板/用户/情绪/疗愈室/角色/提示词/审核/会话/可观测性/模型/系统
│   │   ├── stores/            # Pinia 状态
│   │   ├── api/               # axios 封装
│   │   └── router/            # 含 /admin 子路由与权限守卫
│   └── vite.config.js         # 开发代理 /api → 8000
└── README.md
```

## 快速启动

### 方式一：Docker（推荐，当前项目采用）

单容器运行：镜像内构建前端 `dist/`，由 FastAPI 一并托管，无需额外 Nginx。

```bash
docker compose up -d --build             # 构建并后台启动
# 浏览器访问 http://localhost:8000
docker compose logs -f                    # 查看日志
docker compose down                       # 停止并移除容器
docker compose ps                        # 状态（healthy 即正常）
```

- **端口**：宿主机 `8000` → 容器 `8000`（改 `docker-compose.yml` 的 `ports` 可换端口）
- **数据持久化**：`backend/data/`（SQLite）、`backend/uploads/`（用户上传内容、角色立绘）、`backend/prompts/`（角色卡提示词）均通过 volume 挂载到宿主机，重建容器不丢数据
- **配置注入**：大模型等配置仍放在 `backend/.env`，由 `env_file` 注入容器；文件不存在也能正常启动
- **健康检查**：容器内置 `GET /api/health` 探针，`docker compose ps` 显示 `healthy`；另有 `GET /api/health/deep` 深度检查（数据库/磁盘/断路器）
- 首次启动自动建库并创建管理员（默认 `13800000000 / admin123`），可在 `backend/.env` 中通过 `ADMIN_PASSWORD`、`JWT_SECRET` 覆盖
- **改代码后**：`docker compose up -d --build`（前端代码必须重新构建，否则页面还是旧产物）

### 方式二：本地开发调试（可选）

> 当前项目已改为 Docker 管理；本地启动仅用于开发调试，且**不要与容器同时占用 8000 端口**（可换 PORT）。

```bash
# 后端
cd backend
python -m venv .venv                     # 首次
.venv\Scripts\activate                   # Windows；mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py                            # 默认 http://127.0.0.1:8000

# 前端开发模式（热更新）
cd frontend
npm install
npm run dev                              # http://localhost:5173（已代理 /api 到 8000）
```

首次启动会自动创建数据库，并生成默认管理员：

- 管理员手机号：`13800000000`
- 管理员密码：`admin123`

> 生产环境请务必通过 `.env` 修改 `ADMIN_PASSWORD` 与 `JWT_SECRET`。

## 命令行聊天（终端里与角色卡对话）

无需打开浏览器，在终端直接和任意角色聊天（流式逐字输出 + 情绪识别显示）。

### 最简单：双击 `chat.bat`（Windows）

项目根目录的 **`chat.bat`** 双击即可：自动检查 Docker Desktop 与容器状态（未运行会自动启动）→ 列出全部角色 → 输入角色名/ID（直接回车 = 小窝）→ 进入聊天。
聊天中输入消息回车发送；`/list` 看角色、`/persona 迷雾魅魔` 换角色、`/exit` 退出。

> 前提：电脑已安装 Docker Desktop 并处于启动状态（任务栏小鲸鱼图标稳定）。

### 命令行方式（手动）

```bash
# 列出全部角色（分类 / id / 标签）
docker compose exec app python cli_chat.py --list

# 与小窝聊天（交互式，多个身份都支持模糊匹配）
docker compose exec app python cli_chat.py -p nuan
docker compose exec app python cli_chat.py -p 迷雾魅魔
docker compose exec app python cli_chat.py -p 林静之          # 疗愈室专家

# 单轮模式（脚本化 / 管道测试）
docker compose exec app python cli_chat.py -p succubus --once "今天好累，想找人说说话"

# 临时指定模型
docker compose exec app python cli_chat.py -p nuan --model qwen-flash
```

宿主机也可以直接跑（需已安装依赖）：`cd backend && .venv\Scripts\python cli_chat.py -p nuan`

交互命令：`/list` 列角色 · `/persona <关键字>` 切换角色（自动新建会话）· `/new` 新会话 · `/help` 帮助 · `/exit` 退出

常用参数：`--phone/--password`（默认演示账号 13900000000）、`--base-url`、`--no-stream`（关闭流式）、`--no-color`（适合重定向到日志）

## 配置大模型（可选，强烈推荐）

编辑 `backend/.env`（参照 `.env.example`）：

```ini
LLM_ENABLED=true
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-xxxx
LLM_MODEL=gpt-4o-mini
```

配置后：情绪深度分析 + 个性化共情回复均走大模型；若 Key 无效或超时，**自动降级**到本地规则，服务不中断。

## 数据库（PostgreSQL）

项目接入**已有的 PostgreSQL 实例**（不新建数据库容器），连接串配置在 `backend/.env`（`env_file` 注入容器）：

```ini
DATABASE_URL=postgresql://projb:***@host.docker.internal:5432/projb
```

- **驱动**：`psycopg[binary]`（requirements 已含），SQLAlchemy 使用 `postgresql+psycopg://` 协议（`postgresql://` 前缀会自动改写）
- **连接池**：5 常驻 + 5 溢出（合计 ≤10，服务端总上限 100、多项目共享）；`pool_pre_ping` 取连接前探活、30 分钟回收，避免共享实例断连
- **时区约定**：库内一律存 **UTC**（全部时间列为 `timestamptz`，`_utcnow()` 产生 aware 时间）；接口输出带 `+00:00` 偏移，**前端按浏览器本地时区（Asia/Shanghai）渲染**
- **权限边界**：应用账号仅为该库 owner（public schema 建表），不做 `CREATE EXTENSION / DATABASE / ROLE`；`pgvector` 已预装可随时用于向量检索升级
- **SQLite 回落**：未设置 `DATABASE_URL` 时自动回落本地 SQLite（开发/测试模式，`DB_PATH` 生效；测试用例强制 SQLite 隔离，不会误连生产库）

### 从 SQLite 迁移数据（一次性）

```bash
# 容器内执行（源为挂载的旧 SQLite 文件）
docker compose run --rm app python migrate_to_pg.py
docker compose run --rm app python migrate_to_pg.py --force   # 清空目标表后重导
```

迁移脚本行为：`create_all` 建表 → 按外键依赖序（父→子）搬运 → SQLite 布尔列转真 bool → 保留源主键并对 PG 自增序列 `setval` 对齐 → 非空表默认跳过（可重复执行）。

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
| POST | /api/chat/sessions/{id}/messages | 发送消息（支持 text/image，触发情绪分析+意图+回复；响应含 trace_id） |
| POST | /api/chat/sessions/{id}/messages/stream | 流式发送（SSE；meta/chunk/done 事件，done 含 trace_id） |
| GET  | /api/chat/trace/{trace_id} | 查看该回复的 Agent 处理链路（节点/耗时/入参出参/模型与 tokens；仅本人与管理员） |
| GET  | /api/admin/trace/{trace_id} | 管理员审计：查看任意回复的完整链路 |
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
| GET  | /api/admin/prompts/overview | 提示词总览：源文件信息 + 只读守则 + 备份列表 + 角色索引 |
| GET  | /api/admin/prompts/source | 提示词 Markdown 源文件全文 |
| PUT  | /api/admin/prompts/source | Markdown 全文保存（逐行校验→备份→写盘→热重载） |
| GET  | /api/admin/prompts/persona/{id}/markdown | 单角色 Markdown 源码块（左编辑右渲染的数据源） |
| PUT  | /api/admin/prompts/persona/{id}/markdown | 保存单角色 Markdown 块（id/技术字段不可变） |
| GET  | /api/admin/prompts/persona/{id} | 单角色可编辑字段 + 组装后完整系统提示词 |
| PUT  | /api/admin/prompts/persona/{id} | 表单更新单角色（保存即热生效） |
| POST | /api/admin/prompts/preview | 预览补丁应用后的系统提示词（不落盘） |
| POST | /api/admin/prompts/restore | 恢复历史备份（恢复前先备份当前） |
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
| GET  | /api/profile/me/portrait | 我的长期画像（基础/情绪/话题/校准/摘要/事实卡） |

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
- **待机动画优化（告别「呆板立正」）**：参考开源 3D 工具链 **GI-Model-Importer-Assets / WWMI-Assets / UmaViewer / GBFRBlenderTools** 中游戏角色的动画组织方式（分层待机动作、次级物理、表情混合），仅借鉴技术思路、不使用其模型资产：
  - **分层待机**：0.55rad/s 极低频重心左右转移 + 胸腔呼吸（肩部联动）+ 视线缓慢漂移 + 手臂/前臂微摆，四个频段叠加，避免单一正弦的机械感
  - **空闲小动作调度**：每 8~13 秒随机播放一次换重心/转头/伸懒腰/张望，角色不会长时间定格
  - **指数阻尼平滑**：所有关节朝目标姿态阻尼收敛（层级速率 6~16），动作不再「瞬间到位」，快速动作也有跟随感
  - **表情混合**：happy/sad/angry/surprised/relaxed 平滑淡入淡出；说话口型改为多层噪声模拟自然音节，并随机连眨两下眼睛
  - **次级物理**：加载后自动调低 VRM 弹簧骨骼刚度与阻尼（×0.82 / ×0.92），头发与裙摆随动作自然摆动
  - **镜头呼吸与视差**：镜头极缓慢上下浮动 + 随鼠标轻微横移，画面不再是冻结的静态图
- **手部与表情细节**：
  - **手部**：驱动 VRM 手指骨骼（每只手 14 根：拇指/食指/中指/无名指/小指 × 三节）实现握拳、张开、指向、托腮等手型，并配合手腕转动（挥手摆动、鼓掌内扣、摸头下压）；待机时手指保留自然微曲与缓慢起伏。注：内置示例模型的手指网格未蒙皮，手型变化在它身上不明显；换成 VRoid 制作的标准 VRM 后会完整呈现
  - **表情**：支持模型全部表情（happy/sad/angry/surprised/relaxed/aa/oh/ee/ih/ou/blinkLeft/blinkRight），带淡入淡出与「惊讶快起快落」的差异化速率；说话时 aa/oh/ee 三层口型混合；眨眼为左右眼 22ms 相位差 + 偶尔连眨；待机每 5~11 秒随机浅笑/挑眉；情绪动作触发时 65% 概率伴随一次眨眼
- **运动逻辑（告别「漂移感」）**：按经典动画三原则重写关键动作——
    **预备（anticipation）**：转圈前先反向蓄力约 7°、手臂内收；挥手前手臂先向身侧收一下再抬起
    **重心转移（weight shift / pivot）**：转身时身体绕支撑脚划弧（rootZ 弧线 + rootX 侧移）、自由脚轻微离地、重心上下起伏；待机侧移幅度收敛一半，避免「平移滑步」
    **跟随与回弹（follow-through / overshoot）**：转圈采用缓入缓出五次曲线，收尾过冲约 7° 再回正；头部先转、身体后到、收尾头先回正（头领身随）；手臂摆动延迟于躯干
    **时长与节奏**：转圈 2.2s → 2.6s，动作更从容；所有关节仍经指数阻尼平滑
- **生动度（参考最新数字人做法）**：
    **语音驱动节拍手势**：借鉴 IJCAI 2025 实时语音驱动动画的思路，说话时手部/头部跟随语音节奏做小幅「打拍子」，告别「只动嘴不动身」
    **注意力扫视**：不会死盯一个点——每 2~4.5 秒快速瞟向附近某点，约一半概率伴随眨眼（真人的注视-眨眼耦合）
    **情绪唤醒余韵**：剧烈动作（跳/拍手/转圈）后呼吸频率与幅度短暂升高，再按指数衰减回平静，身体状态有连续性
    **待机微动作扩充**：新增抚发、随节奏摇摆、耸肩小抖三类，待机 6~13 秒随机触发，长时间观看不重复
    **VRMA 升级路径**：官方 `@pixiv/three-vrm-animation` 支持 `.vrma` 动作片段（可用 VRM Consortium 的 `bvh2vrma` 从 Mixamo BVH 转换）；当前无可用示例文件，接入点已预留
- **说话**：回复可选用浏览器 TTS 朗读，同步**张嘴口型动画**（VRM `aa` 表情）与轻微点头。
- **聊天**：复用现有会话与情绪引擎（persona_id=`yui`），柚子有专属人设卡与回复语料，情绪同样写入情绪档案。
- **换模型（自有模型插槽）**：加载顺序为 `frontend/public/models/avatar.vrm` → `twist-sample.vrm` → 程序化兜底。把你自己合法获得的 VRM 模型命名为 `avatar.vrm` 放进 `public/models/` 即可自动生效，无需改代码；动作/表情/待机优化全部通用。若模型来自游戏提取（FBX/GLB），需先经 Blender + VRM 插件转换导出为 VRM 才能保留人形骨骼与表情。

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
| 提示词管理 | /admin/prompts | 角色卡提示词在线编辑（四页签：角色表单+实时预览 / Markdown 全文 / 安全守则只读 / 历史版本恢复） |
| 社区审核 | /admin/forum | 帖子/评论审核与下架 |
| 会话抽查 | /admin/sessions | 会话列表（不含正文，保护隐私） |
| 系统信息 | /admin/system | 版本、存储、LLM 状态、健康检查 |

## 安全提示

- 本项目定位为**情绪陪伴工具，不替代专业心理咨询**。
- 高危情绪（自伤倾向）会引导用户联系心理援助热线（全国 12356），请勿删除该引导。
- 生产环境请修改 `JWT_SECRET`、`ADMIN_PASSWORD`，并考虑限制 CORS 来源。

> AI生成
