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
  anxious: 2.0, scared: 1.6, protect: 2.2, pat: 1.6, spin: 2.2,
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
let speaking = false
let speakTimer = null
let gradientMap
let lookTarget = null
let fallbackDone = false

/* ---------- 工具 ---------- */
const toon = (color) => new THREE.MeshToonMaterial({ color, gradientMap })
const mesh = (geo, mat, x = 0, y = 0, z = 0) => {
  const m = new THREE.Mesh(geo, mat)
  m.position.set(x, y, z)
  return m
}
const smooth = (p) => p * p * (3 - 2 * p)
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

/* ---------- VRM 加载 ---------- */
function tryLoadVRM() {
  const loader = new GLTFLoader()
  loader.register((parser) => new VRMLoaderPlugin(parser))
  const fallbackTimer = setTimeout(() => { if (mode === 'loading') enableProcedural() }, 12000)
  loader.load(MODEL_URL, (gltf) => {
    clearTimeout(fallbackTimer)
    if (mode !== 'loading') return // 兜底已启用
    const vrm = gltf.userData.vrm
    if (!vrm) { enableProcedural(); return }
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
      // 自动取景：全身入镜
      vrm.scene.updateMatrixWorld(true)
      const box = new THREE.Box3().setFromObject(vrm.scene)
      const h = Math.max(0.5, box.max.y)
      camera.position.set(0.12, h * 0.78, h * 2.15)
      camera.lookAt(0, h * 0.52, 0)
      scene.add(vrm.scene)
      // 眼睛注视目标
      lookTarget = new THREE.Object3D()
      lookTarget.position.set(0, h * 0.55, 1.2)
      scene.add(lookTarget)
      if (vrm.lookAt) vrm.lookAt.target = lookTarget
      const shadow = scene.getObjectByName('__shadow')
      if (shadow) shadow.scale.setScalar(h * 0.42)
      console.info('[VrmGirl] VRM 模型加载成功')
    } catch (e) {
      console.warn('[VrmGirl] VRM 初始化失败，使用兜底建模', e)
      enableProcedural()
    }
  }, undefined, () => {
    clearTimeout(fallbackTimer)
    if (mode === 'loading') enableProcedural()
  })
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
function idlePose(t) {
  const breathe = Math.sin(t * 2.1)
  return {
    torso: { x: 0.02 + breathe * 0.012, sy: 1 + breathe * 0.012, z: 0 },
    head: { x: Math.sin(t * 1.3) * 0.02 + mouse.y * -0.22, y: mouse.x * 0.5, z: Math.sin(t * 0.9) * 0.03 },
    armL: { x: Math.sin(t * 1.6) * 0.04, z: 0.14 + Math.sin(t * 1.6) * 0.02 },
    armR: { x: -Math.sin(t * 1.6) * 0.04, z: -0.14 - Math.sin(t * 1.6) * 0.02 },
    foreL: { x: 0.06 }, foreR: { x: 0.06 },
    legL: { x: 0 }, legR: { x: 0 },
    tailL: { x: Math.sin(t * 1.8) * 0.10, z: 0.10 + Math.sin(t * 1.5 + 1) * 0.08 },
    tailR: { x: Math.sin(t * 1.8 + 0.6) * 0.10, z: -0.10 - Math.sin(t * 1.5) * 0.08 },
    rootY: 0, rootX: 0, mouth: 0,
  }
}

