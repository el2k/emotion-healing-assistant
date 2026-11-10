<template>
  <div ref="wrapEl" class="vrm-wrap">
    <canvas ref="cnvEl" class="vrm-canvas"></canvas>
    <div class="vrm-hint">🖱 拖动旋转 · 点击她会有反应</div>
  </div>
</template>

<script setup>
/**
 * VrmGirl —— 3D 聊天角色（JK 元气少女「柚子」）
 *
 * 方案（参考 pixiv/three-vrm、pixiv/ChatVRM、moeru-ai/airi 的开源实现）：
 *   1) 首选：three-vrm 加载 GitHub 开源 VRM 模型（three-vrm 官方示例模型），
 *      用 normalized humanoid 骨骼 + expression 表情做情绪驱动；
 *   2) 兜底：Three.js 程序化建模（几何体拼装），模型加载失败时自动启用，永不空白。
 *
 * 动画 = 每帧重置「待机姿态」再叠加「动作偏移」，情绪→动作映射由父组件调用 playAnim()。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm'

const emit = defineEmits(['poke'])

const wrapEl = ref(null)
const cnvEl = ref(null)

const MODEL_URL = '/models/twist-sample.vrm'
const COL = {
  skin: 0xffe3d0, hair: 0x7a4a2f, white: 0xf7f8fc, navy: 0x2b3a67,
  skirt: 0x31406f, red: 0xd94f5c, sock: 0xf2f3fa, shoe: 0x6b4a35,
  eye: 0x5b3b2a, blush: 0xff9fb0, pack: 0x9fc3e8, mouthIn: 0xb23b4e,
}
const DUR = {
  wave: 1.8, nod: 1.3, jump: 1.9, clap: 1.4, curious: 1.8, sad: 2.4,
  anxious: 2.0, scared: 1.6, protect: 2.2, pat: 1.6, spin: 2.6,
  surprise: 1.0, stomp: 1.4,
}

let renderer, scene, camera, clock, rafId, wrap, disposeFns = []
let model, J = {}
let mode = 'loading' // loading | vrm | procedural
let anim = null
let userYaw = 0
let drag = null
const mouse = { x: 0, y: 0 }
let blinkAt = 2
let blinkQueue = 0
let speaking = false
let speakTimer = null
let gradientMap
let lookTarget = null
let fallbackDone = false
let gesture = null
let gestureNext = 9
let cameraHome = null
let microExpr = null          // 待机微表情（偶尔浅笑/挑眉）
let microExprNext = 6
let breathPhase = 0           // 呼吸相位（受情绪唤醒度调制）
let arousal = 0               // 情绪唤醒度：剧烈动作后呼吸加快，随后回落
const gaze = { x: 0, y: 0, nextAt: 3 }   // 注意力扫视目标
const S = {}    // 关节平滑缓存（消除机械感的关键）
const EXP = {}  // 表情平滑缓存

/* 手指骨骼：VRM 人形可选骨骼，存在则驱动 */
const FINGER_SEGS = ["Proximal", "Intermediate", "Distal"]
const FINGER_CURL = {
  Thumb: [0.32, 0.46, 0.30],
  Index: [0.52, 0.68, 0.44],
  Middle: [0.58, 0.74, 0.48],
  Ring: [0.60, 0.76, 0.50],
  Little: [0.62, 0.78, 0.52],
}

/* ---------- 工具 ---------- */
const toon = (color) => new THREE.MeshToonMaterial({ color, gradientMap })
const mesh = (geo, mat, x = 0, y = 0, z = 0) => {
  const m = new THREE.Mesh(geo, mat)
  m.position.set(x, y, z)
  return m
}
const smooth = (p) => p * p * (3 - 2 * p)
const clamp01 = (v) => Math.max(0, Math.min(1, v))
// 缓入缓出（五次曲线）：起步加速柔和、收尾减速明显，比线性更接近真人发力
const easeInOutCubic = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2)
const env = (p, inR = 0.18, outR = 0.78) =>
  p < inR ? smooth(p / inR) : p > outR ? smooth((1 - p) / (1 - outR)) : 1

/* ---------- 程序化兜底建模 ---------- */
function buildGradient() {
  const data = new Uint8Array([70, 128, 190, 255])
  const tex = new THREE.DataTexture(data, 4, 1, THREE.RedFormat)
  tex.needsUpdate = true
  return tex
}

