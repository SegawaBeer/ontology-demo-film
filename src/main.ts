import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { loadEngineAssets, Engine, type EngineAssets } from './model';
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

scene.add(new THREE.HemisphereLight('#dfeaf2', '#0a1418', 0.5));
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

new RGBELoader().load('/environment/poly_haven_studio_1k.hdr', texture => {
  const pmrem = new THREE.PMREMGenerator(renderer);
  texture.mapping = THREE.EquirectangularReflectionMapping;
  scene.environment = pmrem.fromEquirectangular(texture).texture;
  texture.dispose();
  pmrem.dispose();
});

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
}
addEventListener('resize', resize);

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
    const cut = Number(params.get('cut') ?? 0);
    const coat = Number(params.get('coat') ?? 0);
    const rows = params.get('rows');
    const zoom = Number(params.get('zoom') ?? 1);
    const pose = params.get('pose');
    const heroRows = ['film-le-1', 'film-le-2', 'film-le-3', 'film-le-4',
      'film-ps-1', 'film-ps-2', 'film-ss-1', 'slot-te']
      .map(id => `turbine.hero-blade.${id}`);
    if (pose) {
      engine.hero.show(true);
      engine.hero.setCutaway(cut);
      engine.hero.setCoatings(coat);
      const poseResult = engine.hero.poseFor(bladeIdFor(pose));
      engine.setVisible(bladeIdFor(pose), false);
      if (poseResult) {
        engine.setVisible('nacelle', false);
        engine.setVisible('core-casing', false);
        engine.setVisible('compressor', false);
        engine.setVisible('turbine.band', false);
        engine.setVisible('turbine.inner-cone', false);
        const target = new THREE.Vector3(...poseResult.position);
        cameraGoal.target.copy(target);
        cameraGoal.position.copy(target)
          .add(new THREE.Vector3(-0.45, 0.55, 0.7).normalize().multiplyScalar(0.85 * zoom));
        cameraAnimating = true;
      }
    } else {
      for (const moduleRuntime of engine.modules) {
        for (const component of moduleRuntime.components) {
          engine.setVisible(component.meta.id, component.meta.id === 'turbine.hero-blade');
        }
      }
      engine.hero.show(true);
      engine.hero.setCutaway(cut);
      engine.hero.setCoatings(coat);
      const angle = params.get('angle') ?? 'face';
      cameraGoal.target.set(0, 0.075, 0.02);
      const offset = angle === 'leading' ? new THREE.Vector3(0.37, 0.06, 0.26)
        : angle === 'oblique' ? new THREE.Vector3(-0.14, 0.3, 0.3)
        : new THREE.Vector3(0.24, 0.08, -0.34);
      cameraGoal.position.copy(cameraGoal.target).addScaledVector(offset, zoom * 1.45);
      cameraAnimating = true;
    }
    if (rows === 'all') engine.setColor(heroRows, '#39d0ff');
    else if (rows === 'le') engine.setColor(heroRows.slice(0, 4), '#39d0ff');
    if (params.get('ceramic') === '1') engine.setColor('turbine.hero-blade.coat-ysz', '#e03b2f');
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
