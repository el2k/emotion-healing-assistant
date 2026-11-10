<template>
  <div class="fortune-page">
    <header class="topbar">
      <router-link to="/" class="back">← 返回聊天</router-link>
      <span class="tb-title">🔮 测测</span>
      <span class="tb-sub">八字 · 紫微 · 每日运势</span>
    </header>

    <div class="tabs">
      <button v-for="t in tabs" :key="t.id" class="tab" :class="{ on: tab === t.id }"
              @click="switchTab(t.id)">{{ t.label }}</button>
    </div>

    <div class="container">
      <!-- ============ 每日运势 ============ -->
      <template v-if="tab === 'daily'">
        <div v-if="daily" class="card daily-card">
          <div class="dc-head">
            <div>
              <h2>{{ todayLabel }} · {{ daily.level }}</h2>
              <span class="gz">今日 {{ daily.ganzhi.month }}月 · {{ daily.ganzhi.day }}日<template v-if="daily.shengxiao"> · {{ daily.shengxiao }}生肖</template></span>
            </div>
            <div class="dc-overall">
              <div class="donut">{{ daily.scores.overall.value }}</div>
              <span>综合</span>
            </div>
          </div>

          <div class="score-grid">
            <div v-for="(s, k) in scoreList" :key="k" class="score-item">
              <div class="si-top"><span>{{ s.label }}</span><b>{{ s.value }}</b></div>
              <div class="bar"><i :style="{ width: s.value + '%' }" :class="k"></i></div>
            </div>
          </div>

          <div class="lucky-row">
            <span>🎨 幸运色 <b>{{ daily.lucky_color }}</b></span>
            <span>🔢 幸运数字 <b>{{ daily.lucky_number }}</b></span>
            <span>⏰ 吉时 <b>{{ daily.lucky_time }}</b></span>
          </div>

          <div class="do-avoid">
            <div class="da do"><b>宜</b><span v-for="d in daily.do" :key="d">{{ d }}</span></div>
            <div class="da avoid"><b>忌</b><span v-for="a in daily.avoid" :key="a">{{ a }}</span></div>
          </div>

          <!-- 算法理由（基于五行生克 / 生肖+日支） -->
          <div v-if="daily.calc_reason" class="calc-reason">
            <b>📊 推演依据（{{ daily.engine }}）</b>
            <p style="white-space: pre-line">{{ daily.calc_reason }}</p>
          </div>

          <p class="hint">💡 {{ daily.hint }}</p>
          <div class="zodiac-row">
            <span>选生肖看专属运势：</span>
            <select v-model="zodiac" class="zx-select" @change="loadDaily">
              <option value="">通用</option>
              <option v-for="z in zodiacs" :key="z" :value="z">{{ z }}</option>
            </select>
            <span v-if="birthShengxiao" class="zx-tip">（根据你的生日自动带出了 {{ birthShengxiao }}）</span>
          </div>
          <p class="disclaimer">{{ daily.disclaimer }}</p>
        </div>
      </template>

      <!-- ============ 八字 / 紫微 ============ -->
      <template v-else>
        <div class="card form-card">
          <h3>{{ tab === 'bazi' ? '☀️ 八字测评' : '🌟 紫微斗数' }}</h3>
          <p class="form-tip">输入出生信息开始排盘（信息只用于本地计算，不会出现在社区）</p>
          <div class="form-row">
            <label>出生日期</label>
            <input v-model="form.birth_date" type="date" />
            <label>出生时间</label>
            <select v-model="hourSel">
              <option value="">不确定</option>
              <option v-for="h in hourOptions" :key="h.v" :value="h.v">{{ h.t }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>性别</label>
            <select v-model="form.gender"><option>女</option><option>男</option></select>
            <button class="go-btn" :disabled="loading || !form.birth_date" @click="run">
              {{ loading ? '排盘中…' : '开始排盘' }}
            </button>
          </div>
          <p v-if="formError" class="err">{{ formError }}</p>
        </div>

        <!-- 八字结果 -->
        <div v-if="tab === 'bazi' && bazi" class="card result-card">
          <h3>你的四柱</h3>
          <div class="pillars">
            <div v-for="p in bazi.pillars" :key="p.label" class="pillar">
              <span class="pl">{{ p.label }}</span>
              <b class="pz">{{ p.gz }}</b>
              <span class="pd">{{ p.desc }}</span>
            </div>
          </div>
          <div class="meta-row">
            <span>🎂 {{ bazi.lunar_date }}</span>
            <span>🐕 生肖 · {{ bazi.shengxiao }}</span>
            <span>🌤️ 日主 {{ bazi.day_master.gan }}（{{ bazi.day_master.profile }}）</span>
          </div>

          <h4>五行分布</h4>
          <div class="wx-grid">
            <div v-for="(n, e) in bazi.wuxing" :key="e" class="wx-item" :class="{ miss: n === 0 }">
              <span class="wx-e">{{ e }}</span>
              <div class="wx-bar"><i :style="{ width: (n / 4 * 100) + '%' }"></i></div>
              <span class="wx-n">{{ n }}<em v-if="n === 0"> 缺</em></span>
            </div>
          </div>
          <p class="read">{{ bazi.summary }}</p>
          <!-- 大运 / 流年 / 流月 / 流日（可切换日期） -->
          <template v-if="bazi.dayun">
            <h4>大运排盘<span class="mini">（{{ bazi.dayun.direction }} · {{ bazi.dayun.start_age }}岁起运 · 点击大运卡片可跳到该大运起始年）</span></h4>
            <div class="dayun-row">
              <div v-for="(d, i) in bazi.dayun.dayun" :key="i"
                   class="dayun-item"
                   :class="{ current: dayunData?.current_dayun?.index === i }"
                   :title="`查看「${d.gz}」大运（公元 ${dayunYearRange(d)} 年）`"
                   @click="jumpToDayun(d)">
                <b class="dy-gz">{{ d.gz }}</b>
                <span class="dy-age">{{ d.age }}岁</span>
                <span class="dy-wx">{{ d.wuxing_gan }}·{{ d.wuxing_zhi }}</span>
                <span class="dy-year">{{ dayunYearRange(d) }}年</span>
              </div>
            </div>

            <!-- 日期选择：年 / 月 / 日 三级下拉，点击大运卡片自动带出 -->
            <div class="query-date-row">
              <label>📅 选择日期</label>
              <select v-model.number="queryYear" class="qd-sel" @change="applyQueryDate">
                <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}年</option>
              </select>
              <select v-model.number="queryMonth" class="qd-sel" @change="onMonthYearChange">
                <option v-for="m in 12" :key="m" :value="m">{{ m }}月</option>
              </select>
              <select v-model.number="queryDay" class="qd-sel" @change="applyQueryDate">
                <option v-for="d in daysInMonth" :key="d" :value="d">{{ d }}日</option>
              </select>
              <button v-if="queryDate !== todayStr" class="qd-reset" @click="resetQueryDate">
                回到今天
              </button>
            </div>

            <h4 ref="currentLuckRef">{{ queryDate === todayStr ? '当前' : queryDate }}运势{{ dayunLoading ? '（加载中…）' : '' }}</h4>
            <div class="current-luck" v-if="dayunData">
              <div class="cl-item">
                <span>大运</span>
                <b>{{ dayunData.current_dayun?.gz || '—' }}</b>
                <em>{{ dayunData.current_dayun?.age || '' }}</em>
              </div>
              <div class="cl-item">
                <span>流年</span>
                <b>{{ dayunData.current_year.gz }}</b>
                <em>{{ dayunData.current_year.wuxing_gan }}·{{ dayunData.current_year.wuxing_zhi }}</em>
              </div>
              <div class="cl-item">
                <span>流月</span>
                <b>{{ dayunData.current_month.gz }}</b>
              </div>
              <div class="cl-item">
                <span>流日</span>
                <b>{{ dayunData.current_day.gz }}</b>
              </div>
            </div>

            <!-- 交互分析 -->
            <template v-if="dayunData?.interactions?.length">
              <h4>干支交互分析<span class="mini">（{{ dayunData.query_date }}）</span></h4>
              <div class="interaction-list">
                <div v-for="(it, idx) in dayunData.interactions" :key="idx"
                     class="interaction-item" :class="it.type">
                  <div class="ia-head">
                    <span class="ia-badge">{{ it.type }}</span>
                    <b>{{ it.detail }}</b>
                    <span class="ia-src">{{ it.source }} ↔ {{ it.target }}</span>
                  </div>
                  <p class="ia-analysis">{{ it.analysis }}</p>
                </div>
              </div>
            </template>
            <div v-else-if="dayunData" class="interaction-none">
              该日与命局无显著干支交互，属于平稳期。
            </div>
          </template>

          <p class="disclaimer">{{ bazi.disclaimer }}</p>
        </div>

        <!-- 紫微结果 -->
        <div v-if="tab === 'ziwei' && ziwei" class="card result-card zw-card">
          <div class="zw-head">
            <div>
              <h3>命宫 · {{ ziwei.ming.gong_zhi }}宫（{{ ziwei.ming.gong_gan_zhi }}）</h3>
              <span class="zw-meta">{{ ziwei.ming.ju }} · 身宫在{{ ziwei.ming.body_zhi }} ·
                {{ ziwei.meta.lunar_date }} {{ ziwei.meta.hour_zhi }}时 · 生肖{{ ziwei.meta.shengxiao }}
                · 大限{{ ziwei.daxian.direction }}（{{ ziwei.daxian.start_age }}岁起）· 流年 {{ ziwei.liunian.gz }}
              </span>
            </div>
          </div>
          <p class="read">{{ ziwei.ming.summary }}</p>

          <h4>{{ liunianPan ? `流年盘 · 十二宫重排（${liunianPan.gz}年）` : '十二宫命盘' }}
            <span class="mini">（{{ liunianPan
              ? '传统盘式 · 星曜按地支落位不动，宫名以流年命宫重排 · 点击宫位看三方四正'
              : '传统盘式 · 点击任意宫查看其三方四正与解读' }}）</span>
          </h4>

          <!-- 流年盘横幅：年份切换 + 返回本命盘 -->
          <div v-if="liunianPan" class="ln-banner">
            <b>🔄 流年盘 · {{ liunianPan.gz }}（{{ liunianPan.year }}年）</b>
            <span class="ln-note">以{{ liunianPan.ming_zhi }}宫为流年命宫{{ liunianPan.source_palace ? `（来自本命${liunianPan.source_palace}）` : '' }}，星曜不动、宫名重排</span>
            <select v-model.number="lnYear" class="ln-year-sel" @change="reloadLiunian">
              <option v-for="y in lnYearOptions" :key="y" :value="y">{{ y }}年</option>
            </select>
            <button class="ln-back" @click="exitLiunian">← 返回本命盘</button>
          </div>

          <div v-if="!liunianPan" class="board-legend">
            <span class="lg lg-self">本宫</span><span class="lg lg-he">三合（三方）</span><span class="lg lg-dui">对宫</span>
            <span class="lg lg-dx">当前大限</span><span class="lg lg-ln">流年命宫</span>
            <span class="lg lg-auxg">小签=吉星辅佐</span><span class="lg lg-auxh">小签=煞星提醒</span>
            <span class="lg lg-lnage">年NN = 该宫做流年命宫的年龄</span>
          </div>
          <div v-else class="board-legend">
            <span class="lg lg-self">本宫</span><span class="lg lg-he">三合（三方）</span><span class="lg lg-dui">对宫</span>
            <span class="lg lg-ln">流年命宫</span>
            <span class="lg lg-hua">绿=流年化禄/权/科 · 红=流年化忌</span>
          </div>
          <div class="board-wrap" ref="zwBoardRef">
            <div class="board-zw">
              <!-- 十二宫按传统盘位放置 -->
              <div v-for="(p, pi) in activeBoard" :key="p.palace + p.zhi" class="house"
                   :style="gridPos(p.zhi)"
                   :class="{
                     ming: p.is_ming, body: p.is_body && !liunianPan,
                     'sf-self': selectedPalace && pi === selectedPalace.index,
                     'sf-he': selectedPalace && selectedPalace.sanfang.he.includes(pi),
                     'sf-dui': selectedPalace && selectedPalace.sanfang.dui === pi,
                   }" @click="selectPalace(p)">
                <div class="h-name">{{ p.palace }}<i v-if="p.is_ming">{{ liunianPan ? '年' : '命' }}</i><i v-if="!liunianPan && p.is_body">身</i></div>
                <div class="h-stars" :class="{ empty: !p.stars.length }">
                  <template v-if="p.stars.length">
                    <span v-for="b in p.brightness" :key="b.star"
                          class="star-br" :class="brightClass(b.level)">
                      {{ b.star }}<em>{{ b.level }}</em>
                    </span>
                  </template>
                  <template v-else>空宫</template>
                </div>
                <div v-if="p.aux?.length" class="h-aux">
                  <span v-for="a in p.aux" :key="a.star"
                        class="aux-tag" :class="a.type === '吉' ? 'lucky' : 'harsh'"
                        :title="a.trait">{{ a.star }}</span>
                </div>
                <div v-if="!liunianPan" class="h-marks">
                  <span class="dx-badge" :class="{ on: p.daxian.current }" title="大限年龄段">限{{ p.daxian.range }}</span>
                  <span v-if="p.is_liunian" class="ln-badge" title="流年命宫（年支落此宫）">流年</span>
                  <span v-if="p.liunian_upcoming?.length" class="ln-ages"
                        :class="{ hit: p.is_liunian }"
                        :title="`此宫在这些年龄成为流年命宫：${p.liunian_ages.join(' · ')} 岁`">
                    年{{ p.liunian_upcoming.join('·') }}
                  </span>
                </div>
                <div v-else class="h-marks">
                  <span v-for="t in p.sihua" :key="t" class="hua-badge" :class="huaClass(t)">{{ t }}</span>
                </div>
                <div class="h-zhi">{{ p.zhi }}</div>
              </div>
              <!-- 中心信息盘 -->
              <div class="chart-center">
                <template v-if="!liunianPan">
                  <div class="cc-row"><b>{{ ziwei.ming.ju }}</b><span>命宫 {{ ziwei.ming.gong_zhi }}（{{ ziwei.ming.gong_gan_zhi }}）</span></div>
                  <div class="cc-row"><b>身宫</b><span>{{ ziwei.ming.body_zhi }} · {{ ziwei.meta.shengxiao }} · {{ ziwei.meta.hour_zhi }}时</span></div>
                  <div class="cc-row"><b>大限</b><span>{{ ziwei.daxian.direction }} · {{ ziwei.daxian.start_age }}岁起 · 现约{{ ziwei.daxian.age }}岁</span></div>
                  <div class="cc-row"><b>流年</b><span>{{ ziwei.liunian.gz }}</span></div>
                  <div v-if="ziwei.sihua?.items?.length" class="cc-sihua">
                    <span v-for="it in ziwei.sihua.items" :key="it">{{ it.split('：')[0] }}</span>
                  </div>
                </template>
                <template v-else>
                  <div class="cc-row"><b>流年</b><span>{{ liunianPan.gz }}（{{ liunianPan.year }}年）· 流年命宫 {{ liunianPan.ming_zhi }}</span></div>
                  <div v-if="liunianPan.sihua?.items?.length" class="cc-sihua">
                    <span v-for="it in liunianPan.sihua.items" :key="it">{{ it.split('：')[0] }}</span>
                  </div>
                  <div class="cc-tip">流年四化按流年天干起，落在哪个宫、就看那个领域今年的事件感</div>
                </template>
                <div class="cc-tip">亮度 庙&gt;旺&gt;得&gt;利&gt;平&gt;不&gt;陷<br/>点击宫位查看三方四正</div>
              </div>
            </div>
          </div>
          <transition name="fade">
            <div v-if="selectedPalace" class="palace-detail">
              <b>{{ selectedPalace.palace }}（{{ selectedPalace.zhi }}宫） · {{ selectedPalace.stars_label }}
                 <template v-if="selectedPalace.daxian"> · 大限 {{ selectedPalace.daxian.range }}{{ selectedPalace.daxian.current ? '（当前）' : '' }}</template>
                 <template v-if="selectedPalace.sihua?.length"> · {{ selectedPalace.sihua.join(' / ') }}</template>
              </b>

              <!-- 三方四正总览：本宫 + 两三合 + 对宫 -->
              <div class="trine-block">
                <div class="tb-title">🔗 三方四正（这四宫一起看才完整）</div>
                <div v-for="(row, ri) in trineRows" :key="ri" class="trine-row" :class="row.cls">
                  <span class="tr-role">{{ row.role }}</span>
                  <span class="tr-palace">{{ row.p.palace }}（{{ row.p.zhi }}）</span>
                  <span class="tr-stars">
                    <template v-if="row.p.stars.length">
                      <span v-for="b in row.p.brightness" :key="b.star" class="star-br"
                            :class="brightClass(b.level)">{{ b.star }}<em>{{ b.level }}</em></span>
                    </template>
                    <template v-else>空宫</template>
                    <span v-if="row.p.aux?.length" class="tr-aux">
                      <span v-for="a in row.p.aux" :key="a.star" class="aux-tag"
                            :class="a.type === '吉' ? 'lucky' : 'harsh'">{{ a.star }}</span>
                    </span>
                  </span>
                  <span class="tr-note">{{ row.note }}</span>
                </div>
                <p class="tr-tip">💡 三方四正 = 本宫 + 两个三合宫 + 对宫，是紫微看一个领域的完整视角：
                  本宫是主场景，三合是资源与助力，对宫是外部牵动与对照。</p>
              </div>

              <div v-if="selectedPalace.brightness?.length" class="pd-bright">
                <span v-for="b in selectedPalace.brightness" :key="b.star"
                      class="star-br" :class="brightClass(b.level)">
                  {{ b.star }} {{ b.level }} — {{ b.desc }}
                </span>
              </div>
              <div v-if="selectedPalace.aux?.length" class="pd-aux">
                <b>✨ 辅星</b>
                <div v-for="a in selectedPalace.aux" :key="a.star" class="pa-row">
                  <span class="aux-tag" :class="a.type === '吉' ? 'lucky' : 'harsh'">{{ a.star }}</span>
                  <em>{{ a.trait }}</em>
                  <i>{{ a.hint }}</i>
                </div>
              </div>
              <p>{{ selectedPalace.interpretation }}</p>
              <p class="tips">小建议：{{ selectedPalace.tips }}</p>
              <div class="pd-actions">
                <button v-if="!liunianPan" class="to-ln-btn" :disabled="ziweiLoading"
                        @click="enterLiunian(selectedPalace)">
                  🔄 以此宫为流年命宫 · 看流年盘
                </button>
                <button v-else class="to-ln-btn" :disabled="ziweiLoading"
                        @click="enterLiunian(selectedPalace)">
                  🔄 以此宫为流年命宫 · 重新重排
                </button>
                <button class="close-pd" @click="selectedPalace = null">收起</button>
              </div>
            </div>
          </transition>
          <!-- 生年四化 -->
          <template v-if="ziwei.sihua?.items?.length">
            <h4>生年四化<span class="mini">（年干 {{ ziwei.sihua.year_stem }}）</span></h4>
            <div class="sihua-grid">
              <div v-for="item in ziwei.sihua.items" :key="item" class="sihua-item">
                {{ item }}
              </div>
            </div>
          </template>
          <p class="disclaimer">{{ ziwei.disclaimer }}</p>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'