function buildGirl() {
  const g = new THREE.Group()
  const skinM = toon(COL.skin), hairM = toon(COL.hair), whiteM = toon(COL.white)
  const navyM = toon(COL.navy), redM = toon(COL.red), sockM = toon(COL.sock)
  const shoeM = toon(COL.shoe), eyeM = toon(COL.eye), packM = toon(COL.pack)

  for (const s of [-1, 1]) {
    const leg = new THREE.Group()
    leg.position.set(0.09 * s, 0.72, 0)
    leg.add(mesh(new THREE.CapsuleGeometry(0.056, 0.28, 4, 10), sockM, 0, -0.16, 0))
    leg.add(mesh(new THREE.CapsuleGeometry(0.05, 0.14, 4, 10), skinM, 0, 0.02, 0))
    const shoe = mesh(new THREE.BoxGeometry(0.11, 0.07, 0.17), shoeM, 0, -0.33, 0.025)
    shoe.rotation.x = 0.06
    leg.add(shoe)
    const toe = mesh(new THREE.SphereGeometry(0.055, 12, 8), shoeM, 0, -0.335, 0.09)
    toe.scale.set(1, 0.55, 0.9)
    leg.add(toe)
    g.add(leg)
    J[s < 0 ? 'legL' : 'legR'] = leg
  }

  const skirtGeo = new THREE.CylinderGeometry(0.155, 0.30, 0.30, 18, 1, true)
  const skirtM = new THREE.MeshToonMaterial({
    color: COL.skirt, gradientMap, flatShading: true, side: THREE.DoubleSide,
  })
  g.add(mesh(skirtGeo, skirtM, 0, 0.585, 0))

  const torso = new THREE.Group()
  torso.position.set(0, 0.72, 0)
  torso.add(mesh(new THREE.CylinderGeometry(0.155, 0.185, 0.34, 14), whiteM, 0, 0.17, 0))
  torso.add(mesh(new THREE.BoxGeometry(0.46, 0.02, 0.30), navyM, 0, 0.325, -0.01))
  for (const s of [-1, 1]) {
    const flap = mesh(new THREE.BoxGeometry(0.16, 0.20, 0.02), navyM, 0.105 * s, 0.235, 0.125)
    flap.rotation.z = -0.55 * s
    torso.add(flap)
    const stripe = mesh(new THREE.BoxGeometry(0.03, 0.19, 0.022), whiteM, 0.175 * s, 0.235, 0.126)
    stripe.rotation.z = -0.55 * s
    torso.add(stripe)
  }
  const backFlap = mesh(new THREE.BoxGeometry(0.34, 0.22, 0.02), navyM, 0, 0.23, -0.14)
  backFlap.rotation.x = 0.25
  torso.add(backFlap)
  const knot = mesh(new THREE.ConeGeometry(0.07, 0.13, 4), redM, 0, 0.28, 0.135)
  knot.rotation.x = Math.PI
  knot.rotation.y = Math.PI / 4
  torso.add(knot)
  torso.add(mesh(new THREE.SphereGeometry(0.028, 10, 8), redM, 0, 0.31, 0.14))
  for (const s of [-1, 1]) {
    const tail = mesh(new THREE.BoxGeometry(0.035, 0.13, 0.014), redM, 0.045 * s, 0.21, 0.15)
    tail.rotation.z = 0.3 * s
    torso.add(tail)
  }
  torso.add(mesh(new THREE.CylinderGeometry(0.05, 0.055, 0.09, 10), skinM, 0, 0.375, 0))
  torso.add(mesh(new THREE.BoxGeometry(0.27, 0.30, 0.10), packM, 0, 0.16, -0.20))
  for (const s of [-1, 1]) {
    const strap = mesh(new THREE.BoxGeometry(0.035, 0.20, 0.02), navyM, 0.115 * s, 0.27, 0.115)
    strap.rotation.z = 0.35 * s
    torso.add(strap)
  }
  g.add(torso)
  J.torso = torso

  for (const s of [-1, 1]) {
    const arm = new THREE.Group()
    arm.position.set(0.195 * s, 0.30, 0)
    arm.rotation.z = -0.14 * s
    arm.add(mesh(new THREE.CapsuleGeometry(0.048, 0.12, 4, 10), whiteM, 0, -0.075, 0))
    const fore = new THREE.Group()
    fore.position.set(0, -0.16, 0)
    fore.add(mesh(new THREE.CapsuleGeometry(0.038, 0.13, 4, 10), skinM, 0, -0.08, 0))
    fore.add(mesh(new THREE.SphereGeometry(0.05, 10, 8), skinM, 0, -0.175, 0.01))
    arm.add(fore)
    torso.add(arm)
    J[s < 0 ? 'armL' : 'armR'] = arm
    J[s < 0 ? 'foreL' : 'foreR'] = fore
  }

  const head = new THREE.Group()
  head.position.set(0, 0.40, 0)
  head.add(mesh(new THREE.SphereGeometry(0.30, 28, 22), skinM, 0, 0.26, 0))
  const hairTop = mesh(
    new THREE.SphereGeometry(0.315, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.56),
    hairM, 0, 0.27, -0.01)
  hairTop.scale.set(1.03, 1.1, 1.03)
  head.add(hairTop)
  const hairBack = mesh(new THREE.SphereGeometry(0.295, 20, 14), hairM, 0, 0.24, -0.07)
  hairBack.scale.set(1.02, 1.12, 0.92)
  head.add(hairBack)
  const bangLens = [0.1, 0.13, 0.11, 0.13, 0.1]
  bangLens.forEach((L, i) => {
    const a = (i - 2) * 0.42
    const bang = mesh(new THREE.CapsuleGeometry(0.034, L, 4, 8), hairM,
      Math.sin(a) * 0.26, 0.40 - L * 0.35, Math.cos(a) * 0.245 - 0.03)
    bang.rotation.z = -a * 0.55
    bang.rotation.x = 0.12
    head.add(bang)
  })
  for (const s of [-1, 1]) {
    const lock = mesh(new THREE.CapsuleGeometry(0.032, 0.17, 4, 8), hairM, 0.265 * s, 0.13, 0.06)
    lock.rotation.z = 0.12 * s
    head.add(lock)
  }
  const tails = {}
  for (const s of [-1, 1]) {
    const tw = new THREE.Group()
    tw.position.set(0.30 * s, 0.32, -0.09)
    const tie = mesh(new THREE.TorusGeometry(0.05, 0.016, 8, 14), redM, 0, 0, 0)
    tie.rotation.y = Math.PI / 2 * s
    tw.add(tie)
    const t1 = mesh(new THREE.CapsuleGeometry(0.055, 0.20, 4, 10), hairM, 0.02 * s, -0.16, -0.01)
    t1.rotation.z = 0.28 * s
    tw.add(t1)
    const t2 = mesh(new THREE.CapsuleGeometry(0.042, 0.16, 4, 10), hairM, 0.05 * s, -0.36, -0.03)
    t2.rotation.z = 0.45 * s
    tw.add(t2)
    tw.add(mesh(new THREE.SphereGeometry(0.045, 10, 8), hairM, 0.07 * s, -0.46, -0.05))
    head.add(tw)
    tails[s < 0 ? 'L' : 'R'] = tw
  }
  J.tailL = tails.L
  J.tailR = tails.R

  const eyes = {}
  for (const s of [-1, 1]) {
    const eye = new THREE.Group()
    eye.position.set(0.105 * s, 0.26, 0.235)
    const white = mesh(new THREE.SphereGeometry(0.058, 14, 10), toon(COL.white), 0, 0, 0.02)
    white.scale.set(1, 1.25, 0.45)
    eye.add(white)
    const iris = mesh(new THREE.SphereGeometry(0.037, 14, 10), eyeM, 0, -0.004, 0.045)
    iris.scale.set(1, 1.45, 0.4)
    eye.add(iris)
    eye.add(mesh(new THREE.SphereGeometry(0.013, 8, 6), toon(0xffffff), -0.012 * s, 0.02, 0.065))
    const brow = mesh(new THREE.BoxGeometry(0.075, 0.010, 0.012), hairM, 0, 0.085, 0.02)
    brow.rotation.z = 0.1 * s
    eye.add(brow)
    head.add(eye)
    eyes[s < 0 ? 'L' : 'R'] = eye
  }
  J.eyeL = eyes.L
  J.eyeR = eyes.R

  for (const s of [-1, 1]) {
    const blush = mesh(new THREE.CircleGeometry(0.034, 12),
      new THREE.MeshBasicMaterial({ color: COL.blush, transparent: true, opacity: 0.45 }),
      0.155 * s, 0.175, 0.245)
    blush.rotation.y = -0.35 * s
    head.add(blush)
  }

  const smile = mesh(new THREE.TorusGeometry(0.05, 0.011, 8, 14, Math.PI), toon(COL.mouthIn),
    0, 0.115, 0.25)
  smile.rotation.z = Math.PI
  head.add(smile)
  J.smile = smile
  const mouth = mesh(new THREE.SphereGeometry(0.045, 12, 8), toon(COL.mouthIn), 0, 0.105, 0.245)
  mouth.scale.set(1, 0.22, 0.5)
  mouth.visible = false
  head.add(mouth)
  J.mouth = mouth

  torso.add(head)
  J.head = head
  return g
}

/* ---------- 模型加载（支持自有模型插槽） ---------- */
/**
 * 模型优先级：
 *   1) /models/avatar.vrm —— 用户自备模型插槽（放进 public/models/ 即自动生效）
 *   2) /models/twist-sample.vrm —— 内置开源示例模型
 * 两个都不存在/损坏时，自动降级为程序化兜底建模。
 * 说明：角色模型请使用你自己合法获得的 VRM 文件（如 VRoid 自制、或已获授权的模型）。
 */
const MODEL_URLS = ['/models/avatar.vrm', '/models/twist-sample.vrm']

