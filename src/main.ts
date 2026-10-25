import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { loadEngineAssets, Engine, type EngineAssets } from './model';
import { bladePoint, HERO_PLATFORM_TOP, HERO_TIP } from './hero-blade';
import { createEffects, type Effects } from './effects';
import { EngineAudio } from './audio';
import { createBackdrop, appendBackdropControl, setBackdrop } from './backdrop';
import { renderPixelRatio, onRenderQuality, getRenderQuality, setRenderQuality, type RenderQuality } from './render-quality';
import { languageControl, setLanguage, t, onLanguage } from './i18n';
import './style.css';

type View = 'assembly' | 'cutaway' | 'explode';

const DESCRIPTIONS: Record<string, string> = {
  fan: '风扇吸入空气，一部分进入外涵道直接产生推力，其余进入核心机。',
  'fan-cowl': '进气罩包住风扇，把气流平顺地导入。剖开它就能看到风扇叶片。',
  compressor: '压气机由多级转子和静子交替组成，逐级提高空气压力。',
  combustor: '燃油在这里与高压空气混合燃烧，燃气温度远高于金属熔点。',
  turbine: '高温燃气推动涡轮旋转，涡轮通过主轴带动风扇和压气机。',
  exhaust: '燃气经尾喷管加速排出，剩余的焓变成推力。',
  'core-casing': '核心机机匣把压气机、燃烧室和涡轮连成一个整体。',
  nacelle: '外涵道机匣构成冷气流通道，也承受风扇的推力载荷。',
  shaft: '主轴把涡轮的功率传给压气机和风扇。',
};

const EXPLODE: Record<string, THREE.Vector3Tuple> = {
  fan: [1.55, 0, 0],
  'fan-cowl': [2.25, 1.05, 0],
  compressor: [0.72, 0, 0],
  combustor: [0, 0, 0],
  turbine: [-0.62, 0, 0],
  exhaust: [-1.45, 0, 0],
  'core-casing': [0, -1.35, 0],
  nacelle: [0, 1.55, 0],
  shaft: [-0.25, 0, 0],
};

const canvas = document.querySelector<HTMLCanvasElement>('#scene')!;
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(renderPixelRatio(innerWidth, innerHeight));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
const backdrop = createBackdrop(scene);
const camera = new THREE.PerspectiveCamera(32, innerWidth / innerHeight, 0.05, 80);
camera.position.set(3.4, 1.9, 3.6);

const controls = new OrbitControls(camera, canvas);
controls.target.set(0.15, 0, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.minDistance = 0.06;
controls.maxDistance = 26;
controls.maxPolarAngle = Math.PI * 0.94;

const hemisphere = new THREE.HemisphereLight('#dfeaf2', '#0a1418', 0.5);
scene.add(hemisphere);
const key = new THREE.DirectionalLight('#fff4e2', 2.6);
key.position.set(4.2, 6.5, 5.5);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -5; key.shadow.camera.right = 5;
key.shadow.camera.top = 5; key.shadow.camera.bottom = -5;
key.shadow.camera.near = 0.5; key.shadow.camera.far = 22;
key.shadow.bias = -0.0006;
scene.add(key);
const fill = new THREE.DirectionalLight('#bcd7ea', 0.75);
fill.position.set(-5, 2.5, -4);
scene.add(fill);
const rim = new THREE.DirectionalLight('#8fc6de', 0.55);
rim.position.set(0, -4.5, 3);
scene.add(rim);

let engineEnvironment: THREE.Texture | null = null;
let studioEnvironment: THREE.Texture | null = null;
let studioActive = false;
new RGBELoader().load('/environment/poly_haven_studio_1k.hdr', texture => {
  const pmrem = new THREE.PMREMGenerator(renderer);
  texture.mapping = THREE.EquirectangularReflectionMapping;
  engineEnvironment = pmrem.fromEquirectangular(texture).texture;
  if (!studioActive) scene.environment = engineEnvironment;
  texture.dispose();
  pmrem.dispose();
});
let contrastEnvironment: THREE.Texture | null = null;
/**
 * Studio lighting for the close-up blade: 'room' is three.js's neutral grey room,
 * 'contrast' the bundled high-contrast studio HDR (loaded on first use).
 */
function useStudioEnvironment(on: boolean, kind: 'room' | 'contrast' = 'room') {
  studioActive = on;
  if (!on) { scene.environment = engineEnvironment; return; }
  if (kind === 'contrast') {
    if (contrastEnvironment) { scene.environment = contrastEnvironment; return; }
    new RGBELoader().load('/environment/studio_kontrast_02_1k.hdr', texture => {
      const pmrem = new THREE.PMREMGenerator(renderer);
      texture.mapping = THREE.EquirectangularReflectionMapping;
      contrastEnvironment = pmrem.fromEquirectangular(texture).texture;
      texture.dispose(); pmrem.dispose();
      if (studioActive) scene.environment = contrastEnvironment;
    });
    return;
  }
  if (!studioEnvironment) {
    const pmrem = new THREE.PMREMGenerator(renderer);
    studioEnvironment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
  }
  scene.environment = studioEnvironment;
}

const audio = new EngineAudio();
let assets: EngineAssets | null = null;
let engine: Engine | null = null;
let secondary: Engine | null = null;
let effects: Effects | null = null;

let view: View = 'assembly';
let running = false;
let explode = 0;
let explodeTarget = 0;
let selected: string | null = null;
let isolate = false;

const clipPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
const cameraGoal = { position: camera.position.clone(), target: controls.target.clone() };
let cameraAnimating = false;

const loader = document.querySelector<HTMLDivElement>('#loader')!;
const loaderText = loader.querySelector('span')!;
const partsList = document.querySelector<HTMLOListElement>('#part-list')!;
const info = document.querySelector<HTMLElement>('#info')!;
const infoTitle = document.querySelector<HTMLElement>('#info-title')!;
const infoBody = document.querySelector<HTMLElement>('#info-body')!;
const explodeInput = document.querySelector<HTMLInputElement>('#explode')!;
const explodeField = document.querySelector<HTMLElement>('#explode-field')!;
const runButton = document.querySelector<HTMLButtonElement>('#run')!;
const soundButton = document.querySelector<HTMLButtonElement>('#sound')!;
const qualitySelect = document.querySelector<HTMLSelectElement>('#quality')!;
const isolateButton = document.querySelector<HTMLButtonElement>('#isolate')!;
const clearButton = document.querySelector<HTMLButtonElement>('#clear')!;
const partButtons = new Map<string, HTMLButtonElement>();

function buildPartsList() {
  if (!engine) return;
  for (const moduleRuntime of engine.modules) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.part = moduleRuntime.meta.id;
    button.setAttribute('aria-pressed', 'false');
    button.innerHTML = `<span>${moduleRuntime.meta.name}</span><small>${moduleRuntime.meta.partCount}</small>`;
    button.onclick = () => select(moduleRuntime.meta.id);
    partsList.append(button);
    partButtons.set(moduleRuntime.meta.id, button);
  }
}