const ANIMS = {
  wave: (p) => ({
    armR: { z: -2.45 * env(p), x: -0.1 },
    foreR: { z: Math.sin(p * 14) * 0.55 * env(p) },
    head: { z: 0.16 * env(p) },
    tailR: { z: -0.55 * env(p) },
  }),
  nod: (p) => ({ head: { x: Math.sin(p * Math.PI * 4) * 0.28 * env(p) } }),
  jump: (p) => {
    const hop = Math.abs(Math.sin(p * Math.PI * 2)) * 0.16 * env(p, 0.1, 0.9)
    return {
      rootY: hop,
      torso: { sy: 1 - Math.sin(p * Math.PI * 4) * 0.05 * env(p) },
      armL: { z: 2.0 * env(p) }, armR: { z: -2.0 * env(p) },
      foreL: { x: -0.3 }, foreR: { x: -0.3 },
      tailL: { x: -0.35 * env(p) }, tailR: { x: -0.35 * env(p) },
      mouth: 0.5 * env(p),
    }
  },
  clap: (p) => ({
    armL: { x: -1.15 * env(p), z: 0.55 + Math.sin(p * Math.PI * 8) * 0.18 },
    armR: { x: -1.15 * env(p), z: -0.55 - Math.sin(p * Math.PI * 8) * 0.18 },
    foreL: { x: -0.5 }, foreR: { x: -0.5 },
    head: { x: -0.08 * env(p) },
    mouth: 0.4 * env(p),
  }),
  curious: (p) => ({
    head: { z: 0.32 * env(p), x: -0.05 * env(p) },
    armR: { x: -1.35 * env(p), z: -0.45 * env(p) },
    foreR: { x: -1.1 * env(p) },
    tailL: { z: 0.2 * env(p) },
  }),
  sad: (p) => ({
    head: { x: 0.38 * env(p), z: 0.06 * env(p) },
    torso: { x: 0.16 * env(p), sy: 0.97 },
    armL: { x: -0.55 * env(p), z: 0.35 * env(p) },
    armR: { x: -0.55 * env(p), z: -0.35 * env(p) },
    foreL: { x: -0.85 * env(p) }, foreR: { x: -0.85 * env(p) },
    tailL: { z: 0.42 * env(p), x: 0.15 * env(p) },
    tailR: { z: -0.42 * env(p), x: 0.15 * env(p) },
  }),
  anxious: (p) => ({
    rootX: Math.sin(p * 34) * 0.008 * env(p),
    head: { x: 0.12 * env(p), z: Math.sin(p * 20) * 0.02 * env(p) },
    armL: { x: -0.9 * env(p), z: 0.55 * env(p) },
    armR: { x: -0.9 * env(p), z: -0.55 * env(p) },
    foreL: { x: -1.25 * env(p) }, foreR: { x: -1.25 * env(p) },
    tailL: { z: 0.2 * env(p) }, tailR: { z: -0.2 * env(p) },
  }),
  scared: (p) => ({
    head: { x: 0.22 * env(p), z: Math.sin(p * 26) * 0.03 * env(p) },
    torso: { x: 0.18 * env(p) },
    armL: { x: -1.9 * env(p), z: 0.75 * env(p) },
    armR: { x: -1.9 * env(p), z: -0.75 * env(p) },
    foreL: { x: -0.6 * env(p) }, foreR: { x: -0.6 * env(p) },
    rootY: -0.045 * env(p),
    mouth: 0.6 * env(p),
  }),
  protect: (p) => ({
    head: { x: 0.02 * env(p) },
    torso: { x: 0.12 * env(p) },
    armL: { x: -1.5 * env(p), z: 0.22 * env(p) },
    armR: { x: -1.5 * env(p), z: -0.22 * env(p) },
    foreL: { x: -0.15 }, foreR: { x: -0.15 },
    tailL: { x: 0.1 }, tailR: { x: 0.1 },
  }),
  pat: (p) => ({
    head: { x: -0.12 * env(p), z: Math.sin(p * Math.PI * 6) * 0.05 * env(p) },
    torso: { sy: 1 - 0.04 * env(p) },
    tailL: { z: 0.3 * env(p), x: Math.sin(p * 22) * 0.2 * env(p) },
    tailR: { z: -0.3 * env(p), x: Math.sin(p * 22 + 1) * 0.2 * env(p) },
    armL: { z: 0.9 * env(p) }, armR: { z: -0.9 * env(p) },
    mouth: 0.45 * env(p),
  }),
  spin: (p) => {
    const e = smooth(p)
    return {
      armL: { z: 1.35 * env(p) }, armR: { z: -1.35 * env(p) },
      rootY: Math.sin(p * Math.PI) * 0.05,
      __yaw: e * Math.PI * 2,
    }
  },
  surprise: (p) => ({
    rootY: Math.abs(Math.sin(p * Math.PI * 2)) * 0.05 * env(p),
    armL: { z: 1.6 * env(p), x: -0.3 * env(p) },
    armR: { z: -1.6 * env(p), x: -0.3 * env(p) },
    head: { x: -0.1 * env(p) },
    mouth: 0.7 * env(p),
    tailL: { x: -0.4 * env(p) }, tailR: { x: -0.4 * env(p) },
  }),
  stomp: (p) => ({
    head: { x: -0.08 * env(p), z: Math.sin(p * 18) * 0.03 * env(p) },
    armL: { x: 0.35 * env(p), z: 0.95 * env(p) },
    armR: { x: 0.35 * env(p), z: -0.95 * env(p) },
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
}

/* VRM 模式：写入 normalized 骨骼 */
function applyPoseVRM(p) {
  const hb = (n) => J.humanoid?.getNormalizedBoneNode(n)
  const set = (node, x, y, z) => { if (node) node.rotation.set(x, y, z) }
  set(hb('spine'), p.torso.x * 0.6, 0, p.torso.z)
  set(hb('chest'), p.torso.x * 0.6, 0, 0)
  set(hb('neck'), p.head.x * 0.25, p.head.y * 0.3, p.head.z * 0.3)
  set(hb('head'), p.head.x, p.head.y, p.head.z)
  // 手臂：rest ±1.25（自然下垂），姿态值为抬起量
  set(hb('leftUpperArm'), p.armL.x, 0, -1.25 + p.armL.z)
  set(hb('rightUpperArm'), p.armR.x, 0, 1.25 + p.armR.z)
  set(hb('leftLowerArm'), -p.foreL.x, 0, 0)
  set(hb('rightLowerArm'), -p.foreR.x, 0, 0)
  set(hb('leftUpperLeg'), p.legL.x, 0, 0)
  set(hb('rightUpperLeg'), p.legR.x, 0, 0)
  model.position.y = p.rootY
  model.position.x = p.rootX
}

function setExpr(name, v) {
  try { J.em?.setValue?.(name, v) } catch (e) { /* 模型无该表情时忽略 */ }
}

function tick() {
  rafId = requestAnimationFrame(tick)
  if (!model) { renderer.render(scene, camera); return }
  const dt = clock.getDelta()
  const t = clock.getElapsedTime()
  const base = idlePose(t)
  let pose = base
  let yaw = 0

  if (anim) {
    const p = Math.min(1, (t - anim.t0) / anim.dur)
    const fn = ANIMS[anim.name]
    if (fn) {
      const d = fn(p, t)
      yaw = d.__yaw || 0
      delete d.__yaw
      pose = addPose(base, d)
    }
    if (p >= 1) anim = null
  }

  if (mode === 'vrm') {
    applyPoseVRM(pose)
    model.rotation.y = userYaw + yaw
    // 表情：根据动作与说话状态
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
    setExpr('happy', ex.happy)
    setExpr('sad', ex.sad)
    setExpr('angry', ex.angry)
    setExpr('surprised', ex.surprised)
    setExpr('relaxed', ex.relaxed)
    // 说话口型 + 眨眼
    setExpr('aa', speaking ? 0.25 + Math.abs(Math.sin(t * 11)) * 0.55 : Math.min(0.35, pose.mouth))
    if (t > blinkAt) {
      const bp = (t - blinkAt) / 0.16
      if (bp >= 1) blinkAt = t + 2 + Math.random() * 3.5
      setExpr('blink', 1 - Math.sin(Math.min(bp, 1) * Math.PI))
    } else {
      setExpr('blink', 0)
    }
    // 眼睛注视
    if (lookTarget && model) {
      const h = camera.position.y / 0.78 || 1.4
      lookTarget.position.set(mouse.x * 0.9, h * 0.55 - mouse.y * 0.35, 1.3)
    }
    J.vrm.update(dt)
  } else {
    applyPoseProcedural(pose)
    model.rotation.y += (userYaw + yaw - model.rotation.y) * 0.5
    if (speaking) {
      J.mouth.visible = true
      J.smile.visible = false
      J.mouth.scale.y = 0.22 + Math.abs(Math.sin(t * 11)) * 0.38
      J.head.rotation.x += Math.sin(t * 3.2) * 0.03
    } else if (J.mouth.visible && !anim) {
      J.mouth.visible = false
      J.smile.visible = true
    }
    if (t > blinkAt) {
      const bp = (t - blinkAt) / 0.16
      if (bp >= 1) blinkAt = t + 2 + Math.random() * 3.5
      const sy = bp >= 1 ? 1 : 1 - Math.sin(bp * Math.PI) * 0.92
      J.eyeL.scale.y = sy
      J.eyeR.scale.y = sy
    }
  }

  renderer.render(scene, camera)
}

/* ---------- 对外 API ---------- */
function playAnim(name) {
  if (!ANIMS[name]) return
  anim = { name, t0: clock.getElapsedTime(), dur: DUR[name] || 1.5 }
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

defineExpose({ playAnim, speak })

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