function tryLoadVRM() {
  const loader = new GLTFLoader()
  loader.register((parser) => new VRMLoaderPlugin(parser))
  const fallbackTimer = setTimeout(() => { if (mode === 'loading') enableProcedural() }, 15000)

  const attempt = (idx) => {
    if (mode !== 'loading') { clearTimeout(fallbackTimer); return }
    if (idx >= MODEL_URLS.length) { clearTimeout(fallbackTimer); enableProcedural(); return }
    const url = MODEL_URLS[idx]
    loader.load(url, (gltf) => {
      clearTimeout(fallbackTimer)
      if (mode !== 'loading') return // 兜底已启用
      const vrm = gltf.userData.vrm
      if (!vrm) {
        // 不是有效 VRM → 尝试下一个
        attempt(idx + 1)
        return
      }
      try {
        // VRM0 模型朝向修正
        if (vrm.meta?.metaVersion === '0') VRMUtils.rotateVRM0(vrm)
        VRMUtils.removeUnnecessaryVertices(gltf.scene)
        VRMUtils.combineSkeletons?.(gltf.scene)
        vrm.scene.traverse((o) => { o.frustumCulled = false })
        mode = 'vrm'
        model = vrm.scene
        J = {
          vrm,
          humanoid: vrm.humanoid,
          em: vrm.expressionManager,
        }
        // 手部骨骼（腕 + 手指）：有则驱动，没有则自然跳过
        J.hands = {}
        J.fingers = { left: [], right: [] }
        for (const side of ['left', 'right']) {
          J.hands[side] = vrm.humanoid.getNormalizedBoneNode(`${side}Hand`)
          for (const finger of ['Thumb', 'Index', 'Middle', 'Ring', 'Little']) {
            FINGER_SEGS.forEach((seg, i) => {
              const node = vrm.humanoid.getNormalizedBoneNode(`${side}${finger}${seg}`)
              if (node) J.fingers[side].push({ node, finger, seg: i })
            })
          }
        }
        // 模型实际拥有的表情集合（不同模型命名略有差异）
        try {
          J.exprNames = new Set(Object.keys(vrm.expressionManager?.expressionMap || {}))
        } catch (e) {
          J.exprNames = new Set()
        }
        console.info('[VrmGirl] 手指骨骼:', J.fingers.left.length + J.fingers.right.length,
          '表情数:', J.exprNames.size)
        // 自动取景：全身入镜
        vrm.scene.updateMatrixWorld(true)
        const box = new THREE.Box3().setFromObject(vrm.scene)
        const h = Math.max(0.5, box.max.y)
        camera.position.set(0.12, h * 0.78, h * 2.15)
        camera.lookAt(0, h * 0.52, 0)
        cameraHome = { x: 0.12, y: h * 0.78, look: new THREE.Vector3(0, h * 0.52, 0) }
        scene.add(vrm.scene)
        // 眼睛注视目标
        lookTarget = new THREE.Object3D()
        lookTarget.position.set(0, h * 0.55, 1.2)
        scene.add(lookTarget)
        if (vrm.lookAt) vrm.lookAt.target = lookTarget
        // 头发/裙摆等弹簧骨骼调参：降低刚度与阻尼，让动作带动更自然的次级物理
        try {
          const joints = vrm.springBoneManager?.joints
          if (joints) {
            let n = 0
            for (const j of joints) {
              if (j?.settings) {
                j.settings.stiffness *= 0.82
                j.settings.dragForce *= 0.92
                n++
              }
            }
            console.info('[VrmGirl] spring joints tuned:', n)
          }
        } catch (e) { /* 模型无弹簧骨骼时忽略 */ }
        const shadow = scene.getObjectByName('__shadow')
        if (shadow) shadow.scale.setScalar(h * 0.42)
        console.info('[VrmGirl] VRM 模型加载成功：', url)
      } catch (e) {
        console.warn('[VrmGirl] VRM 初始化失败，尝试兜底', e)
        enableProcedural()
      }
    }, undefined, () => {
      // 该路径不存在或损坏 → 尝试下一个模型
      attempt(idx + 1)
    })
  }
  attempt(0)
}

function enableProcedural() {
  if (fallbackDone) return
  fallbackDone = true
  mode = 'procedural'
  gradientMap = gradientMap || buildGradient()
  model = buildGirl()
  model.position.y = 0.02
  scene.add(model)
  camera.position.set(0.1, 1.15, 2.9)
  camera.lookAt(0, 1.02, 0)
  cameraHome = { x: 0.1, y: 1.15, look: new THREE.Vector3(0, 1.02, 0) }
  console.info('[VrmGirl] 使用程序化兜底建模')
}

/* ---------- 场景 ---------- */
function buildShadow() {
  const cv = document.createElement('canvas')
  cv.width = cv.height = 128
  const ctx = cv.getContext('2d')
  const grad = ctx.createRadialGradient(64, 64, 4, 64, 64, 62)
  grad.addColorStop(0, 'rgba(40,30,60,0.42)')
  grad.addColorStop(1, 'rgba(40,30,60,0)')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 128, 128)
  const tex = new THREE.CanvasTexture(cv)
  const m = new THREE.Mesh(
    new THREE.CircleGeometry(0.62, 24),
    new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }),
  )
  m.rotation.x = -Math.PI / 2
  m.position.y = 0.01
  m.name = '__shadow'
  return m
}