const tabs = [
  { id: 'daily', label: '📅 每日运势' },
  { id: 'bazi', label: '☀️ 八字' },
  { id: 'ziwei', label: '🌟 紫微斗数' },
]
const tab = ref('daily')
const loading = ref(false)
const formError = ref('')

/* 每日运势 */
const daily = ref(null)
const zodiac = ref('')
const zodiacs = ['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪']
const birthShengxiao = ref(
  (() => { try { return localStorage.getItem('eh_shengxiao') || '' } catch (e) { return '' } })()
)
const savedDayMaster = ref((() => {
  try {
    const raw = localStorage.getItem('eh_day_master')
    return raw ? JSON.parse(raw) : null
  } catch (e) { return null }
})())
const todayLabel = new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' })
const scoreList = computed(() => {
  if (!daily.value) return {}
  const { overall, ...rest } = daily.value.scores
  return rest
})

async function loadDaily() {
  try {
    const dm = savedDayMaster.value
    const params = {
      shengxiao: zodiac.value || birthShengxiao.value,
      ...(dm ? { day_master_gan: dm.gan, day_master_wuxing: dm.wuxing } : {}),
    }
    const { data } = await api.get('/fortune/daily', { params })
    daily.value = data
  } catch (e) { formError.value = '运势加载失败，请重试' }
}

