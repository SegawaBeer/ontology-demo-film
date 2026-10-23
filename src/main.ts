import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { loadTurbofan, sectionOf, type SectionId, type TurbofanModel } from './model';
import { createEffects, type Effects } from './effects';
import { EngineAudio } from './audio';
import { createBackdrop, appendBackdropControl } from './backdrop';
import { renderPixelRatio, onRenderQuality, getRenderQuality, setRenderQuality, type RenderQuality } from './render-quality';
import { languageControl, setLanguage, t, onLanguage } from './i18n';
import './style.css';

type View = 'assembly' | 'cutaway' | 'explode';

const DESCRIPTIONS: Record<SectionId, string> = {
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

const EXPLODE: Record<SectionId, THREE.Vector3Tuple> = {
  fan: [2.35, 0, 0],
  'fan-cowl': [3.15, 1.05, 0],
  compressor: [1.15, 0, 0],
  combustor: [0, 0, 0],
  turbine: [-1.15, 0, 0],
  exhaust: [-2.35, 0, 0],
  nacelle: [0, 1.95, 0],
  'core-casing': [0, -1.95, 0],
  shaft: [-0.3, 0, 0],
};

const CUTAWAY_HIDDEN: SectionId[] = ['fan-cowl', 'nacelle', 'core-casing'];

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
controls.minDistance = 0.8;
controls.maxDistance = 16;
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
let model: TurbofanModel | null = null;
let effects: Effects | null = null;
const sectionMaterials = new Map<SectionId, THREE.MeshStandardMaterial[]>();

let view: View = 'assembly';
let running = false;
let explode = 0;
let explodeTarget = 0;
let selected: SectionId | null = null;
let isolate = false;
let rotorAngle = 0;

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

const partButtons = new Map<SectionId, HTMLButtonElement>();

function buildPartsList(current: TurbofanModel) {
  for (const section of current.sections) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.part = section.id;
    button.setAttribute('aria-pressed', 'false');
    button.innerHTML = `<span>${section.name}</span><small>${section.english}</small>`;
    button.onclick = () => select(section.id);
    partsList.append(button);
    partButtons.set(section.id, button);
  }
}

function setExplode(value: number) {
  explode = value;
  explodeInput.value = String(Math.round(value * 100));
  if (!model) return;
  for (const section of model.sections) {
    const offset = EXPLODE[section.id];
    section.object.position.set(offset[0] * value, offset[1] * value, offset[2] * value);
  }
  applyVisibility();
}

function applyVisibility() {
  if (!model) return;
  for (const section of model.sections) {
    const cutawayHidden = view === 'cutaway' && CUTAWAY_HIDDEN.includes(section.id);
    section.object.visible = isolate ? section.id === selected : !cutawayHidden;
    if (section.shell) section.shell.visible = isolate ? section.id === selected : view !== 'cutaway';
  }
  if (effects) effects.group.visible = !isolate && explode < 0.4;
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
  if (!model) return;
  if (next !== 'explode') {
    explodeTarget = 0;
  } else {
    explodeTarget = Number(explodeInput.value) / 100 || 1;
    explodeInput.value = String(Math.round(explodeTarget * 100));
  }
  applyVisibility();
  fitCamera(next === 'explode' ? explodeTarget : 0);
}

function highlight() {
  const dim = new THREE.Color('#0b1a22');
  for (const [id, materials] of sectionMaterials) {
    const active = selected === id;
    for (const material of materials) {
      const base = material.userData.baseColor as THREE.Color | undefined;
      if (base) material.color.copy(base);
      if (!selected) {
        material.emissive.set('#000000');
        material.emissiveIntensity = 0;
        material.envMapIntensity = 1.15;
      } else if (active) {
        material.emissive.set('#2aa6c6');
        material.emissiveIntensity = 0.38;
        material.envMapIntensity = 1.7;
      } else {
        if (base) material.color.lerp(dim, 0.62);
        material.emissive.set('#000000');
        material.emissiveIntensity = 0;
        material.envMapIntensity = 0.3;
      }
    }
  }
  for (const [id, button] of partButtons) {
    button.setAttribute('aria-pressed', String(selected === id));
  }
}

function select(id: SectionId | null, focus = true) {
  selected = id;
  if (!id) isolate = false;
  updateIsolateButton();
  highlight();
  applyVisibility();
  if (!id || !model) {
    info.hidden = true;
    if (focus) focusOn(null);
    return;
  }
  const section = model.byId.get(id);
  if (!section) return;
  info.hidden = false;
  infoTitle.textContent = t(section.name);
  infoBody.textContent = t(DESCRIPTIONS[id]);
  if (focus) focusOn(section.object);
}