function init() {
  wrap = wrapEl.value
  renderer = new THREE.WebGLRenderer({ canvas: cnvEl.value, antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(32, 1, 0.1, 60)
  camera.position.set(0.1, 1.15, 2.9)
  camera.lookAt(0, 1.02, 0)
  scene.add(buildShadow())
  scene.add(new THREE.HemisphereLight(0xffffff, 0xcdd6ff, 1.05))
  const key = new THREE.DirectionalLight(0xffffff, 1.15)
  key.position.set(1.6, 2.4, 2.2)
  scene.add(key)
  const rim = new THREE.DirectionalLight(0xffe6f0, 0.5)
  rim.position.set(-1.8, 1.6, -2.0)
  scene.add(rim)
  clock = new THREE.Clock()
  resize()
  const ro = new ResizeObserver(resize)
  ro.observe(wrap)
  disposeFns.push(() => ro.disconnect())
  rafId = requestAnimationFrame(tick)
  gradientMap = buildGradient() // 兜底建模提前准备好渐变贴图
  tryLoadVRM()
}

/* ---------- 姿态与动作（两种模式共用） ---------- */

/**
 * 待机姿态：不再是「只有呼吸的立正」。
 * 参考游戏角色的 idle 动画结构（UmaViewer / 原神、鸣潮模型提取工具里的动作组织方式）：
 *   - 缓慢重心转移（0.55rad/s 的极低频摆动）
 *   - 胸腔呼吸 + 肩部联动
 *   - 视线缓慢漂移（叠加鼠标注视）
 *   - 手臂/前臂微摆，形成「有重量感」的静态
 */
function idlePose(t) {
  // 呼吸用相位累加：唤醒度高时呼吸更快更深（动作之后的「余韵」）
  const breathe = Math.sin(breathPhase)
  const shift = Math.sin(t * 0.55)      // 重心左右转移
  const drift = Math.sin(t * 0.37)      // 视线漂移
  return {
    torso: {
      x: 0.02 + breathe * (0.012 + arousal * 0.01),
      sy: 1 + breathe * (0.010 + arousal * 0.008),
      z: shift * 0.022,
    },
    head: {
      x: Math.sin(t * 1.3) * 0.02 + mouse.y * -0.22 + drift * 0.012,
      y: mouse.x * 0.5 + drift * 0.06,
      z: Math.sin(t * 0.9) * 0.03 - shift * 0.016,
    },
    armL: { x: Math.sin(t * 1.6) * 0.05, z: 0.14 + Math.sin(t * 1.6) * 0.03 + shift * 0.02 },
    armR: { x: -Math.sin(t * 1.6) * 0.05, z: -0.14 - Math.sin(t * 1.6) * 0.03 + shift * 0.02 },
    shoulderL: { z: 0.015 + breathe * 0.008, x: 0 },
    shoulderR: { z: -0.015 - breathe * 0.008, x: 0 },
    foreL: { x: 0.16 + Math.sin(t * 1.1) * 0.03 },
    foreR: { x: 0.16 + Math.sin(t * 1.1 + 0.6) * 0.03 },
    legL: { x: 0 }, legR: { x: 0 },
    tailL: { x: Math.sin(t * 1.8) * 0.10, z: 0.10 + Math.sin(t * 1.5 + 1) * 0.08 },
    tailR: { x: Math.sin(t * 1.8 + 0.6) * 0.10, z: -0.10 - Math.sin(t * 1.5) * 0.08 },
    rootY: 0, rootX: shift * 0.007, rootZ: 0, mouth: 0,
  }
}

/* 空闲小动作：像真人一样偶尔换重心、转头、伸懒腰，而不是一直定格 */
const GESTURES = {
  headTurn: (p) => ({
    head: { y: 0.28 * env(p, 0.2, 0.8) },
    torso: { z: 0.012 * env(p) },
  }),
  stretch: (p) => ({
    armL: { z: 0.55 * env(p) }, armR: { z: -0.55 * env(p) },
    torso: { x: -0.03 * env(p) }, head: { x: -0.06 * env(p) },
  }),
  shoulderRoll: (p) => ({
    head: { z: 0.12 * env(p), y: -0.1 * env(p) },
    torso: { z: -0.015 * env(p) },
  }),
  lookAround: (p) => ({
    head: { y: Math.sin(p * Math.PI * 2) * 0.22 * env(p), x: -0.03 * env(p) },
  }),
  hairTouch: (p) => ({
    armR: { z: -1.35 * env(p, 0.22, 0.8), x: -0.18 * env(p) },
    foreR: { x: -1.1 * env(p, 0.22, 0.8) },
    head: { z: 0.16 * env(p), x: 0.04 * env(p) },
    tailR: { z: -0.35 * env(p) },
  }),
  sway: (p) => ({
    torso: { z: 0.055 * Math.sin(p * Math.PI * 2) * env(p) },
    armL: { z: 0.2 * Math.sin(p * Math.PI * 2) * env(p) },
    armR: { z: -0.2 * Math.sin(p * Math.PI * 2) * env(p) },
    head: { z: -0.035 * Math.sin(p * Math.PI * 2) * env(p) },
    rootX: 0.01 * Math.sin(p * Math.PI * 2),
  }),
  shimmy: (p) => ({
    armL: { z: 0.16 * Math.sin(p * Math.PI * 12) * env(p, 0.15, 0.85) },
    armR: { z: -0.16 * Math.sin(p * Math.PI * 12) * env(p, 0.15, 0.85) },
    head: { z: 0.05 * Math.sin(p * Math.PI * 6) * env(p) },
    torso: { x: 0.01 * Math.sin(p * Math.PI * 12) },
  }),
}

function addGesture(base, t) {
  if (anim) return base
  if (gesture) {
    const p = (t - gesture.t0) / gesture.dur
    if (p >= 1) { gesture = null; return base }
    return addPose(base, GESTURES[gesture.name](p))
  }
  if (t > gestureNext) {
    const names = Object.keys(GESTURES)
    gesture = {
      name: names[Math.floor(Math.random() * names.length)],
      t0: t, dur: 2.4 + Math.random() * 1.2,
    }
    gestureNext = t + 6 + Math.random() * 7
  }
  return base
}

/**
 * 说话节拍手势：参考实时语音驱动动画（audio-driven gesture）的思路，
 * 用手部/头部的小幅「打拍子」跟随说话节奏，让讲话不是「动嘴不动身」。
 */
function speechBeats(pose, t) {
  if (!speaking || anim) return pose
  const beat = Math.pow(Math.max(0, Math.sin(t * 6.1 + 0.6)), 3)  // 约每 1 秒一次重音
  return addPose(pose, {
    armR: { x: -0.08 * beat, z: -0.14 * beat },
    foreR: { x: 0.22 * beat },
    head: { x: 0.022 * beat },
    torso: { z: 0.006 * beat },
  })
}

/* 指数阻尼：让每个关节朝目标平滑收敛，动作不再「瞬间到位」 */
function damp(key, target, rate, dt) {
  const cur = S[key] === undefined ? target : S[key]
  S[key] = cur + (target - cur) * (1 - Math.exp(-rate * dt))
  return S[key]
}

function smoothPose(p, dt) {
  return {
    torso: {
      x: damp('torso.x', p.torso.x, 6, dt),
      sy: damp('torso.sy', p.torso.sy, 6, dt),
      z: damp('torso.z', p.torso.z, 6, dt),
    },
    head: {
      x: damp('head.x', p.head.x, 9, dt),
      y: damp('head.y', p.head.y, 9, dt),
      z: damp('head.z', p.head.z, 9, dt),
    },
    armL: { x: damp('armL.x', p.armL.x, 10, dt), z: damp('armL.z', p.armL.z, 10, dt) },
    armR: { x: damp('armR.x', p.armR.x, 10, dt), z: damp('armR.z', p.armR.z, 10, dt) },
    shoulderL: {
      x: damp('shoulderL.x', p.shoulderL?.x || 0, 9, dt),
      z: damp('shoulderL.z', p.shoulderL?.z || 0, 9, dt),
    },
    shoulderR: {
      x: damp('shoulderR.x', p.shoulderR?.x || 0, 9, dt),
      z: damp('shoulderR.z', p.shoulderR?.z || 0, 9, dt),
    },
    foreL: { x: damp('foreL.x', p.foreL.x, 8, dt) },
    foreR: { x: damp('foreR.x', p.foreR.x, 8, dt) },
    legL: { x: damp('legL.x', p.legL.x, 10, dt) },
    legR: { x: damp('legR.x', p.legR.x, 10, dt) },
    tailL: { x: damp('tailL.x', p.tailL.x, 7, dt), z: damp('tailL.z', p.tailL.z, 7, dt) },
    tailR: { x: damp('tailR.x', p.tailR.x, 7, dt), z: damp('tailR.z', p.tailR.z, 7, dt) },
    rootX: damp('rootX', p.rootX, 10, dt),
    rootY: damp('rootY', p.rootY, 16, dt),
    rootZ: damp('rootZ', p.rootZ || 0, 10, dt),
    mouth: p.mouth,
  }
}

/* ---------- 手部姿态（腕 + 五指） ---------- */
/**
 * 手部不再固定成默认手型：
 *   待机 → 轻微自然蜷曲（并带极缓慢的呼吸式起伏）
 *   挥手 → 张开手掌、手腕随节奏摆动
 *   鼓掌 → 双掌相对、手腕内扣
 *   摸头 → 手掌盖向头顶、手腕下压
 *   跺脚 → 握拳
 *   指向 → 食指伸出、其余手指收拢
 */
function handTarget(name, p, t) {
  const idleCurl = 0.26 + Math.sin(t * 2.3) * 0.02
  // 待机不强行加手腕角度：尊重模型自身 rest pose，避免出现不自然折角
  const idle = () => ({ curl: idleCurl, thumb: 0.28, indexOnly: false,
    wx: 0, wy: 0, wz: 0 })
  const out = { left: idle(), right: idle() }
  if (!anim) return out

  switch (name) {
    case 'wave':
      out.right = { curl: 0.03, thumb: 0.12, indexOnly: false,
        wx: 0.05, wy: Math.sin(p * 14) * 0.18, wz: Math.sin(p * 14) * 0.34 }
      break
    case 'clap':
      out.left.curl = out.right.curl = 0.10
      out.left.wx = out.right.wx = -0.32
      out.left.wz = 0.12; out.right.wz = -0.12
      break
    case 'pat':
      out.right = { curl: 0.30, thumb: 0.28, indexOnly: false, wx: 0.62, wy: 0.15, wz: -0.06 }
      break
    case 'stomp':
      out.left.curl = out.right.curl = 0.98
      out.left.thumb = out.right.thumb = 0.85
      out.left.wx = out.right.wx = 0.12
      break
    case 'jump':
      out.left.curl = out.right.curl = 0.10
      out.left.wx = 0.02; out.right.wx = 0.02
      break
    case 'surprise':
      out.left.curl = out.right.curl = 0.02
      out.left.thumb = out.right.thumb = 0.1
      break
    case 'curious':
      out.right.indexOnly = true
      out.right.curl = 1.0
      out.right.thumb = 0.45
      out.right.wx = 0.3
      break
    case 'sad':
    case 'anxious':
      out.left.curl = out.right.curl = 0.36
      out.left.wx = out.right.wx = -0.12
      break
    case 'protect':
      out.left.curl = out.right.curl = 0.03
      out.left.wx = out.right.wx = -0.5
      break
    case 'scared':
      out.left.curl = out.right.curl = 0.45
      out.left.wx = out.right.wx = -0.22
      break
    case 'spin':
      out.left.curl = out.right.curl = 0.12
      break
    default:
      break
  }
  return out
}

function applyHands(name, p, t, dt) {
  if (!J.fingers) return
  if (!J.fingers.left.length && !J.fingers.right.length && !J.hands?.left) return
  const target = handTarget(name, p, t)
  for (const side of ['left', 'right']) {
    const cfg = target[side]
    const curl = damp(`hand.${side}.curl`, cfg.curl, 14, dt)
    const thumb = damp(`hand.${side}.thumb`, cfg.thumb, 14, dt)
    const wx = damp(`hand.${side}.wx`, cfg.wx, 10, dt)
    const wy = damp(`hand.${side}.wy`, cfg.wy, 10, dt)
    const wz = damp(`hand.${side}.wz`, cfg.wz, 10, dt)
    // 握拳/伸展方向：左右手镜像，符号相反
    const sign = side === 'right' ? -1 : 1
    for (const f of J.fingers[side]) {
      let c
      if (cfg.indexOnly && f.finger === 'Index') c = 0
      else if (cfg.indexOnly && f.finger !== 'Thumb') c = 1.0
      else if (f.finger === 'Thumb') c = thumb * (f.seg === 0 ? 1 : 0.8)
      else c = curl * FINGER_CURL[f.finger][f.seg]
      f.node.rotation.z = c * sign
    }
    const hand = J.hands[side]
    if (hand) hand.rotation.set(wx, wy, wz)
  }
}

/* ---------- 微表情调度：待机时偶尔浅笑/挑眉，避免「面瘫」 ---------- */
function microExpression(t) {
  if (microExpr) {
    const p = (t - microExpr.t0) / microExpr.dur
    if (p >= 1) {
      microExpr = null
      microExprNext = t + 5 + Math.random() * 6
    } else {
      return { name: microExpr.name, value: Math.sin(Math.min(p, 1) * Math.PI) * microExpr.amp }
    }
  } else if (t > microExprNext && !anim) {
    const pick = Math.random()
    microExpr = pick < 0.6
      ? { name: 'happy', amp: 0.22, t0: t, dur: 1.6 }
      : pick < 0.85
        ? { name: 'surprised', amp: 0.10, t0: t, dur: 1.0 }
        : { name: 'relaxed', amp: 0.25, t0: t, dur: 2.0 }
    microExprNext = t + 5 + Math.random() * 6
  }
  return null
}

/* 眨眼包络：phase 从 0 开始，0.14s 闭眼一次 */
function blinkClosed(ph) {
  return ph >= 0 && ph <= 0.14 ? 1 - Math.sin((ph / 0.14) * Math.PI) : 0
}

const ANIMS = {
  wave: (p) => {
    // 预备：手臂先向身体内侧收一下再抬起（真人挥手不会直接弹起）
    const wind = 0.10 * Math.sin(Math.PI * Math.min(1, p / 0.24))
    const e = env(clamp01((p - 0.12) / 0.88))
    return {
      armR: { z: wind - 1.32 * e, x: -0.1 * e },
      shoulderR: { z: -0.16 * e, x: 0.04 * e },
      // 上举时肘部向头部方向弯（Z 轴负向），手落在脸侧挥动
      foreR: { z: Math.sin(p * 14) * 0.3 * e, x: 1.05 * e },
      head: { z: 0.16 * e },
      tailR: { z: -0.55 * e },
    }
  },
  nod: (p) => ({ head: { x: Math.sin(p * Math.PI * 4) * 0.28 * env(p) } }),
  jump: (p) => {
    const hop = Math.abs(Math.sin(p * Math.PI * 2)) * 0.16 * env(p, 0.1, 0.9)
    return {
      rootY: hop,
      torso: { sy: 1 - Math.sin(p * Math.PI * 4) * 0.05 * env(p) },
      armL: { z: 1.85 * env(p) }, armR: { z: -1.85 * env(p) },
      shoulderL: { z: 0.12 * env(p) }, shoulderR: { z: -0.12 * env(p) },
      foreL: { x: 0.4 * env(p) }, foreR: { x: 0.4 * env(p) },
      tailL: { x: -0.35 * env(p) }, tailR: { x: -0.35 * env(p) },
      mouth: 0.5 * env(p),
    }
  },
  clap: (p) => ({
    armL: { x: -1.15 * env(p), z: 0.55 + Math.sin(p * Math.PI * 8) * 0.18 },
    armR: { x: -1.15 * env(p), z: -0.55 - Math.sin(p * Math.PI * 8) * 0.18 },
    shoulderL: { z: 0.1 * env(p) }, shoulderR: { z: -0.1 * env(p) },
    foreL: { x: 0.65 * env(p) }, foreR: { x: 0.65 * env(p) },
    head: { x: -0.08 * env(p) },
    mouth: 0.4 * env(p),
  }),
  curious: (p) => ({
    head: { z: 0.32 * env(p), x: -0.05 * env(p) },
    armR: { x: -1.35 * env(p), z: -0.45 * env(p) },
    shoulderR: { z: -0.12 * env(p) },
    foreR: { x: 1.45 * env(p) },
    tailL: { z: 0.2 * env(p) },
  }),
  sad: (p) => ({
    head: { x: 0.38 * env(p), z: 0.06 * env(p) },
    torso: { x: 0.16 * env(p), sy: 0.97 },
    shoulderL: { x: 0.06 * env(p), z: 0.02 * env(p) },
    shoulderR: { x: 0.06 * env(p), z: -0.02 * env(p) },
    armL: { x: -0.55 * env(p), z: 0.35 * env(p) },
    armR: { x: -0.55 * env(p), z: -0.35 * env(p) },
    foreL: { x: 0.9 * env(p) }, foreR: { x: 0.9 * env(p) },
    tailL: { z: 0.42 * env(p), x: 0.15 * env(p) },
    tailR: { z: -0.42 * env(p), x: 0.15 * env(p) },
  }),
  anxious: (p) => ({
    rootX: Math.sin(p * 34) * 0.008 * env(p),
    head: { x: 0.12 * env(p), z: Math.sin(p * 20) * 0.02 * env(p) },
    armL: { x: -0.9 * env(p), z: 0.55 * env(p) },
    armR: { x: -0.9 * env(p), z: -0.55 * env(p) },
    shoulderL: { z: 0.08 * env(p) }, shoulderR: { z: -0.08 * env(p) },
    foreL: { x: 1.3 * env(p) }, foreR: { x: 1.3 * env(p) },
    tailL: { z: 0.2 * env(p) }, tailR: { z: -0.2 * env(p) },
  }),
  scared: (p) => ({
    head: { x: 0.22 * env(p), z: Math.sin(p * 26) * 0.03 * env(p) },
    torso: { x: 0.18 * env(p) },
    armL: { x: -1.9 * env(p), z: 0.75 * env(p) },
    armR: { x: -1.9 * env(p), z: -0.75 * env(p) },
    shoulderL: { z: 0.15 * env(p) }, shoulderR: { z: -0.15 * env(p) },
    foreL: { x: 0.85 * env(p) }, foreR: { x: 0.85 * env(p) },
    rootY: -0.045 * env(p),
    mouth: 0.6 * env(p),
  }),
  protect: (p) => ({
    head: { x: 0.02 * env(p) },
    torso: { x: 0.12 * env(p) },
    armL: { x: -1.5 * env(p), z: 0.22 * env(p) },
    armR: { x: -1.5 * env(p), z: -0.22 * env(p) },
    shoulderL: { z: 0.1 * env(p) }, shoulderR: { z: -0.1 * env(p) },
    foreL: { x: 0.35 * env(p) }, foreR: { x: 0.35 * env(p) },
    tailL: { x: 0.1 }, tailR: { x: 0.1 },
  }),
  pat: (p) => ({
    head: { x: -0.12 * env(p), z: Math.sin(p * Math.PI * 6) * 0.05 * env(p) },
    torso: { sy: 1 - 0.04 * env(p) },
    tailL: { z: 0.3 * env(p), x: Math.sin(p * 22) * 0.2 * env(p) },
    tailR: { z: -0.3 * env(p), x: Math.sin(p * 22 + 1) * 0.2 * env(p) },
    // 只有右手抬到头顶（左手保持自然下垂），肘部弯折把手带到头上
    armR: { z: -1.45 * env(p), x: -0.15 * env(p) },
    shoulderR: { z: -0.18 * env(p) },
    foreR: { x: 1.8 * env(p) },
    mouth: 0.45 * env(p),
  }),
  spin: (p) => {
    // 转身三阶段：预备（反向蓄力）→ 主转（加速-减速+过冲）→ 回正（落脚稳定）
    const antic = 0.12
    let yaw
    if (p < 0.14) {
      yaw = -antic * smooth(p / 0.14)
    } else if (p < 0.84) {
      const q = (p - 0.14) / 0.70
      yaw = -antic + (Math.PI * 2 + antic + 0.12) * easeInOutCubic(q)
    } else {
      const q = (p - 0.84) / 0.16
      yaw = Math.PI * 2 + 0.12 * (1 - smooth(q))
    }
    const turning = clamp01((p - 0.14) / 0.70)
    const lift = Math.sin(Math.PI * turning)          // 支撑脚重心起伏
    const swing = Math.sin(Math.PI * clamp01((p - 0.18) / 0.72))  // 手臂延迟摆动
    return {
      __yaw: yaw,
      rootX: 0.02 * Math.sin(Math.PI * p),             // 重心侧移
      rootZ: 0.035 * Math.sin(Math.PI * p),            // 绕支撑脚划弧（不是原地刚体旋转）
      rootY: 0.015 * Math.sin(Math.PI * p) - 0.02 * lift,
      torso: { x: 0.01, z: 0.045 * Math.sin(Math.PI * p) },
      // 头先转、身体后到，收尾时头先回正 —— 典型的「头领身随」
      head: { y: 0.22 * Math.sin(Math.PI * clamp01(p / 0.5)) * (1 - smooth(clamp01((p - 0.55) / 0.45))) },
      armL: { z: 0.85 * swing, x: -0.12 * swing },
      armR: { z: -0.85 * swing, x: -0.12 * swing },
      shoulderL: { z: 0.1 * swing }, shoulderR: { z: -0.1 * swing },
      foreL: { x: 0.35 * swing }, foreR: { x: 0.35 * swing },
      legR: { x: -0.18 * lift },                        // 自由脚轻微抬离地面
      legL: { x: 0.05 * lift },
      tailL: { z: 0.25 * lift }, tailR: { z: -0.25 * lift },
    }
  },
  surprise: (p) => ({
    rootY: Math.abs(Math.sin(p * Math.PI * 2)) * 0.05 * env(p),
    armL: { z: 1.6 * env(p), x: -0.3 * env(p) },
    armR: { z: -1.6 * env(p), x: -0.3 * env(p) },
    shoulderL: { z: 0.14 * env(p) }, shoulderR: { z: -0.14 * env(p) },
    foreL: { x: 0.5 * env(p) }, foreR: { x: 0.5 * env(p) },
    head: { x: -0.1 * env(p) },
    mouth: 0.7 * env(p),
    tailL: { x: -0.4 * env(p) }, tailR: { x: -0.4 * env(p) },
  }),
  stomp: (p) => ({
    head: { x: -0.08 * env(p), z: Math.sin(p * 18) * 0.03 * env(p) },
    armL: { x: 0.35 * env(p), z: 0.95 * env(p) },
    armR: { x: 0.35 * env(p), z: -0.95 * env(p) },
    shoulderL: { z: 0.08 * env(p) }, shoulderR: { z: -0.08 * env(p) },
    foreL: { x: 0.75 * env(p) }, foreR: { x: 0.75 * env(p) },
    legR: { x: -Math.max(0, Math.sin(p * Math.PI * 3)) * 0.7 * env(p) },
    torso: { x: -0.06 * env(p) },
  }),
}

function addPose(base, delta) {
  const out = { ...base }
  for (const k of Object.keys(delta)) {
    out[k] = { ...(base[k] || {}), ...delta[k] }
  }
  out.rootY = (base.rootY || 0) + (delta.rootY || 0)
  out.rootX = (base.rootX || 0) + (delta.rootX || 0)
  out.mouth = (base.mouth || 0) + (delta.mouth || 0)
  return out
}

/* 程序化模式：应用姿态 */
function applyPoseProcedural(p) {
  J.torso.rotation.set(p.torso.x, 0, p.torso.z)
  J.torso.scale.y = p.torso.sy
  J.head.rotation.set(p.head.x, p.head.y, p.head.z)
  J.armL.rotation.set(p.armL.x, 0, p.armL.z)
  J.armR.rotation.set(p.armR.x, 0, p.armR.z)
  J.foreL.rotation.set(p.foreL.x, 0, 0)
  J.foreR.rotation.set(p.foreR.x, 0, 0)
  J.legL.rotation.x = p.legL.x
  J.legR.rotation.x = p.legR.x
  J.tailL.rotation.set(p.tailL.x, 0, p.tailL.z)
  J.tailR.rotation.set(p.tailR.x, 0, p.tailR.z)
  model.position.y = 0.02 + p.rootY
  model.position.x = p.rootX
  model.position.z = p.rootZ || 0
}

/* VRM 模式：写入 normalized 骨骼 */
function applyPoseVRM(p) {
  const hb = (n) => J.humanoid?.getNormalizedBoneNode(n)
  const set = (node, x, y, z) => { if (node) node.rotation.set(x, y, z) }
  set(hb('spine'), p.torso.x * 0.6, 0, p.torso.z)
  set(hb('chest'), p.torso.x * 0.6, 0, 0)
  set(hb('neck'), p.head.x * 0.25, p.head.y * 0.3, p.head.z * 0.3)
  set(hb('head'), p.head.x, p.head.y, p.head.z)
  // 手臂：肩（锁骨）抬起 → 大臂 → 小臂 → 手腕四段联动
  set(hb('leftShoulder'), p.shoulderL?.x || 0, 0, p.shoulderL?.z || 0)
  set(hb('rightShoulder'), p.shoulderR?.x || 0, 0, p.shoulderR?.z || 0)
  set(hb('leftUpperArm'), p.armL.x, 0, -1.25 + p.armL.z)
  set(hb('rightUpperArm'), p.armR.x, 0, 1.25 + p.armR.z)
  // 肘关节：实测本模型的屈伸轴是 Z，且左右镜像（同值反向）才是对称弯曲
  set(hb('leftLowerArm'), 0, 0, p.foreL.x)
  set(hb('rightLowerArm'), 0, 0, -p.foreR.x)
  set(hb('leftUpperLeg'), p.legL.x, 0, 0)
  set(hb('rightUpperLeg'), p.legR.x, 0, 0)
  model.position.y = p.rootY
  model.position.x = p.rootX
  model.position.z = p.rootZ || 0
}

function setExpr(name, v) {
  // 模型没有该表情时直接跳过（避免无效调用与控制台噪音）
  if (J.exprNames && J.exprNames.size && !J.exprNames.has(name)) return
  try { J.em?.setValue?.(name, v) } catch (e) { /* 模型无该表情时忽略 */ }
}

/* 表情平滑：让表情有淡入淡出的过渡，而不是硬切 */
function smoothExpr(name, target, dt, rate = 7) {
  const cur = EXP[name] === undefined ? target : EXP[name]
  EXP[name] = cur + (target - cur) * (1 - Math.exp(-rate * dt))
  setExpr(name, EXP[name])
}

function tick() {
  rafId = requestAnimationFrame(tick)
  if (!model) { renderer.render(scene, camera); return }
  const dt = Math.min(0.05, clock.getDelta())
  const t = clock.getElapsedTime()

  // 呼吸：唤醒度高时加快加深，随后缓慢回落
  breathPhase += dt * (2.05 + arousal * 1.5)
  arousal *= Math.exp(-dt / 4.5)

  let base = idlePose(t)
  base = addGesture(base, t)
  let pose = base
  let yaw = 0
  let animName = ''
  let animP = 0

  if (anim) {
    const p = Math.min(1, (t - anim.t0) / anim.dur)
    animName = anim.name
    animP = p
    const fn = ANIMS[anim.name]
    if (fn) {
      const d = fn(p, t)
      yaw = d.__yaw || 0
      delete d.__yaw
      pose = addPose(base, d)
    }
    if (p >= 1) anim = null
  }

  pose = smoothPose(pose, dt)
  pose = speechBeats(pose, t)

  if (mode === 'vrm') {
    applyPoseVRM(pose)
    applyHands(animName, animP, t, dt)
    model.rotation.y = userYaw + yaw
    // 表情：根据动作与说话状态（带平滑过渡）
    const ex = { happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0 }
    if (anim) {
      if (['jump', 'clap', 'wave', 'pat'].includes(anim.name)) ex.happy = 0.85
      if (anim.name === 'sad') ex.sad = 0.85
      if (anim.name === 'anxious') ex.angry = 0.35
      if (anim.name === 'stomp') ex.angry = 0.55
      if (['scared', 'surprise'].includes(anim.name)) ex.surprised = 0.9
      if (anim.name === 'curious') ex.relaxed = 0.5
    }
    if (speaking) ex.happy = Math.max(ex.happy, 0.25)
    // 待机微表情：偶尔浅笑 / 挑眉，避免面瘫
    const micro = microExpression(t)
    if (micro) ex[micro.name] = Math.max(ex[micro.name] || 0, micro.value)
    // 微笑时眼周更柔和（relaxed 叠加）
    if (ex.happy > 0.4) ex.relaxed = Math.max(ex.relaxed, 0.22)
    smoothExpr('happy', ex.happy, dt, 8)
    smoothExpr('sad', ex.sad, dt, 7)
    smoothExpr('angry', ex.angry, dt, 9)
    smoothExpr('surprised', ex.surprised, dt, 16)   // 惊讶要快起快落
    smoothExpr('relaxed', ex.relaxed, dt, 6)
    // 说话口型：aa / oh / ee 三层混合，比单一开合更接近真实发音
    if (speaking) {
      const amp = Math.max(0.12, Math.min(0.8,
        0.22 + 0.42 * (0.55 + 0.45 * Math.sin(t * 9.3)) *
        Math.abs(Math.sin(t * 13.7 + 0.6))))
      smoothExpr('aa', amp, dt, 26)
      smoothExpr('oh', amp * 0.32 * Math.abs(Math.sin(t * 6.7)), dt, 24)
      smoothExpr('ee', amp * 0.18 * Math.abs(Math.sin(t * 8.9 + 1)), dt, 24)
    } else {
      smoothExpr('aa', Math.min(0.35, pose.mouth), dt, 14)
      smoothExpr('oh', 0, dt, 12)
      smoothExpr('ee', 0, dt, 12)
    }
    // 眨眼：随机间隔 + 偶尔连眨两下 + 左右眼 22ms 相位差
    if (t > blinkAt) {
      const bp = (t - blinkAt) / 0.14
      if (bp >= 1) {
        if (blinkQueue > 0) { blinkQueue -= 1; blinkAt = t + 0.22 }
        else {
          blinkAt = t + 2.2 + Math.random() * 3.6
          if (Math.random() < 0.28) blinkQueue = 1
        }
      }
    }
    const blinkPh = t - blinkAt
    if (J.exprNames?.has('blinkLeft') || J.exprNames?.has('blinkRight')) {
      setExpr('blink', 0)
      setExpr('blinkLeft', blinkClosed(blinkPh))
      setExpr('blinkRight', blinkClosed(blinkPh - 0.022))
    } else {
      setExpr('blink', blinkClosed(blinkPh))
    }
    // 眼睛注视 + 注意力扫视：真人不会一直死盯着一个点，
    // 每隔 2~4.5 秒会快速瞟向附近某个点，且约一半概率伴随眨眼
    if (t > gaze.nextAt) {
      gaze.x = (Math.random() * 2 - 1) * 0.42
      gaze.y = (Math.random() * 2 - 1) * 0.22
      gaze.nextAt = t + 2 + Math.random() * 2.5
      if (Math.random() < 0.5) blinkAt = t + 0.05 + Math.random() * 0.12
    }
    if (lookTarget && model) {
      const h = camera.position.y / 0.78 || 1.4
      lookTarget.position.set(mouse.x * 0.9 + gaze.x,
        h * 0.55 - mouse.y * 0.35 + gaze.y, 1.3)
    }
    J.vrm.update(dt)
  } else {
    applyPoseProcedural(pose)
    model.rotation.y += (userYaw + yaw - model.rotation.y) * (1 - Math.exp(-10 * dt))
    if (speaking) {
      J.mouth.visible = true
      J.smile.visible = false
      const amp = 0.22 + 0.38 * Math.abs(Math.sin(t * 13.7 + 0.6)) *
        (0.6 + 0.4 * Math.sin(t * 9.3))
      J.mouth.scale.y = Math.max(0.18, Math.min(0.62, amp))
      J.head.rotation.x += Math.sin(t * 3.2) * 0.03
    } else if (J.mouth.visible && !anim) {
      J.mouth.visible = false
      J.smile.visible = true
    }
    if (t > blinkAt) {
      const bp = (t - blinkAt) / 0.14
      if (bp >= 1) {
        if (blinkQueue > 0) { blinkQueue -= 1; blinkAt = t + 0.22 }
        else {
          blinkAt = t + 2.2 + Math.random() * 3.6
          if (Math.random() < 0.28) blinkQueue = 1
        }
      }
      const sy = bp >= 1 ? 1 : 1 - Math.sin(Math.min(bp, 1) * Math.PI) * 0.92
      J.eyeL.scale.y = sy
      J.eyeR.scale.y = sy
    }
  }

  // 镜头呼吸 + 轻微视差：让画面不是一张冻结的图
  if (cameraHome) {
    camera.position.y = cameraHome.y + Math.sin(t * 1.9) * 0.004
    camera.position.x = cameraHome.x + mouse.x * 0.018
    camera.lookAt(cameraHome.look)
  }

  renderer.render(scene, camera)
}

/* ---------- 对外 API ---------- */
function playAnim(name) {
  if (!ANIMS[name]) return
  anim = { name, t0: clock.getElapsedTime(), dur: DUR[name] || 1.5 }
  // 剧烈动作后呼吸会加快一阵（情绪唤醒的余韵）
  if (['jump', 'clap', 'spin', 'wave', 'pat', 'stomp'].includes(name)) {
    arousal = Math.min(1, arousal + 0.75)
  }
  // 情绪反应常伴随一次眨眼，动作会更像「活人」
  if (Math.random() < 0.65) blinkAt = clock.getElapsedTime() + 0.12 + Math.random() * 0.12
}

function speak(text, enabled = true) {
  clearTimeout(speakTimer)
  const stop = () => { speaking = false }
  if (!enabled || typeof window === 'undefined' || !window.speechSynthesis) {
    speaking = true
    speakTimer = setTimeout(stop, Math.min(9000, text.length * 90 + 700))
    return
  }
  try {
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text.replace(/[♪～]/g, ''))
    u.lang = 'zh-CN'
    u.rate = 1.05
    u.pitch = 1.25
    const voices = window.speechSynthesis.getVoices()
    const zh = voices.find((v) => v.lang && v.lang.startsWith('zh'))
    if (zh) u.voice = zh
    u.onstart = () => { speaking = true }
    u.onend = u.onerror = stop
    window.speechSynthesis.speak(u)
    speaking = true
    speakTimer = setTimeout(() => { if (!window.speechSynthesis.speaking) stop() },
      Math.min(12000, text.length * 160 + 1500))
  } catch (e) {
    speaking = true
    speakTimer = setTimeout(stop, 2500)
  }
}

function getDebug() {
  return {
    mode,
    fingers: J.fingers
      ? { left: J.fingers.left.length, right: J.fingers.right.length }
      : null,
    expressions: J.exprNames ? [...J.exprNames] : [],
    anim: anim?.name || null,
    rotationY: model ? Number(model.rotation.y.toFixed(3)) : null,
    speaking,
    arousal: Number(arousal.toFixed(2)),
    gaze: { x: Number(gaze.x.toFixed(2)), y: Number(gaze.y.toFixed(2)) },
  }
}

defineExpose({ playAnim, speak, getDebug })

/* ---------- 交互 ---------- */
function onPointerMove(e) {
  const r = wrap.getBoundingClientRect()
  mouse.x = ((e.clientX - r.left) / r.width) * 2 - 1
  mouse.y = ((e.clientY - r.top) / r.height) * 2 - 1
  if (drag) {
    userYaw += (e.clientX - drag) * 0.012
    drag = e.clientX
  }
}

function onDown(e) {
  drag = e.clientX
  e.target.setPointerCapture?.(e.pointerId)
}
function onUp() { drag = null }

function onClick(e) {
  const r = wrap.getBoundingClientRect()
  const ndc = new THREE.Vector2(
    ((e.clientX - r.left) / r.width) * 2 - 1,
    -(((e.clientY - r.top) / r.height) * 2 - 1),
  )
  const rc = new THREE.Raycaster()
  rc.setFromCamera(ndc, camera)
  if (rc.intersectObject(model, true).length) {
    playAnim('surprise')
    emit('poke')
  }
}

function resize() {
  const w = wrap.clientWidth || 320
  const h = wrap.clientHeight || 420
  renderer.setSize(w, h, false)
  camera.aspect = w / h
  camera.updateProjectionMatrix()
}

onMounted(() => {
  init()
  wrap.addEventListener('pointermove', onPointerMove)
  wrap.addEventListener('pointerdown', onDown)
  wrap.addEventListener('pointerup', onUp)
  wrap.addEventListener('pointerleave', onUp)
  cnvEl.value.addEventListener('click', onClick)
  // 诊断钩子：模型加载后可在控制台/自动化中查看手指与表情能力
  if (typeof window !== 'undefined') window.__vrmDebug = getDebug
})

onBeforeUnmount(() => {
  cancelAnimationFrame(rafId)
  wrap.removeEventListener('pointermove', onPointerMove)
  wrap.removeEventListener('pointerdown', onDown)
  wrap.removeEventListener('pointerup', onUp)
  wrap.removeEventListener('pointerleave', onUp)
  cnvEl.value?.removeEventListener('click', onClick)
  disposeFns.forEach((f) => f())
  renderer?.dispose()
  scene?.traverse((o) => {
    o.geometry?.dispose?.()
    if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose())
  })
})
</script>

<style scoped>
.vrm-wrap { position: relative; width: 100%; height: 100%; overflow: hidden; cursor: grab; }
.vrm-wrap:active { cursor: grabbing; }
.vrm-canvas { width: 100%; height: 100%; display: block; }
.vrm-hint {
  position: absolute; left: 12px; bottom: 10px; font-size: 12px;
  color: var(--text-soft); background: rgba(255, 255, 255, .72);
  padding: 4px 10px; border-radius: 20px; pointer-events: none;
  backdrop-filter: blur(4px);
}
</style>