/* 八字 / 紫微 */
const hourOptions = [
  { v: 0, t: '子时 23-01' }, { v: 1, t: '丑时 01-03' }, { v: 3, t: '寅时 03-05' },
  { v: 5, t: '卯时 05-07' }, { v: 7, t: '辰时 07-09' }, { v: 9, t: '巳时 09-11' },
  { v: 11, t: '午时 11-13' }, { v: 13, t: '未时 13-15' }, { v: 15, t: '申时 15-17' },
  { v: 17, t: '酉时 17-19' }, { v: 19, t: '戌时 19-21' }, { v: 21, t: '亥时 21-23' },
]
const form = reactive({ birth_date: '', gender: '女' })
const hourSel = ref('')
const bazi = ref(null)
const ziwei = ref(null)
const selectedPalace = ref(null)
/* 本次排盘实际使用的出生信息（防止用户改了表单未重新排盘时查询错位） */
const lastBirth = ref(null)
/* 滚动锚点：当前运势标题 / 紫微盘面 */
const currentLuckRef = ref(null)
const zwBoardRef = ref(null)

/* 紫微流年盘：liunianPan 有值时盘面切为流年盘 */
const liunianPan = ref(null)
const ziweiLoading = ref(false)
const lnYear = ref(new Date().getFullYear())
const lnYearOptions = (() => {
  const ys = [], nowY = new Date().getFullYear()
  for (let y = nowY - 5; y <= nowY + 5; y++) ys.push(y)
  return ys
})()