function moduleIds(): string[] {
  return engine ? engine.modules.map(m => m.meta.id) : [];
}

function setExplode(value: number) {
  explode = value;
  explodeInput.value = String(Math.round(value * 100));
  if (!engine) return;
  for (const moduleRuntime of engine.modules) {
    const offset = EXPLODE[moduleRuntime.meta.id] ?? [0, 0, 0];
    moduleRuntime.group.position.set(offset[0] * value, offset[1] * value, offset[2] * value);
  }
  applyVisibility();
}

function applyVisibility() {
  if (!engine) return;
  for (const moduleRuntime of engine.modules) {
    const hide = isolate && moduleRuntime.meta.id !== selected;
    engine.setVisible(moduleRuntime.meta.id, !hide);
  }
  applyCutawayClipping(view === 'cutaway' && !isolate);
  if (effects) effects.group.visible = !isolate && explode < 0.4;
}

function applyCutawayClipping(on: boolean) {
  renderer.clippingPlanes = on ? [clipPlane] : [];
}

function updateIsolateButton() {
  isolateButton.setAttribute('aria-pressed', String(isolate));
  isolateButton.textContent = isolate ? t('显示全部') : t('单独显示');
}

function applyView(next: View) {
  view = next;
  isolate = false;
  updateIsolateButton();
  document.querySelectorAll<HTMLButtonElement>('#views button').forEach(button => {
    if (button.dataset.view === next) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  explodeField.classList.toggle('visible', next === 'explode');
  if (!engine) return;
  explodeTarget = next === 'explode' ? (Number(explodeInput.value) / 100 || 1) : 0;
  if (next === 'explode') explodeInput.value = String(Math.round(explodeTarget * 100));
  applyVisibility();
  fitCamera(next === 'explode' ? explodeTarget : 0);
}

function highlight() {
  if (!engine) return;
  for (const moduleRuntime of engine.modules) {
    if (!selected) engine.setColor(moduleRuntime.meta.id, null);
    else if (moduleRuntime.meta.id === selected) engine.setColor(moduleRuntime.meta.id, null);
    else engine.setDim(moduleRuntime.meta.id, 0.2);
  }
  for (const [id, button] of partButtons) button.setAttribute('aria-pressed', String(selected === id));
}

function select(id: string | null, focus = true) {
  selected = id;
  if (!id) isolate = false;
  updateIsolateButton();
  highlight();
  applyVisibility();
  if (!id || !engine) {
    info.hidden = true;
    if (focus) focusOn(null);
    return;
  }
  const moduleRuntime = engine.modules.find(m => m.meta.id === id);
  if (!moduleRuntime) return;
  info.hidden = false;
  infoTitle.textContent = t(moduleRuntime.meta.name);
  const componentNames = moduleRuntime.components.slice(0, 3).map(c => t(c.meta.name)).join('、');
  infoBody.textContent = `${t(DESCRIPTIONS[id] ?? '')} ${componentNames}等 ${moduleRuntime.meta.components.length} 个组件，共 ${moduleRuntime.meta.partCount} 个零件。`;
  if (focus) focusOn(moduleRuntime.group);
}

function selectPart(partId: string) {
  if (!engine) return;
  const meta = engine.getPart(partId);
  if (!meta) return;
  selected = meta.module;
  isolate = false;
  updateIsolateButton();
  highlight();
  applyVisibility();
  info.hidden = false;
  const moduleMeta = engine.modules.find(m => m.meta.id === meta.module)?.meta;
  infoTitle.textContent = `${t(moduleMeta?.name ?? meta.module)} · ${meta.name}`;
  infoBody.textContent = t(DESCRIPTIONS[meta.module] ?? '');
  focusOn(engine.root);
}

function fitCamera(spread = 0) {
  if (!engine) return;
  const box = new THREE.Box3().setFromObject(engine.root);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const halfWidth = Math.hypot(size.x / 2 + spread * 2.6, size.z / 2 + spread * 1.55);
  const halfHeight = size.y / 2 + spread * 2.15;
  const vertical = THREE.MathUtils.degToRad(camera.fov) / 2;
  const horizontal = Math.atan(Math.tan(vertical) * camera.aspect);
  const distance = Math.max(halfHeight / Math.tan(vertical), halfWidth / Math.tan(horizontal)) * 1.12;
  controls.maxDistance = Math.max(16, distance * 1.3);
  const direction = new THREE.Vector3(0.78, 0.36, 0.92).normalize();
  cameraGoal.target.copy(center);
  cameraGoal.position.copy(center).addScaledVector(direction, distance);
  cameraAnimating = true;
}

function focusOn(object: THREE.Object3D | null) {
  if (!engine) return;
  if (!object) { fitCamera(); return; }
  const box = new THREE.Box3().setFromObject(object);
  if (box.isEmpty()) { fitCamera(); return; }
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(0.05, size.length() / 2);
  const vertical = THREE.MathUtils.degToRad(camera.fov) / 2;
  const horizontal = Math.atan(Math.tan(vertical) * camera.aspect);
  const distance = Math.max(0.12, radius / Math.sin(Math.min(vertical, horizontal)) * 1.15);
  const direction = camera.position.clone().sub(controls.target).normalize();
  cameraGoal.target.copy(center);
  cameraGoal.position.copy(center).addScaledVector(direction, distance);
  cameraAnimating = true;
}

function setRunning(next: boolean) {
  running = next;
  runButton.setAttribute('aria-pressed', String(running));
  runButton.textContent = running ? t('停止') : t('运行');
  audio.setRunning(running);
}

runButton.addEventListener('click', () => setRunning(!running));
soundButton.addEventListener('click', async () => {
  const on = await audio.toggle();
  soundButton.setAttribute('aria-pressed', String(on));
  soundButton.textContent = on ? t('声音已开') : t('声音');
});
isolateButton.addEventListener('click', () => {
  if (!selected) return;
  isolate = !isolate;
  updateIsolateButton();
  applyVisibility();
  if (isolate && engine) {
    const moduleRuntime = engine.modules.find(m => m.meta.id === selected);
    if (moduleRuntime) focusOn(moduleRuntime.group);
  }
});
clearButton.addEventListener('click', () => select(null));

qualitySelect.value = getRenderQuality();
qualitySelect.onchange = () => setRenderQuality(qualitySelect.value as RenderQuality);
onRenderQuality(() => {
  qualitySelect.value = getRenderQuality();
  renderer.setPixelRatio(renderPixelRatio(innerWidth, innerHeight));
});
onLanguage(() => {
  runButton.textContent = running ? t('停止') : t('运行');
  soundButton.textContent = audio.isOn ? t('声音已开') : t('声音');
  updateIsolateButton();
  if (selected && engine) {
    const moduleRuntime = engine.modules.find(m => m.meta.id === selected);
    if (moduleRuntime) infoTitle.textContent = t(moduleRuntime.meta.name);
  }
});

document.querySelector('#language-host')!.append(languageControl());
appendBackdropControl(document.querySelector('#backdrop-host')!);
document.querySelectorAll<HTMLButtonElement>('#views button').forEach(button => {
  button.onclick = () => applyView(button.dataset.view as View);
});
explodeInput.oninput = () => { explodeTarget = Number(explodeInput.value) / 100; };
explodeInput.onchange = () => { if (view !== 'explode') applyView('explode'); };

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let downX = 0, downY = 0;
canvas.addEventListener('pointerdown', event => { downX = event.clientX; downY = event.clientY; });
canvas.addEventListener('pointerup', event => {
  if (Math.hypot(event.clientX - downX, event.clientY - downY) > 6 || !engine) return;
  const rect = canvas.getBoundingClientRect();
  pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const id = engine.pick(raycaster);
  if (id) selectPart(id); else select(null);
});

function resize() {
  const width = innerWidth, height = innerHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  backdrop.resize(width * renderer.getPixelRatio(), height * renderer.getPixelRatio());
  if (studioBackground) scene.background = studioBackground;
}
addEventListener('resize', resize);

const HERO_IDS = ['root', 'platform', 'tip', 'edges', 'wall-ps', 'wall-ps-cut', 'wall-ss', 'dividers',
  'ribs-1', 'ribs-2', 'ribs-3', 'pin-fins', 'airflow', 'coat-base', 'coat-bond', 'coat-tgo', 'coat-ysz',
  'film-ps-1', 'film-ps-2', 'film-ps-3', 'film-ps-4', 'film-ss-1', 'film-ss-2', 'film-ss-3', 'film-ss-4']
  .map(id => `turbine.hero-blade.${id}`);

/** ?debug=hero-check: runtime self-check of the close-up blade, printed on the page. */
function runHeroCheck(current: Engine) {
  const hero = current.hero, runtime = hero.runtime;
  const lines: string[] = [];
  let ok = true;
  const check = (pass: boolean, label: string, detail = '') => {
    ok &&= pass;
    lines.push(`${pass ? 'PASS' : 'FAIL'}  ${label}${detail ? '  ' + detail : ''}`);
  };
  const listed = current.listParts('turbine.hero-blade');
  const missing = HERO_IDS.filter(id => !listed.includes(id) || !current.getPart(id) || current.resolve(id)[0] !== id);
  check(missing.length === 0 && listed.length === HERO_IDS.length, `${HERO_IDS.length} 个 id 都能取到`,
    missing.length ? `缺少 ${missing.join(', ')}` : `listParts 返回 ${listed.length} 个`);

  // Colour isolation: only the coloured part changes, the rest of the blade and the engine do not.
  const engineColors = () => [...current.parts.values()].map(state => state.color.getHexString()).join();
  const engineBefore = engineColors();
  const leaks: string[] = [];
  for (const id of HERO_IDS) {
    const before = HERO_IDS.map(other => runtime.materialState(other));
    current.setColor(id, '#ff2600');
    const after = HERO_IDS.map(other => runtime.materialState(other));
    const changed = HERO_IDS.filter((other, i) => before[i] !== after[i]);
    if (changed.length !== 1 || changed[0] !== id) leaks.push(`${id} -> ${changed.join('/') || '无变化'}`);
    if (engineColors() !== engineBefore) leaks.push(`${id} -> 整机`);
    current.setColor(id, null);
  }
  check(leaks.length === 0, '每个 id 设颜色后只有它自己变色', leaks.join('; '));

  // Every caller API restores.
  const base = runtime.snapshot();
  for (const id of HERO_IDS) {
    current.setDim(id, 0.2); current.setColor(id, null);
    current.setOpacity(id, 0.3); current.setOpacity(id, 1);
    current.setVisible(id, false); current.setVisible(id, true);
  }
  check(runtime.snapshot() === base, 'setDim / setOpacity / setVisible 设置后能恢复');

  // Continuous parameters: 0 -> 1 -> 0, repeated in one frame, with mid values.
  const sweep = [0, 0.1, 0.3, 0.5, 0.75, 0.99, 1, 1, 0.6, 0.2, 0];
  const restored: string[] = [];
  for (const [name, set] of [['setCutaway', (v: number) => hero.setCutaway(v)], ['setCoatings', (v: number) => hero.setCoatings(v)],
    ['setAirflow', (v: number) => hero.setAirflow(v)]] as [string, (v: number) => void][]) {
    sweep.forEach(set);
    set(0); set(0);
    if (runtime.snapshot() !== base) restored.push(name);
  }
  for (const v of sweep) { hero.setCutaway(v); hero.setCoatings(v); hero.setAirflow(v); }
  hero.setCutaway(0); hero.setCoatings(0); hero.setAirflow(0);
  if (runtime.snapshot() !== base) restored.push('三个一起');
  check(restored.length === 0, '三个连续参数 0→1→0 后几何和材质恢复原样', restored.length ? `未恢复：${restored.join(', ')}` : '');

  // Same value twice in a frame gives the same state.
  hero.setCutaway(0.5); const once = runtime.snapshot(); hero.setCutaway(0.5);
  check(runtime.snapshot() === once, '同一帧里重复设置结果一致');
  hero.setCutaway(0);

  const rise = runtime.linerRise();
  check(rise <= 1e-6, '孔内衬不高出叶片表面', `最高处 ${rise.toExponential(2)}（负数表示低于表面）`);
  check(!current.getPart('turbine.hero-blade.neck') && !current.resolve('turbine.hero-blade.film-le-1').length, '旧零件 id 已不存在');
  // poseFor: aerofoil height and tip radius match ring blade 001.
  const ringId = 'turbine.stage-1-blades.001';
  const seated = hero.poseFor(ringId);
  const ring = current.partRestWorldMatrix(ringId);
  if (seated && ring) {
    const height = (HERO_TIP - HERO_PLATFORM_TOP) * seated.scale;
    const radial = (v: THREE.Vector3) => Math.hypot(v.y, v.z);
    const tip = radial(bladePoint(0.5, 1, 0).applyMatrix4(seated.matrix));
    const ringTip = radial(new THREE.Vector3(0, 0.146, 0).applyMatrix4(ring));
    // Mid-span chord centre (halfway between leading and trailing edge) on the ring blade's stacking axis.
    const chordMid = bladePoint(0, 0.5, 0).add(bladePoint(1, 0.5, 0)).multiplyScalar(0.5).applyMatrix4(seated.matrix);
    const axial = Math.abs(chordMid.x - new THREE.Vector3().setFromMatrixPosition(ring).x);
    check(Math.abs(height - 0.126) < 1e-4 && Math.abs(tip - ringTip) < 0.002 && axial < 0.003,
      'poseFor 缩放和位置与 001 号叶片一致',
      `叶身高 ${height.toFixed(4)}（环上 0.1260），叶尖半径 ${tip.toFixed(4)}（环上 ${ringTip.toFixed(4)}），轴向偏差 ${axial.toFixed(4)}`);
  } else check(false, 'poseFor 返回位姿');
  hero.reset();
  check(runtime.snapshot() === base && !hero.visible, 'reset 后恢复隐藏和初始状态');
  lines.push(`三角形 ${runtime.triangles().toLocaleString('en-US')}`);
  lines.unshift(ok ? 'HERO-CHECK PASS' : 'HERO-CHECK FAIL');
  return { ok, lines };
}

function showHeroCheck(report: { ok: boolean; lines: string[] }) {
  const panel = document.createElement('pre');
  panel.id = 'hero-check';
  panel.textContent = report.lines.join('\n');
  panel.style.cssText = 'position:fixed;left:24px;top:120px;z-index:50;margin:0;padding:14px 16px;max-width:760px;'
    + 'white-space:pre-wrap;font:13px/1.55 ui-monospace,monospace;color:#e8f1f4;border-radius:8px;'
    + `background:${report.ok ? 'rgba(10,40,24,.92)' : 'rgba(60,12,12,.92)'};`;
  document.body.append(panel);
}

// ---- Close-up blade review states (?debug=hero).
// Studio: the blade alone at reference scale with the reference tilt, which is the
// caller's choice of orientation (the blade itself has none).
const STUDIO_TILT = new THREE.Euler(-0.06, -0.12, -0.13);
const STUDIO_BACKGROUNDS = { dark: new THREE.Color('#03070c'), light: new THREE.Color('#ececec') };
let studioBackground: THREE.Color | null = null;
const chrome = () => document.querySelectorAll<HTMLElement>('.topbar, .parts, .info, .dock, .credit');

function heroStudio(current: Engine, params: URLSearchParams) {
  const hero = current.hero;
  const num = (key: string, fallback = 0) => {
    const value = Number(params.get(key) ?? fallback);
    return Number.isFinite(value) ? value : fallback;
  };
  for (const moduleRuntime of current.modules) current.setVisible(moduleRuntime.meta.id, false);
  if (effects) effects.setVisible(false);
  setRunning(false);
  chrome().forEach(element => { element.style.visibility = 'hidden'; });
  studioBackground = STUDIO_BACKGROUNDS[params.get('bg') === 'light' ? 'light' : 'dark'];
  scene.background = studioBackground;
  // Studio light: lower key and environment so the alloy reads as dark metal and
  // the ceramic as mid grey, as in the reference renders. Restored by applyState.
  renderer.toneMappingExposure = num('exposure', 0.62);
  key.color.set('#ffffff'); fill.color.set('#dfe8ee');
  key.intensity = num('key', 0.8);
  fill.intensity = num('fill', 0.3);
  rim.intensity = num('rim', 0.25);
  hemisphere.intensity = num('hemi', 0.35);
  scene.environmentIntensity = num('env', 1);
  useStudioEnvironment(true, params.get('studio') === 'room' ? 'room' : 'contrast');
  scene.environmentRotation.set(0, THREE.MathUtils.degToRad(num('envrot', 10)), 0);

  hero.setCutaway(num('cut'));
  hero.setCoatings(num('coat'));
  hero.setAirflow(num('flow'));
  const rows = params.get('rows');
  const ps = [1, 2, 3, 4].map(n => `turbine.hero-blade.film-ps-${n}`);
  const ss = [1, 2, 3, 4].map(n => `turbine.hero-blade.film-ss-${n}`);
  const lit = rows === 'ps' ? ps : rows === 'ss' ? ss : rows === 'all' ? [...ps, ...ss]
    : rows && /^(ps|ss)[1-4]$/.test(rows) ? [`turbine.hero-blade.film-${rows.slice(0, 2)}-${rows[2]}`] : [];
  if (lit.length) current.setColor(lit, '#39d0ff');
  if (params.get('ceramic') === '1') current.setColor('turbine.hero-blade.coat-ysz', '#e03b2f');

  const pose = params.get('pose');
  if (pose) {
    // Ring swap: only the first-stage blade ring and its disc stay.
    current.setVisible(['turbine.stage-1-blades', 'turbine.stage-1-disk'], true);
    const blade = bladeIdFor(pose);
    hero.poseFor(blade);
    current.setVisible(blade, false);
    hero.setLanding(num('land', 1));
    const seat = new THREE.Vector3(...hero.pose().position);
    const radial = new THREE.Vector3(0, seat.y, seat.z).normalize();
    const side = new THREE.Vector3(0, -radial.z, radial.y);
    if (params.get('shot') === 'near') {
      // Camera at r = 0.72, just outside the turbine band (r 0.69).
      cameraGoal.target.set(seat.x, 0, 0).addScaledVector(radial, 0.375);
      cameraGoal.position.set(seat.x + 0.13, 0, 0).addScaledVector(radial, 0.695).addScaledVector(side, 0.19);
    } else {
      cameraGoal.target.set(seat.x, 0, 0).addScaledVector(radial, 0.1);
      cameraGoal.position.set(seat.x + 1.25, 0, 0).addScaledVector(radial, 1.25).addScaledVector(side, 1.7);
    }
    return;
  }

  const matrix = new THREE.Matrix4().makeRotationFromEuler(STUDIO_TILT);
  hero.placeAt(matrix);
  hero.show(true);
  const angle = params.get('angle') ?? 'front';
  if (angle === 'zoom') {
    // Platform-to-tip aerofoil at 80 % of the frame height, oblique, to show creases.
    const height = 4.17 - 0.555, vertical = THREE.MathUtils.degToRad(camera.fov) / 2;
    const distance = height / 0.8 / 2 / Math.tan(vertical);
    cameraGoal.target.set(0.2, 2.36, 0.05).applyMatrix4(matrix);
    cameraGoal.position.copy(cameraGoal.target).addScaledVector(new THREE.Vector3(0.62, 0.1, 0.78).normalize(), distance);
  } else if (angle === 'edge') {
    // Grazing view along the pressure face from the leading edge, to check that
    // no hole liner stands proud of the surface.
    cameraGoal.target.set(-0.35, 2.4, 0.3).applyMatrix4(matrix);
    cameraGoal.position.copy(cameraGoal.target).addScaledVector(new THREE.Vector3(-0.93, 0.12, 0.34).normalize(), num('dist', 4.2));
  } else if (angle === 'back') {
    cameraGoal.target.set(0.55, 1.85, -0.1);
    cameraGoal.position.copy(cameraGoal.target).addScaledVector(new THREE.Vector3(-0.08, 0.09, -1).normalize(), num('dist', 9.4));
  } else {
    cameraGoal.target.set(0.86, 1.92, 0.25);
    cameraGoal.position.copy(cameraGoal.target).addScaledVector(new THREE.Vector3(0.06, 0.09, 1).normalize(), num('dist', 9.9));
  }
}

function applyDebug(params: URLSearchParams) {
  if (!engine) return;
  const mode = params.get('debug');
  if (!mode) return;
  const blades = engine.listParts('turbine.stage-1-blades');
  if (mode === 'single-blade') {
    for (const moduleRuntime of engine.modules) engine.setVisible(moduleRuntime.meta.id, false);
    engine.setVisible(blades[0], true);
    engine.setTransform(blades[0], { position: [0, 0, 0], rotation: [0, 0, 0] });
    if (effects) effects.setVisible(false);
    setBackdrop('white');
    const state = engine.parts.get(blades[0]);
    if (state?.promoted) {
      const m = state.matrix.clone();
      m.setPosition(0, 0, 0);
      state.promoted.matrixAutoUpdate = false;
      state.promoted.matrix.copy(m);
      state.promoted.matrixWorldNeedsUpdate = true;
    }
    const angle = params.get('angle') ?? 'face';
    cameraGoal.target.set(0, 0.06, 0);
    if (angle === 'leading') cameraGoal.position.set(0.37, 0.10, 0.26);
    else if (angle === 'oblique') cameraGoal.position.set(-0.12, 0.30, 0.30);
    else cameraGoal.position.set(0.26, 0.10, -0.36);
    cameraAnimating = true;
    setRunning(false);
    const meta = engine.getPart(blades[0]);
    if (meta) {
      info.hidden = false;
      infoTitle.textContent = meta.name;
      infoBody.textContent = '第一级涡轮叶片，单独取出。';
    }
  } else if (mode === 'red-16') {
    engine.setColor(blades.slice(0, 16), '#e03b2f');
    for (const moduleRuntime of engine.modules) engine.setVisible(moduleRuntime.meta.id, moduleRuntime.meta.id === 'turbine');
    const turbine = engine.modules.find(m => m.meta.id === 'turbine');
    if (turbine) {
      focusOn(turbine.group);
      cameraAnimating = false;
      camera.position.copy(cameraGoal.position);
      controls.target.copy(cameraGoal.target);
    }
  } else if (mode === 'extract-16') {
    engine.setColor(blades.slice(0, 16), '#e03b2f');
    engine.setColor(blades.slice(40, 48), '#1f9fd0');
    engine.setTransform(blades.slice(0, 16), { position: [0.9, 0.75, 0.55], rotation: [0, 0, 0] });
    applyView('assembly');
    fitCamera();
    running = true;
    audio.setRunning(true);
  } else if (mode === 'ring-closeup') {
    for (const moduleRuntime of engine.modules) engine.setVisible(moduleRuntime.meta.id, moduleRuntime.meta.id === 'turbine');
    engine.setVisible('turbine.inner-cone', false);
    engine.setVisible('turbine.band', false);
    const turbine = engine.modules.find(m => m.meta.id === 'turbine');
    if (turbine) {
      cameraGoal.target.set(-1.36, 0, 0);
      cameraGoal.position.set(-0.15, 0.65, 1.35);
      cameraAnimating = true;
    }
  } else if (mode === 'alpha-16') {
    engine.setOpacity(blades.slice(0, 16), 0.3);
    engine.setColor(blades.slice(40, 48), '#e03b2f');
    for (const moduleRuntime of engine.modules) engine.setVisible(moduleRuntime.meta.id, moduleRuntime.meta.id === 'turbine');
    engine.setVisible('turbine.inner-cone', false);
    cameraGoal.target.set(-1.36, 0, 0);
    cameraGoal.position.set(-0.55, 0.5, 0.85);
    cameraAnimating = true;
    running = true;
    audio.setRunning(true);
  } else if (mode === 'dim') {
    for (const moduleRuntime of engine.modules) engine.setDim(moduleRuntime.meta.id, 0.2);
    engine.setColor('turbine.stage-1-blades', null);
    explodeTarget = 0.55;
    fitCamera(0.55);
  } else if (mode === 'transparent') {
    engine.setOpacity('combustor', 0.28);
    engine.setVisible('nacelle', false);
    engine.setVisible('core-casing', false);
    fitCamera();
    cameraGoal.position.sub(cameraGoal.target).multiplyScalar(0.82).add(cameraGoal.target);
  } else if (mode === 'twin') {
    if (!assets) return;
    secondary = new Engine(assets);
    secondary.root.scale.setScalar(0.5);
    secondary.root.position.set(1.5, -0.9, 1.2);
    secondary.root.rotation.y = Math.PI;
    scene.add(secondary.root);
    for (const id of ['nacelle', 'core-casing', 'fan-cowl']) secondary.setOpacity(id, 0.12);
    const secondTurbine = secondary.modules.find(m => m.meta.id === 'turbine');
    if (secondTurbine) {
      for (const component of secondTurbine.components) {
        if (component.meta.id !== 'turbine.stage-1-blades') secondary.setOpacity(component.meta.id, 0.14);
      }
    }
    secondary.setColor(secondary.listParts('turbine.stage-1-blades').slice(0, 30), '#e03b2f');
    const box = new THREE.Box3().setFromObject(engine.root).union(new THREE.Box3().setFromObject(secondary.root));
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const vertical = THREE.MathUtils.degToRad(camera.fov) / 2;
    const horizontal = Math.atan(Math.tan(vertical) * camera.aspect);
    const distance = Math.max(size.y / 2 / Math.tan(vertical), Math.hypot(size.x, size.z) / 2 / Math.tan(horizontal)) * 1.1;
    cameraGoal.target.copy(center);
    cameraGoal.position.copy(center).addScaledVector(new THREE.Vector3(0.7, 0.35, 0.85).normalize(), distance);
    cameraAnimating = true;
  } else if (mode === 'hero') {
    heroStudio(engine, params);
  } else if (mode === 'hero-check') {
    const report = runHeroCheck(engine);
    (window as unknown as Record<string, unknown>).__heroCheck = report;
    document.body.dataset.heroCheck = report.ok ? 'pass' : 'fail';
    console.log(report.lines.join('\n'));
    showHeroCheck(report);
  } else if (mode === 'assemble') {
    const step = params.get('step');
    const limit = step === 'full' ? 99 : Number(step ?? 1);
    for (const component of assets?.manifest.components ?? []) {
      if (component.order > limit) engine.setVisible(component.id, false);
    }
    if (limit <= 3) {
      cameraGoal.target.set(-1.55, 0, 0);
      cameraGoal.position.set(-0.3, 1.7, 2.5);
    } else {
      fitCamera();
      cameraGoal.position.sub(cameraGoal.target).multiplyScalar(0.9).add(cameraGoal.target);
    }
    cameraAnimating = true;
  }
  const warm = Number(params.get('warm') ?? 0);
  if (warm > 0) {
    engine.update(warm, true);
    if (secondary) secondary.update(warm, true);
  }
  // Review states are captured without waiting for the camera tween.
  camera.position.copy(cameraGoal.position);
  controls.target.copy(cameraGoal.target);
  cameraAnimating = false;
  controls.update();
  if (view === 'cutaway') {
    const dy = camera.position.y - controls.target.y;
    const dz = camera.position.z - controls.target.z;
    const length = Math.hypot(dy, dz) || 1;
    clipPlane.normal.set(0, -dy / length, -dz / length);
    clipPlane.constant = 0;
  }
}

(async () => {
  try {
    assets = await loadEngineAssets('/models/turbofan.glb', '/models/turbofan-parts.json', ratio => {
      loaderText.textContent = `${t('加载中')} ${Math.round(ratio * 100)}%`;
    });
    engine = new Engine(assets);
    scene.add(engine.root);
    effects = createEffects(engine);
    buildPartsList();
    resize();
    fitCamera();
    camera.position.copy(cameraGoal.position);
    controls.target.copy(cameraGoal.target);
    cameraAnimating = false;

    const params = new URLSearchParams(location.search);
    const requestedView = params.get('view');
    applyView(requestedView === 'cutaway' || requestedView === 'explode' ? requestedView : 'assembly');
    setExplode(explodeTarget);
    applyDebug(params);
    loader.classList.add('done');
    performance.mark('engine-ready');
    setTimeout(() => loader.remove(), 600);
  } catch (error) {
    console.error(error);
    loaderText.textContent = '模型加载失败';
  }
})();

let last = performance.now();
let frames = 0, statsStart = performance.now();
function frame(now: number) {
  const delta = Math.min(0.05, (now - last) / 1000);
  last = now;

  if (engine) {
    explode += (explodeTarget - explode) * Math.min(1, delta * 5.5);
    if (Math.abs(explodeTarget - explode) > 0.0005) setExplode(explode);
    engine.update(delta, running);
    if (secondary) secondary.update(delta, running);
  }

  if (view === 'cutaway' && !isolate) {
    const dy = camera.position.y - controls.target.y;
    const dz = camera.position.z - controls.target.z;
    const length = Math.hypot(dy, dz) || 1;
    clipPlane.normal.set(0, -dy / length, -dz / length);
    clipPlane.constant = 0;
  }

  if (effects) {
    const intensity = view === 'cutaway' ? 1 : 0.85;
    effects.update(now / 1000, delta, running, intensity);
  }

  if (cameraAnimating) {
    camera.position.lerp(cameraGoal.position, Math.min(1, delta * 4.5));
    controls.target.lerp(cameraGoal.target, Math.min(1, delta * 4.5));
    if (camera.position.distanceTo(cameraGoal.position) < 0.01) cameraAnimating = false;
  }

  controls.update();
  renderer.render(scene, camera);

  frames++;
  if (now - statsStart > 1000) {
    const stats = { fps: Math.round(frames * 1000 / (now - statsStart)), calls: renderer.info.render.calls, tris: renderer.info.render.triangles };
    (window as unknown as Record<string, unknown>).__stats = stats;
    document.body.dataset.stats = JSON.stringify(stats);
    frames = 0; statsStart = now;
  }
  requestAnimationFrame(frame);
}

resize();
requestAnimationFrame(frame);
setLanguage(new URLSearchParams(location.search).get('lang') === 'en' ? 'en' : 'zh');

function bladeIdFor(value: string): string {
  return value.includes('.') ? value : `turbine.stage-1-blades.${value.padStart(3, '0')}`;
}

function applyState(mode: string, extra: Record<string, string> = {}) {
  if (!engine) return;
  renderer.toneMappingExposure = 1.12;
  key.intensity = 2.6; fill.intensity = 0.75; rim.intensity = 0.55; hemisphere.intensity = 0.5;
  key.color.set('#fff4e2'); fill.color.set('#bcd7ea');
  scene.environmentIntensity = 1;
  useStudioEnvironment(false);
  scene.environmentRotation.set(0, 0, 0);
  studioBackground = null;
  backdrop.restore();
  chrome().forEach(element => { element.style.visibility = ''; });
  engine.reset();
  for (const moduleRuntime of engine.modules) {
    for (const component of moduleRuntime.components) component.group.rotation.x = 0;
  }
  if (secondary) { scene.remove(secondary.root); secondary = null; }
  explode = 0; explodeTarget = 0;
  setExplode(0);
  applyView('assembly');
  if (effects) effects.setVisible(true);
  applyDebug(new URLSearchParams({ debug: mode, ...extra }));
}

if (import.meta.env.DEV) {
  (window as unknown as Record<string, unknown>).__app = {
    get engine() { return engine; },
    get secondary() { return secondary; },
    camera, controls, renderer, scene,
    setRunning, applyView, setExplode, select, selectPart, applyState,
    commitCamera: () => { camera.position.copy(cameraGoal.position); controls.target.copy(cameraGoal.target); cameraAnimating = false; controls.update(); },
  };
}