function fitCamera(spread = 0) {
  if (!model) return;
  const halfWidth = Math.hypot(model.size.x / 2 + spread * 2.6, model.size.z / 2 + spread * 1.55);
  const halfHeight = model.size.y / 2 + spread * 2.15;
  const vertical = THREE.MathUtils.degToRad(camera.fov) / 2;
  const horizontal = Math.atan(Math.tan(vertical) * camera.aspect);
  const distance = Math.max(halfHeight / Math.tan(vertical), halfWidth / Math.tan(horizontal)) * 1.12;
  controls.maxDistance = Math.max(16, distance * 1.3);
  const direction = new THREE.Vector3(0.78, 0.36, 0.92).normalize();
  cameraGoal.target.set(model.center.x, model.center.y, model.center.z);
  cameraGoal.position.copy(model.center).addScaledVector(direction, distance);
  cameraAnimating = true;
}

function focusOn(object: THREE.Object3D | null) {
  if (!model) return;
  if (!object) {
    fitCamera();
    return;
  }
  const box = new THREE.Box3().setFromObject(object);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = size.length() / 2;
  const vertical = THREE.MathUtils.degToRad(camera.fov) / 2;
  const horizontal = Math.atan(Math.tan(vertical) * camera.aspect);
  const distance = Math.max(0.6, radius / Math.sin(Math.min(vertical, horizontal)) * 1.15);
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
  if (isolate) focusOn(model?.byId.get(selected)?.object ?? null);
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
  if (selected && model) {
    const section = model.byId.get(selected);
    if (section) {
      infoTitle.textContent = t(section.name);
      infoBody.textContent = t(DESCRIPTIONS[selected]);
    }
  }
});

document.querySelector('#language-host')!.append(languageControl());
appendBackdropControl(document.querySelector('#backdrop-host')!);

document.querySelectorAll<HTMLButtonElement>('#views button').forEach(button => {
  button.onclick = () => applyView(button.dataset.view as View);
});

explodeInput.oninput = () => {
  explodeTarget = Number(explodeInput.value) / 100;
};
explodeInput.onchange = () => {
  if (view !== 'explode') applyView('explode');
};

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let downX = 0, downY = 0;

canvas.addEventListener('pointerdown', event => { downX = event.clientX; downY = event.clientY; });
canvas.addEventListener('pointerup', event => {
  if (Math.hypot(event.clientX - downX, event.clientY - downY) > 6 || !model) return;
  const rect = canvas.getBoundingClientRect();
  pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObject(model.root, true);
  const visible = hits.find(hit => {
    let node: THREE.Object3D | null = hit.object;
    while (node) { if (!node.visible) return false; node = node.parent; }
    return true;
  });
  if (!visible) { select(null); return; }
  const id = sectionOf(visible.object);
  if (id) select(id);
});

function resize() {
  const width = innerWidth, height = innerHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  backdrop.resize(width * renderer.getPixelRatio(), height * renderer.getPixelRatio());
}
addEventListener('resize', resize);

(async () => {
  try {
    const params = new URLSearchParams(location.search);
    const loaded = await loadTurbofan('/models/turbofan.glb', ratio => {
      loaderText.textContent = `${t('加载中')} ${Math.round(ratio * 100)}%`;
    });
    model = loaded;
    scene.add(model.root);
    for (const section of model.sections) {
      const materials: THREE.MeshStandardMaterial[] = [];
      section.object.traverse(object => {
        const mesh = object as THREE.Mesh;
        if (!mesh.isMesh) return;
        const material = mesh.material as THREE.MeshStandardMaterial;
        if (!material || Array.isArray(material)) return;
        const clone = material.clone();
        clone.userData.baseColor = clone.color.clone();
        mesh.material = clone;
        materials.push(clone);
      });
      sectionMaterials.set(section.id, materials);
    }
    buildPartsList(model);
    effects = createEffects(model);
    scene.add(effects.group);
    resize();
    fitCamera();
    camera.position.copy(cameraGoal.position);
    controls.target.copy(cameraGoal.target);
    cameraAnimating = false;

    const requestedView = params.get('view');
    applyView(requestedView === 'cutaway' || requestedView === 'explode' ? requestedView : 'assembly');
    setExplode(explodeTarget);
    const requestedSection = params.get('section') as SectionId | null;
    if (requestedSection && model.byId.has(requestedSection)) select(requestedSection, false);
    loader.classList.add('done');
    setTimeout(() => loader.remove(), 600);
  } catch (error) {
    console.error(error);
    loaderText.textContent = '模型加载失败';
  }
})();

let last = performance.now();
function frame(now: number) {
  const delta = Math.min(0.05, (now - last) / 1000);
  last = now;

  if (model) {
    explode += (explodeTarget - explode) * Math.min(1, delta * 5.5);
    if (Math.abs(explodeTarget - explode) > 0.0005) setExplode(explode);

    if (running) {
      rotorAngle += delta * 9.5;
      for (const rotor of model.rotors) rotor.rotation.x = -rotorAngle;
    }
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
  requestAnimationFrame(frame);
}

resize();
requestAnimationFrame(frame);

setLanguage(new URLSearchParams(location.search).get('lang') === 'en' ? 'en' : 'zh');