function huaClass(tag) {
  return tag.endsWith('化忌') ? 'hua-ji' : 'hua-ji-x'
}

/* 当前渲染的盘面：流年盘优先，否则本命盘 */
const activeBoard = computed(() =>
  (liunianPan.value ? liunianPan.value.board : ziwei.value?.board) || [])

/* 选中宫位的三方四正（本宫+两三合+对宫），从当前盘面按下标取 */
function selectPalace(p) { selectedPalace.value = p }

const trineRows = computed(() => {
  if (!selectedPalace.value || !activeBoard.value.length) return []
  const b = activeBoard.value
  const sf = selectedPalace.value.sanfang
  if (!sf) return []
  return [
    { role: '本宫', cls: 'self', p: selectedPalace.value, note: '主场景' },
    { role: '三合', cls: 'he', p: b[sf.he[0]], note: '资源助力·三方' },
    { role: '三合', cls: 'he', p: b[sf.he[1]], note: '资源助力·三方' },
    { role: '对宫', cls: 'dui', p: b[sf.dui], note: '外部牵动·对照' },
  ]
})

/* 星曜亮度配色：庙旺绿、得利紫、平灰、不陷红 */
function brightClass(level) {
  if (['庙', '旺'].includes(level)) return 'br-strong'
  if (['得', '利'].includes(level)) return 'br-mid'
  if (level === '平') return 'br-flat'
  return 'br-dim'  // 不 / 陷
}

/* 传统盘式：地支在 4×4 方盘上的固定位置（巳午未申在上，亥子丑寅在下，卯辰在左，酉戌在右） */
const ZHI_POS = {
  '巳': [1, 1], '午': [1, 2], '未': [1, 3], '申': [1, 4],
  '辰': [2, 1], '酉': [2, 4],
  '卯': [3, 1], '戌': [3, 4],
  '寅': [4, 1], '丑': [4, 2], '子': [4, 3], '亥': [4, 4],
}
function gridPos(zhi) {
  const pos = ZHI_POS[zhi] || [1, 1]
  return { gridRow: pos[0], gridColumn: pos[1] }
}

function switchTab(t) {
  tab.value = t
  formError.value = ''
  if (t === 'daily' && !daily.value) loadDaily()
}

async function run() {
  formError.value = ''
  if (!form.birth_date) return
  loading.value = true
  try {
    const payload = {
      birth_date: form.birth_date,
      birth_hour: hourSel.value === '' ? null : Number(hourSel.value),
      gender: form.gender,
    }
    if (tab.value === 'bazi') {
      const { data } = await api.post('/fortune/bazi', payload)
      bazi.value = data
      dayunData.value = data.dayun
      lastBirth.value = { ...payload }
      queryDate.value = todayStr
      syncQueryPickers(todayStr)
      try {
        localStorage.setItem('eh_shengxiao', data.shengxiao)
        localStorage.setItem('eh_day_master', JSON.stringify({
          gan: data.day_master.gan, wuxing: data.day_master.wuxing,
        }))
        savedDayMaster.value = { gan: data.day_master.gan, wuxing: data.day_master.wuxing }
      } catch (e) { /* 忽略 */ }
      birthShengxiao.value = data.shengxiao
    } else {
      const { data } = await api.post('/fortune/ziwei', payload)
      ziwei.value = data
      selectedPalace.value = null
      liunianPan.value = null
      lastBirth.value = { ...payload }
    }
  } catch (e) {
    formError.value = e.response?.data?.detail || '排盘失败，请检查日期格式'
  } finally {
    loading.value = false
  }
}

/* 大运日期切换：年/月/日三级下拉，同步 queryDate 后查询 */
const todayStr = new Date().toISOString().slice(0, 10)
const queryDate = ref(todayStr)
const dayunData = ref(null)
const dayunLoading = ref(false)
const queryYear = ref(Number(todayStr.slice(0, 4)))
const queryMonth = ref(Number(todayStr.slice(5, 7)))
const queryDay = ref(Number(todayStr.slice(8, 10)))

/* 出生年（本次排盘实际使用的） */
const birthYear = computed(() =>
  lastBirth.value ? Number(lastBirth.value.birth_date.slice(0, 4)) : Number(todayStr.slice(0, 4)))
/* 年份选项：出生年起 100 年（覆盖 8 步大运） */
const yearOptions = computed(() => {
  const ys = []
  for (let y = birthYear.value; y <= birthYear.value + 100; y++) ys.push(y)
  return ys
})
/* 当年当月实际天数（自动处理闰年） */
const daysInMonth = computed(() => new Date(queryYear.value, queryMonth.value, 0).getDate())

function pad2(n) { return String(n).padStart(2, '0') }
function syncQueryPickers(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number)
  queryYear.value = y
  queryMonth.value = m
  queryDay.value = d
}

function applyQueryDate() {
  if (queryDay.value > daysInMonth.value) queryDay.value = daysInMonth.value
  if (queryDay.value < 1) queryDay.value = 1
  queryDate.value = `${queryYear.value}-${pad2(queryMonth.value)}-${pad2(queryDay.value)}`
  loadDayunForDate()
}

function onMonthYearChange() {
  if (queryDay.value > daysInMonth.value) queryDay.value = daysInMonth.value
  applyQueryDate()
}

/* 大运卡片 → 公元年份区间（岁数 + 出生年） */
function dayunYearRange(d) {
  const y0 = birthYear.value + d.age_from
  const y1 = birthYear.value + d.age_to - 1
  return `${y0}-${y1}`
}

/* 点击大运卡片：跳到该大运起始年（出生月日），加载那年运势并滚动到结果 */
function jumpToDayun(d) {
  if (!lastBirth.value) return
  const by = birthYear.value
  let targetYear = by + d.age_from
  if (targetYear < by) targetYear = by
  if (targetYear > by + 100) return
  queryYear.value = targetYear
  queryMonth.value = Number(lastBirth.value.birth_date.slice(5, 7))
  queryDay.value = Number(lastBirth.value.birth_date.slice(8, 10))
  applyQueryDate()
  nextTick(() => {
    currentLuckRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

async function loadDayunForDate() {
  if (!lastBirth.value || !queryDate.value) return
  dayunLoading.value = true
  try {
    const { data } = await api.post('/fortune/dayun', {
      birth_date: lastBirth.value.birth_date,
      birth_hour: lastBirth.value.birth_hour,
      gender: lastBirth.value.gender,
      query_date: queryDate.value,
    })
    dayunData.value = data
  } catch (e) { /* 忽略 */ } finally {
    dayunLoading.value = false
  }
}

function resetQueryDate() {
  syncQueryPickers(todayStr)
  queryDate.value = todayStr
  loadDayunForDate()
}

/* ============ 紫微流年盘：点击宫位 → 以该宫为流年命宫重排十二宫 ============ */
async function requestZiwei(gongZhi, year) {
  if (!lastBirth.value) return
  ziweiLoading.value = true
  try {
    const { data } = await api.post('/fortune/ziwei', {
      ...lastBirth.value,
      liunian_gong_zhi: gongZhi,
      liunian_year: year,
    })
    ziwei.value = data
    liunianPan.value = data.liunian_pan || null
  } catch (e) {
    formError.value = e.response?.data?.detail || '流年盘生成失败，请重试'
  } finally {
    ziweiLoading.value = false
  }
}

async function enterLiunian(p) {
  await requestZiwei(p.zhi, lnYear.value)
  selectedPalace.value = null
  nextTick(() => {
    zwBoardRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

function exitLiunian() {
  liunianPan.value = null
  selectedPalace.value = null
}

async function reloadLiunian() {
  if (liunianPan.value) {
    await requestZiwei(liunianPan.value.ming_zhi, lnYear.value)
    selectedPalace.value = null
  }
}

onMounted(() => { loadDaily() })
</script>

<style scoped>
.fortune-page { min-height: 100vh; background: linear-gradient(180deg, #f6f2ff 0%, var(--bg) 300px); padding-bottom: 60px; }
.topbar { display: flex; align-items: center; gap: 14px; padding: 14px 28px; background: rgba(255,255,255,.92); backdrop-filter: blur(8px); border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.back { font-size: 14px; }
.tb-title { font-size: 17px; font-weight: 700; color: var(--primary); }
.tb-sub { font-size: 12.5px; color: var(--text-soft); }

.tabs { display: flex; gap: 10px; justify-content: center; margin: 22px auto 0; }
.tab { border: 1px solid var(--border); background: #fff; border-radius: 20px; padding: 9px 22px; font-size: 14px; color: var(--text-soft); cursor: pointer; transition: all .15s; }
.tab.on { background: var(--primary); color: #fff; border-color: var(--primary); box-shadow: 0 6px 16px rgba(124,111,208,.3); }

.container { max-width: 860px; margin: 18px auto 0; padding: 0 20px; display: flex; flex-direction: column; gap: 16px; }
.card { background: #fff; border: 1px solid var(--border); border-radius: 18px; padding: 24px; box-shadow: var(--shadow); }

/* 每日运势 */
.dc-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
.dc-head h2 { font-size: 21px; }
.gz { font-size: 12.5px; color: var(--text-soft); }
.dc-overall { text-align: center; }
.donut { width: 86px; height: 86px; border-radius: 50%; border: 6px solid var(--primary-soft); display: flex; align-items: center; justify-content: center; font-size: 26px; font-weight: 800; color: var(--primary); background: conic-gradient(var(--primary) var(--p, 70%), transparent 0); }
.donut { background: #fdfbff; border-color: #e9e2ff; }
.dc-overall span { font-size: 12px; color: var(--text-soft); }

.score-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
@media (max-width: 640px) { .score-grid { grid-template-columns: 1fr; } }
.score-item .si-top { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 5px; }
.si-top b { color: #5f54a3; }
.bar { height: 8px; border-radius: 4px; background: #f1ecfa; overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: 4px; background: linear-gradient(90deg, #b9aaff, #7c6fd0); transition: width .6s ease; }
.bar i.love { background: linear-gradient(90deg, #f7b6c2, #e0618a); }
.bar i.wealth { background: linear-gradient(90deg, #ecd28f, #d6a02e); }
.bar i.career { background: linear-gradient(90deg, #9fd6c2, #2f9e6b); }
.bar i.health { background: linear-gradient(90deg, #a8c9f0, #3d8fd0); }

.lucky-row { display: flex; gap: 22px; flex-wrap: wrap; margin: 18px 0; padding: 12px 16px; background: #faf8ff; border-radius: 12px; font-size: 13.5px; color: var(--text-soft); }
.lucky-row b { color: #4a4360; }
.do-avoid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 640px) { .do-avoid { grid-template-columns: 1fr; } }
.da { border-radius: 12px; padding: 12px 14px; font-size: 13px; }
.da b { display: inline-block; width: 24px; height: 24px; border-radius: 50%; text-align: center; line-height: 24px; color: #fff; margin-right: 8px; font-size: 12.5px; }
.da.do { background: #eaf7f0; } .da.do b { background: #2f9e6b; }
.da.avoid { background: #fdf0f2; } .da.avoid b { background: #d9536b; }
.da span { display: inline-block; margin: 3px 10px 0 0; color: #4a4360; }
.hint { margin-top: 14px; font-size: 13.5px; color: #6f63b8; background: var(--primary-soft); padding: 10px 14px; border-radius: 10px; }
.zodiac-row { margin-top: 14px; font-size: 12.5px; color: var(--text-soft); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.zx-select { border: 1px solid var(--border); border-radius: 8px; padding: 5px 10px; font-size: 13px; }
.zx-tip { color: #b9b3c9; }
.disclaimer { margin-top: 14px; font-size: 11.5px; color: #b9b3c9; }

/* 算法理由 */
.calc-reason { margin-top: 14px; background: #f0faf5; border: 1px solid #c9ede0; border-radius: 10px; padding: 10px 14px; }
.calc-reason b { font-size: 12.5px; color: #2f9e6b; display: block; margin-bottom: 6px; }
.calc-reason p { font-size: 12.5px; color: #4a4360; line-height: 1.8; }

/* 大运 */
.dayun-row { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 6px; }
.dayun-item { flex: none; text-align: center; border: 1px solid #eee9f7; border-radius: 10px; padding: 10px 8px; min-width: 76px; background: #fdfcff; cursor: pointer; transition: all .15s; }
.dayun-item:hover { transform: translateY(-2px); box-shadow: 0 6px 14px rgba(124,111,208,.18); border-color: #d9d0ef; }
.dayun-item.current { background: linear-gradient(160deg, #f3efff, #fdf1f5); border-color: #d9c8f5; }
.dy-gz { display: block; font-size: 18px; color: #5f54a3; }
.dy-age { display: block; font-size: 11px; color: var(--text-soft); margin-top: 4px; }
.dy-wx { display: block; font-size: 10px; color: #b9b3c9; }
.dy-year { display: block; font-size: 9.5px; color: #9a94ab; margin-top: 3px; }

.current-luck { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
@media (max-width: 640px) { .current-luck { grid-template-columns: repeat(2, 1fr); } }
.cl-item { border: 1px solid #eee9f7; border-radius: 10px; padding: 10px; text-align: center; background: #fdfcff; }
.cl-item span { display: block; font-size: 11px; color: var(--text-soft); }
.cl-item b { display: block; font-size: 20px; color: #5f54a3; margin-top: 4px; }
.cl-item em { display: block; font-style: normal; font-size: 10.5px; color: #b9b3c9; }

/* 日期选择器（年/月/日三级下拉） */
.query-date-row { display: flex; align-items: center; gap: 10px; margin: 18px 0; flex-wrap: wrap; }
.query-date-row label { font-size: 13px; color: var(--text-soft); }
.qd-sel { border: 1px solid var(--primary); border-radius: 10px; padding: 8px 10px; font-size: 14px; background: var(--primary-soft); outline: none; cursor: pointer; }
.qd-reset { border: none; background: #f4f1fb; color: var(--primary); border-radius: 8px; padding: 8px 14px; font-size: 12.5px; cursor: pointer; }

/* 流年盘横幅 */
.ln-banner { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: 0 0 12px; padding: 12px 16px; border-radius: 12px; background: linear-gradient(135deg, #fff6ec, #fdf2f8); border: 1px solid #f3d9b8; }
.ln-banner b { font-size: 14.5px; color: #b26a1d; }
.ln-note { font-size: 12px; color: #9a7b52; }
.ln-year-sel { border: 1px solid #e0b06a; border-radius: 8px; padding: 6px 10px; font-size: 13px; background: #fff; outline: none; cursor: pointer; }
.ln-back { border: none; background: #fff; color: #b26a1d; border: 1px solid #e0b06a; border-radius: 8px; padding: 6px 14px; font-size: 12.5px; cursor: pointer; margin-left: auto; }
.ln-back:hover { background: #fdf6ec; }

/* 流年四化徽章：禄/权/科 绿，忌红 */
.hua-badge { font-size: 9.5px; padding: 1px 5px; border-radius: 6px; font-weight: 600; background: #e9f8ef; color: #2f9e6b; }
.hua-badge.hua-ji { background: #fdeef0; color: #d9536b; }
.lg-hua { background: #e9f8ef; color: #2f9e6b; }

/* 详情面板操作区 */
.pd-actions { display: flex; align-items: center; gap: 12px; margin-top: 10px; flex-wrap: wrap; }
.to-ln-btn { border: none; background: linear-gradient(135deg, #e8a04c, #d97b3f); color: #fff; border-radius: 10px; padding: 8px 16px; font-size: 12.5px; cursor: pointer; box-shadow: 0 4px 10px rgba(217,123,63,.25); }
.to-ln-btn:disabled { opacity: .5; cursor: not-allowed; }

/* 交互分析 */
.interaction-list { display: flex; flex-direction: column; gap: 10px; }
.interaction-item { border: 1px solid #eee9f7; border-radius: 12px; padding: 12px 14px; background: #fdfcff; }
.interaction-item.地支相冲 { border-color: #f3c2cb; background: #fdf2f4; }
.interaction-item.天干合化 { border-color: #c9ede0; background: #f0faf5; }
.interaction-item.地支六合 { border-color: #c9ede0; background: #f0faf5; }
.ia-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ia-badge { font-size: 10.5px; font-weight: 600; padding: 2px 8px; border-radius: 8px; background: #f2eefc; color: #6f63b8; }
.interaction-item.地支相冲 .ia-badge { background: #fdeef0; color: #d9536b; }
.interaction-item.天干合化 .ia-badge { background: #e9f8ef; color: #2f9e6b; }
.interaction-item.地支六合 .ia-badge { background: #e9f8ef; color: #2f9e6b; }
.ia-head b { font-size: 15px; color: #5f54a3; }
.ia-src { font-size: 12px; color: #9a94ab; margin-left: auto; }
.ia-analysis { font-size: 13px; color: #4a4360; line-height: 1.8; margin-top: 8px; }
.interaction-none { font-size: 13px; color: var(--text-soft); padding: 16px 0; text-align: center; background: #faf8ff; border-radius: 10px; }

/* 四化 */
.sihua-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
@media (max-width: 640px) { .sihua-grid { grid-template-columns: 1fr; } }
.sihua-item { border: 1px dashed #d9c8f5; border-radius: 10px; padding: 10px 14px; font-size: 12.5px; color: #4a4360; background: #faf8ff; line-height: 1.7; }

/* 表单 */
.form-card h3 { font-size: 16px; margin-bottom: 6px; }
.form-tip { font-size: 12.5px; color: var(--text-soft); margin-bottom: 14px; }
.form-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.form-row label { font-size: 13px; color: var(--text-soft); }
.form-row input, .form-row select { border: 1px solid var(--border); border-radius: 10px; padding: 9px 12px; font-size: 14px; background: #fbfaff; }
.form-row input:focus, .form-row select:focus { outline: none; border-color: var(--primary); }
.go-btn { margin-left: auto; border: none; background: linear-gradient(135deg, var(--primary), var(--accent)); color: #fff; border-radius: 12px; padding: 11px 26px; font-size: 14px; box-shadow: 0 5px 14px rgba(124,111,208,.3); }
.go-btn:disabled { opacity: .5; }
.err { color: #d9536b; font-size: 13px; }

/* 八字结果 */
.result-card h3, .result-card h4 { font-size: 16px; margin: 6px 0 14px; }
.result-card h4 { margin-top: 22px; }
.mini { font-size: 11.5px; color: var(--text-soft); font-weight: 400; margin-left: 8px; }
.pillars { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
@media (max-width: 640px) { .pillars { grid-template-columns: repeat(2, 1fr); } }
.pillar { text-align: center; border: 1px solid #eee9f7; border-radius: 14px; padding: 14px 8px; background: #fdfcff; }
.pl { font-size: 12px; color: var(--text-soft); display: block; }
.pz { font-size: 26px; letter-spacing: 3px; color: #5f54a3; display: block; margin: 8px 0; }
.pd { font-size: 11.5px; color: #b9b3c9; }
.meta-row { display: flex; gap: 18px; flex-wrap: wrap; margin-top: 16px; font-size: 13px; color: var(--text-soft); }
.wx-grid { display: flex; flex-direction: column; gap: 8px; }
.wx-item { display: grid; grid-template-columns: 30px 1fr 60px; align-items: center; gap: 12px; }
.wx-item.miss .wx-bar i { background: #e5e0f0; }
.wx-e { font-size: 14px; font-weight: 700; color: #6f63b8; }
.wx-bar { height: 10px; border-radius: 5px; background: #f1ecfa; overflow: hidden; }
.wx-bar i { display: block; height: 100%; border-radius: 5px; background: linear-gradient(90deg, #b9aaff, var(--primary)); transition: width .6s; }
.wx-n { font-size: 12.5px; color: var(--text-soft); text-align: right; }
.wx-n em { font-style: normal; color: #d9536b; font-size: 11px; }
.read { margin-top: 16px; font-size: 14px; line-height: 2; color: #4a4360; background: #faf8ff; border-radius: 12px; padding: 14px 16px; white-space: pre-line; }

/* 紫微 */
.zw-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.zw-meta { font-size: 12.5px; color: var(--text-soft); }
/* 传统 4×4 方形命盘（外圈十二宫 + 中心信息盘） */
.board-wrap { overflow-x: auto; padding-bottom: 4px; }
.board-zw {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  grid-template-rows: repeat(4, minmax(104px, auto));
  gap: 7px;
  min-width: 620px;
}
.chart-center {
  grid-row: 2 / 4; grid-column: 2 / 4;
  border: 1px dashed #d9c8f5; border-radius: 14px;
  background: linear-gradient(160deg, #fbf9ff, #fdf6f9);
  padding: 12px 16px; display: flex; flex-direction: column; justify-content: center; gap: 7px;
}
.cc-row { display: flex; align-items: baseline; gap: 8px; font-size: 12.5px; color: #4a4360; }
.cc-row b { font-size: 12px; color: #fff; background: var(--primary); border-radius: 7px; padding: 1px 8px; flex: none; }
.cc-sihua { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 2px; }
.cc-sihua span { font-size: 10.5px; color: #6f63b8; background: #f2eefc; padding: 1px 7px; border-radius: 8px; }
.cc-tip { font-size: 10.5px; color: #b9b3c9; line-height: 1.7; margin-top: 2px; }
.house { border: 1px solid #eee9f7; border-radius: 12px; padding: 8px 8px 18px; cursor: pointer; transition: all .15s; background: #fdfcff; position: relative; }
.house:hover { transform: translateY(-2px); box-shadow: 0 8px 18px rgba(124,111,208,.15); border-color: #d9d0ef; }
.house.ming { background: linear-gradient(160deg, #f3efff, #fdf1f5); border-color: #d9c8f5; }

/* 三方四正高亮 */
.house.sf-self { outline: 2.5px solid var(--primary); outline-offset: 1px; background: #f1ebff; }
.house.sf-he { border-color: #4cb98a; background: #edf9f2; box-shadow: inset 0 0 0 1px #bce8d2; }
.house.sf-dui { border-color: #e0954a; background: #fdf4ea; box-shadow: inset 0 0 0 1px #f3d9b8; }

/* 图例 */
.board-legend { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.lg { font-size: 11px; padding: 2px 9px; border-radius: 10px; border: 1px solid transparent; }
.lg-self { background: #f1ebff; color: var(--primary); border-color: var(--primary); }
.lg-he { background: #edf9f2; color: #2f9e6b; border-color: #4cb98a; }
.lg-dui { background: #fdf4ea; color: #b26a1d; border-color: #e0954a; }
.lg-dx { background: #f2eefc; color: #6f63b8; }
.lg-ln { background: #fdeef0; color: #d9536b; }
.lg-auxg { background: #e6f5f5; color: #3d8f8f; }
.lg-auxh { background: #faeee9; color: #b3624a; }
.lg-lnage { background: #f6f4f8; color: #8b869b; }

/* 宫位卡片上的标记 */
.h-marks { display: flex; gap: 4px; margin-top: 4px; flex-wrap: wrap; }
.dx-badge { font-size: 9.5px; color: #8b869b; background: #f4f2f8; padding: 1px 5px; border-radius: 6px; }
.dx-badge.on { color: #fff; background: var(--primary); font-weight: 600; }
.ln-badge { font-size: 9.5px; color: #d9536b; background: #fdeef0; padding: 1px 5px; border-radius: 6px; font-weight: 600; }
.ln-ages { font-size: 9.5px; color: #8b869b; background: #f6f4f8; padding: 1px 5px; border-radius: 6px; }
.ln-ages.hit { color: #d9536b; background: #fdeef0; font-weight: 600; }

/* 三方四正总览 */
.trine-block { margin: 12px 0 4px; border: 1px dashed #d9d0ef; border-radius: 12px; padding: 12px 14px; background: #fbf9ff; }
.tb-title { font-size: 13px; font-weight: 700; color: #5f54a3; margin-bottom: 8px; }
.trine-row { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 8px; margin-bottom: 4px; background: #fff; flex-wrap: wrap; }
.trine-row.self { border: 1.5px solid var(--primary); }
.trine-row.he { border: 1px solid #4cb98a; background: #f4fbf7; }
.trine-row.dui { border: 1px solid #e0954a; background: #fdf8f1; }
.tr-role { font-size: 11px; font-weight: 700; color: #6f63b8; flex: none; width: 34px; }
.trine-row.he .tr-role { color: #2f9e6b; }
.trine-row.dui .tr-role { color: #b26a1d; }
.tr-palace { font-size: 12.5px; font-weight: 600; color: #4a4360; flex: none; }
.tr-stars { display: flex; gap: 4px; flex-wrap: wrap; }
.tr-note { font-size: 10.5px; color: #b9b3c9; margin-left: auto; }
.tr-tip { font-size: 11.5px; color: var(--text-soft); margin-top: 8px; line-height: 1.7; }
.h-name { font-size: 12.5px; font-weight: 700; color: #5f54a3; margin-bottom: 6px; }
.h-name i { font-style: normal; font-size: 10px; background: var(--primary); color: #fff; border-radius: 50%; width: 14px; height: 14px; display: inline-block; line-height: 14px; text-align: center; margin-left: 4px; }
.h-stars { font-size: 11.5px; color: #4a4360; line-height: 1.55; min-height: 36px; }
.h-stars.empty { color: #b9b3c9; }

/* 星曜亮度 */
.star-br { display: inline-block; margin-right: 3px; }

/* 辅星标签（吉星蓝绿 / 煞星砖红，小一号与主星区分） */
.h-aux { margin-top: 3px; }
.aux-tag { display: inline-block; margin: 0 3px 2px 0; font-size: 10px; padding: 0 5px; border-radius: 7px; font-weight: 500; }
.aux-tag.lucky { color: #3d8f8f; background: #e6f5f5; }
.aux-tag.harsh { color: #b3624a; background: #faeee9; }
.tr-aux { display: inline-flex; gap: 3px; margin-left: 4px; vertical-align: middle; }
.star-br em { font-style: normal; font-size: 9.5px; padding: 0 2px; border-radius: 4px; font-weight: 600; }
.br-strong em { color: #2f9e6b; background: #e9f8ef; }
.br-mid em { color: #6f63b8; background: #f2eefc; }
.br-flat em { color: #8b869b; background: #f4f2f8; }
.br-dim em { color: #d9536b; background: #fdeef0; }
.pd-bright { display: flex; flex-direction: column; gap: 4px; margin: 10px 0 2px; padding: 10px 12px; background: #faf8ff; border-radius: 10px; }
.pd-aux { margin: 8px 0 2px; padding: 10px 12px; background: #f8fbfa; border: 1px dashed #cde6e2; border-radius: 10px; }
.pd-aux b { font-size: 12.5px; color: #3d8f8f; display: block; margin-bottom: 6px; }
.pa-row { display: flex; align-items: baseline; gap: 8px; font-size: 12.5px; padding: 2px 0; flex-wrap: wrap; }
.pa-row em { font-style: normal; color: #4a4360; }
.pa-row i { font-style: normal; font-size: 11.5px; color: #9a94ab; }
.pd-bright .star-br { font-size: 12.5px; color: #4a4360; }
.pd-bright .br-strong { color: #2f9e6b; }
.pd-bright .br-mid { color: #6f63b8; }
.pd-bright .br-dim { color: #d9536b; }
.h-zhi { position: absolute; right: 9px; bottom: 7px; font-size: 11px; color: #b9b3c9; }
.palace-detail { margin-top: 14px; background: #faf8ff; border: 1px dashed #d9d0ef; border-radius: 12px; padding: 14px 16px; }
.palace-detail b { font-size: 14px; color: #5f54a3; }
.palace-detail p { font-size: 13.5px; line-height: 1.9; margin-top: 8px; color: #4a4360; }
.palace-detail .tips { color: #6f6885; font-size: 12.5px; }
.close-pd { border: none; background: transparent; color: var(--primary); font-size: 12.5px; cursor: pointer; margin-top: 6px; }
.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>