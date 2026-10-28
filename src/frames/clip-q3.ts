// Timed playback for the question-three clip (script v1.3, 1:04–1:26).
// Everything is a pure function of t, so the exporter can seek frame by frame
// and a browser preview can scrub or loop without drift.
import * as THREE from 'three';
import { renderGraph } from './graph';
import { fleetBlocks, type GraphState } from './data';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { createModelView, type Theme, type Pose, type ModelView } from './scene';
import type { Engine } from '../model';
import { typedTimes } from './timing';
import { createHeroBlade, HERO_COMPONENT } from '../hero-blade';

export const DURATION = 22;

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const seg = (t: number, a: number, b: number) => clamp((t - a) / (b - a));
const ease = (p: number) => p * p * p * (p * (p * 6 - 15) + 10);
const easeOut = (p: number) => 1 - (1 - p) ** 3;
// Deterministic jitter so a re-render of the same frame is identical.
const noise = (n: number) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
// Bump that rises to 1 and falls back to 0 inside [a, b].
const bump = (t: number, a: number, b: number) => { const p = seg(t, a, b); return p <= 0 || p >= 1 ? 0 : Math.sin(Math.PI * p); };

const RING = 'turbine.stage-1-blades';
const slot = (n: number) => `${RING}.${String(((n - 1 + 100) % 100) + 1).padStart(3, '0')}`;
const range = (from: number, count: number) => Array.from({ length: count }, (_, i) => from + i);
const hit7 = range(9, 16);
const hit3 = range(2, 30);

function fleetOffset(key: string) {
  let offset = 0;
  for (const block of fleetBlocks) {
    if (block.key === key) return offset;
    offset += block.count;
  }
  return 0;
}
const hitIndex7 = hit7.map(n => fleetOffset('7') + n - 1);
const hitIndex3 = hit3.map(n => fleetOffset('3') + n - 1);
const allHits = [...hitIndex3, ...hitIndex7].sort((a, b) => a - b);

// The scan through 1,016 blades is uneven on purpose: bursts and short stalls.
const scanKeys: [number, number][] = [
  [7.4, 0], [7.85, 118], [8.05, 126], [8.55, 290], [8.95, 402], [9.12, 409], [9.6, 612], [9.78, 628], [10.15, 812], [10.6, 1016],
];
function scanAt(t: number) {
  if (t <= scanKeys[0][0]) return 0;
  for (let i = 1; i < scanKeys.length; i++) {
    const [t1, v1] = scanKeys[i], [t0, v0] = scanKeys[i - 1];
    if (t <= t1) return Math.round(v0 + (v1 - v0) * (t - t0) / (t1 - t0));
  }
  return 1016;
}
function timeOfIndex(index: number) {
  for (let i = 1; i < scanKeys.length; i++) {
    const [t1, v1] = scanKeys[i], [t0, v0] = scanKeys[i - 1];
    if (index < v1) return t0 + (t1 - t0) * (index - v0) / Math.max(1, v1 - v0);
  }
  return scanKeys[scanKeys.length - 1][0];
}

// Numbers flicker through values before landing, like a count still coming in.
function tick(final: number, t: number, start: number, dur = 0.45) {
  const p = seg(t, start, start + dur);
  if (p >= 1) return final;
  const frame = Math.floor(t * 60);
  return Math.max(0, Math.min(final, Math.round(final * easeOut(p) + (noise(frame + final) - 0.5) * final * 0.6 * (1 - p))));
}

// Characters typed by t: uneven keystrokes, a longer beat after punctuation.
function typed(text: string, t: number, start: number, perChar: number, seed: number) {
  let clock = start, count = 0;
  for (const ch of text) {
    clock += perChar * (0.55 + 0.9 * noise(seed + count)) * ('，。？、·'.includes(ch) ? 2.2 : 1);
    if (t < clock) break;
    count++;
  }
  return [...text].slice(0, count).join('');
}
const typingEnd = (text: string, start: number, perChar: number, seed: number) => {
  let clock = start, i = 0;
  for (const ch of text) { clock += perChar * (0.55 + 0.9 * noise(seed + i)) * ('，。？、·'.includes(ch) ? 2.2 : 1); i++; }
  return clock;
};

const appear = (t: number, at: number, dur = 0.32) => {
  const p = ease(seg(t, at, at + dur));
  return `opacity:${p.toFixed(3)};transform:translateY(${((1 - p) * 8).toFixed(2)}px)`;
};

const Q3_ASK = '这批粉末都用到哪儿了？';
const Q3_ASK_AT = 1.8;
const FOLLOW_ASK = '7 号上的 16 枚拆下停用。3 号发动机还能继续飞吗？';
const FOLLOW_AT = 14.95;
const NEW_ANSWER = '暂不能上试车台 · 等待 16 枚叶片';

function hitsBefore(scan: number, list = allHits) { return list.filter(i => i < scan).length; }

function dialogHTML(t: number) {
  const blinkOff = Math.floor(t * 2.4) % 2 === 1;
  const cursor = (on: boolean) => on ? ` live${blinkOff ? ' blink-off' : ''}` : '';

  const q1 = `<div class="turn past"><div class="meta"><b>研发</b><span>02:07</span></div>
    <p class="ask">第一级涡轮叶片的冷却孔缩小 0.1 毫米，会影响到哪些东西？</p>
    <p class="answer">在制叶片 300 枚 · 在途铸件 200 件 · 涉及发动机 5 台</p></div>`;

  // Question two rewrites itself the moment the stop-use action lands.
  const c = t - 19.0;
  let q2: string;
  if (c < 0) {
    q2 = `<div class="turn past"><div class="meta"><b>总装</b><span>02:11</span></div>
      <p class="ask">7 号发动机明早 9 点能按时上试车台吗？</p>
      <p class="answer green"><span>可以按时上试车台</span><span class="state">09:00</span></p></div>`;
  } else {
    const strike = ease(seg(c, 0.1, 0.45));
    const now = typed(NEW_ANSWER, c, 0.45, 0.035, 71);
    q2 = `<div class="turn past changing" style="opacity:${(0.5 + 0.5 * ease(seg(c, 0, 0.25))).toFixed(3)}">
      <span class="bar" style="transform:scaleY(${ease(seg(c, 0, 0.25)).toFixed(3)})"></span>
      <div class="meta"><b>总装</b><span>02:11</span><span class="flag" style="opacity:${ease(seg(c, 0.05, 0.3)).toFixed(3)}">自动更新 · 02:17</span></div>
      <p class="ask">7 号发动机明早 9 点能按时上试车台吗？</p>
      <p class="answer"><span class="was" style="background-size:${(strike * 100).toFixed(1)}% 1px">可以按时上试车台 09:00</span><span class="now">${now}</span></p></div>`;
  }

  // Layer A: the alert and question three as it is being answered.
  const askText = typed(Q3_ASK, t, Q3_ASK_AT, 0.13, 13);
  const askDone = askText.length === [...Q3_ASK].length;
  const scan = scanAt(t);
  const found = hitsBefore(scan);
  const steps: string[] = [];
  if (t >= 5.0) steps.push(`<div class="step" style="${appear(t, 5.0)}"><span class="n">01</span><span class="line">喷涂工单 <em>${tick(2, t, 5.0, 0.25)}</em> 张</span></div>`);
  if (t >= 7.35) {
    const scanning = scan < 1016 ? `<span class="scan">核对 ${scan.toLocaleString('en-US')} / 1,016</span>` : '';
    steps.push(`<div class="step" style="${appear(t, 7.35)}"><span class="n">02</span><span class="line">第一级涡轮叶片 <em class="red">${found}</em> 枚${scanning}</span></div>`);
  }
  if (t >= 11.55) {
    const second = t >= 11.85
      ? `<br><span style="${appear(t, 11.85)};display:inline-block">3 号发动机 <em class="red">${tick(30, t, 11.85, 0.3)}</em> 枚 · 在役</span>`
      : '';
    steps.push(`<div class="step" style="${appear(t, 11.55)}"><span class="n">03</span><span class="line">7 号发动机 <em class="red">${tick(16, t, 11.55, 0.3)}</em> 枚 · 已装机，未试车${second}</span></div>`);
  }
  const liveStep = t < 13.2 && steps.length ? steps.length - 1 : -1;
  const stepsHTML = steps.map((s, i) => i === liveStep ? s.replace('class="step"', `class="step${cursor(true)}"`) : s).join('');
  const alert = t >= 0.6
    ? `<div class="alert" style="${appear(t, 0.6, 0.35)}"><div class="meta"><b>质量</b><span>02:15</span><span>自动提示</span></div>
        <p>涂层检测：批次 YSZ-2410 粉末杂质超标</p><small>CT-1024-03 · 实测 0.42% / 上限 0.30%</small></div>`
    : '';
  const q3 = t >= Q3_ASK_AT - 0.15
    ? `<div class="turn" style="${appear(t, Q3_ASK_AT - 0.15, 0.2)}"><div class="meta"><b>质量</b><span>02:15</span></div>
        <p class="ask${!askDone || (t < 5.0) ? cursorClass(blinkOff, askDone) : ''}">${askText}</p>${steps.length ? `<div class="steps">${stepsHTML}</div>` : ''}</div>`
    : '';

  // Layer B: question three folded away, the follow-up and its actions.
  const followText = typed(FOLLOW_ASK, t, FOLLOW_AT, 0.055, 29);
  const followDone = t >= typingEnd(FOLLOW_ASK, FOLLOW_AT, 0.055, 29);
  const actions: string[] = [];
  if (t >= 16.9) actions.push(`<div class="step" style="${appear(t, 16.9)}"><span class="n">01</span><span class="line">已停用 <em class="red">${tick(16, t, 16.9, 0.3)}</em> 枚 · 批次 YSZ-2410 已冻结</span></div>`);
  if (t >= 17.7) actions.push(`<div class="step" style="${appear(t, 17.7)}"><span class="n">02</span><span class="line">3 号发动机按设计余量可继续飞行<br>孔探间隔 <em>400</em> → <em class="amber">${t < 17.95 ? 400 : tick(200, t, 17.95, 0.3)}</em> 循环</span></div>`);
  if (t >= 18.5) actions.push(`<div class="step" style="${appear(t, 18.5)}"><span class="n">03</span><span class="line">2027 年 3 月进厂时更换 <em>30</em> 枚 · 已通知澜川航空</span></div>`);
  const liveAction = actions.length ? actions.length - 1 : -1;
  const actionsHTML = actions.map((s, i) => i === liveAction ? s.replace('class="step"', `class="step${cursor(true)}"`) : s).join('');
  const q3Past = `<div class="turn past"><div class="meta"><b>质量</b><span>02:15</span></div>
    <p class="ask">这批粉末都用到哪儿了？</p>
    <p class="answer">第一级涡轮叶片 46 枚 · 7 号发动机 16 枚 · 3 号发动机 30 枚</p></div>`;
  const follow = t >= FOLLOW_AT - 0.2
    ? `<div class="turn" style="${appear(t, FOLLOW_AT - 0.2, 0.2)}"><div class="meta"><b>质量</b><span>02:17</span></div>
        <p class="ask${!followDone || t < 16.9 ? cursorClass(blinkOff, followDone) : ''}">${followText}</p>${actions.length ? `<div class="steps">${actionsHTML}</div>` : ''}</div>`
    : '';

  const swap = ease(seg(t, 14.45, 14.85));
  const layers = `<div class="swap">
    <div class="layer" style="opacity:${(1 - swap).toFixed(3)}">${alert}${q3}</div>
    <div class="layer" style="opacity:${swap.toFixed(3)}">${q3Past}${follow}</div></div>`;

  const [left, right] = traceAt(t, scan);
  return `<div class="dialog"><header class="col-head"><span>提问</span><span>4 个部门 · 同一套对象</span></header>
    <div class="turns">${q1}${q2}${layers}</div>
    <div class="trace"><span>${left}</span><span class="spin">${right}</span></div></div>`;
}

function cursorClass(blinkOff: boolean, done: boolean) {
  return done && blinkOff ? ' typing blink-off' : ' typing';
}

function traceAt(t: number, scan: number): [string, string] {
  if (t < 1.0) return ['就绪', ''];
  if (t < 4.2) return ['1 条自动提示 · 涂层检测 CT-1024-03', ''];
  if (t < 12.4) {
    const objects = 1 + Number(t > 5.0) + Number(t > 6.4) + Number(t > 7.4) + Number(t > 11.5) + Number(t > 11.8);
    const rels = Math.round(2140 * (0.05 * seg(t, 4.2, 7.4) + 0.88 * scan / 1016 + 0.07 * seg(t, 10.6, 12.4)));
    const elapsed = 0.8 * (0.25 * seg(t, 4.2, 7.4) + 0.6 * scan / 1016 + 0.15 * seg(t, 10.6, 12.4));
    return [`检索中 · ${objects} 类对象 · ${rels.toLocaleString('en-US')} 条关系`, `${elapsed.toFixed(2)} 秒`];
  }
  if (t < 16.9) return ['已检索 1,016 枚叶片 · 2,140 条关系', '0.8 秒'];
  if (t < 19.0) {
    const updated = Math.round(20 * seg(t, 16.9, 19.0));
    return [`执行中 · 停用、冻结、调整检查计划 · 已更新 ${updated} 个对象`, `${(1.1 * seg(t, 16.9, 19.0)).toFixed(2)} 秒`];
  }
  return ['已执行 2 个动作 · 更新 20 个对象 · 新建 1 个', '1.1 秒'];
}

// Query path on the graph: each hop draws over [a, b] and stays lit after.
const hops: { from: string; to: string; a: number; b: number }[] = [
  { from: 'coat', to: 'powder', a: 3.75, b: 4.2 },
  { from: 'powder', to: 'spray', a: 4.55, b: 5.0 },
  { from: 'spray', to: 'blade', a: 5.35, b: 6.0 },
  { from: 'blade', to: 'c-t1', a: 11.0, b: 11.16 },
  { from: 'c-t1', to: 'm-turb', a: 11.16, b: 11.3 },
  { from: 'm-turb', to: 'e7', a: 11.3, b: 11.5 },
  { from: 'blade', to: 'e3', a: 11.3, b: 11.85 },
];
// Neighbours that get checked and dropped: they flash, then fall back.
const probes: [string, number][] = [
  ['supplier', 4.25], ['design', 6.05], ['drill', 6.12], ['std', 6.2], ['mwo', 6.28], ['insp', 6.36], ['stock', 6.44], ['po', 6.5],
];
const litAt: [string, number][] = [
  ['coat', 0.7], ['powder', 4.2], ['spray', 5.0], ['blade', 6.0], ['c-t1', 11.16], ['m-turb', 11.3], ['e7', 11.5], ['e3', 11.85], ['awo', 17.2],
];

function graphAt(t: number): GraphState {
  const lit = litAt.filter(([, at]) => t >= at).map(([id]) => id);
  const litEdges = hops.filter(h => t >= h.b).map(h => [h.from, h.to] as [string, string]);
  const drawing = hops.filter(h => t > h.a && t < h.b).map(h => ({ from: h.from, to: h.to, progress: ease(seg(t, h.a, h.b)) }));
  const nodeAlpha: Record<string, number> = {};
  for (const [id, at] of probes) {
    const v = bump(t, at, at + 0.34);
    if (v > 0) nodeAlpha[id] = 0.22 + 0.7 * v;
  }
  const pulse: Record<string, number> = {};
  const pulses: [string, number, number][] = [
    ['coat', 0.6, 1.4], ['powder', 4.2, 4.9], ['e7', 11.5, 12.2], ['e3', 11.85, 12.55],
    ['disposal', 17.0, 17.8], ['awo', 17.2, 17.9], ['e3', 17.7, 18.4], ['e7', 19.0, 19.8],
  ];
  for (const [id, a, b] of pulses) if (t > a && t < b) pulse[id] = seg(t, a, b);

  const status: GraphState['status'] = {};
  if (t >= 0.7) status.coat = 'red';
  if (t >= 4.2) status.powder = 'red';
  if (t >= 11.5) status.e7 = 'red';
  if (t >= 11.85) status.e3 = t >= 17.7 ? 'amber' : 'red';
  if (t >= 17.2) status.awo = 'amber';
  if (t >= 16.9) status.disposal = 'red';

  const chip: GraphState['chip'] = {};
  if (t >= 0.8) chip.coat = { text: 'CT-1024-03', tone: 'red' };
  if (t >= 4.2) chip.powder = { text: t >= 16.95 ? 'YSZ-2410 · 已冻结' : 'YSZ-2410', tone: 'red' };
  if (t >= 5.0 && t < 16.9) chip.spray = { text: 'PT-0817 · PT-0903' };
  // The engine chips sit clear of the lit links below their nodes (主时间轴一 12.2).
  if (t >= 11.55) chip.e7 = { text: t >= 19.0 ? '暂不能上试车台' : `${tick(16, t, 11.55, 0.3)} 枚`, tone: 'red', dx: -4, anchor: 'end' };
  if (t >= 11.85) chip.e3 = t >= 17.7 ? { text: '孔探间隔减半', tone: 'amber', dx: 8, dy: 6 } : { text: `${tick(30, t, 11.85, 0.3)} 枚`, tone: 'red' };
  if (t >= 17.2) chip.awo = { text: '+ 更换 16 枚叶片', tone: 'amber' };
  if (t >= 17.1) chip.disposal = { text: 'CZ-1024-01', tone: 'red' };

  const timing: GraphState['timing'] = [];
  if (t >= 4.2 && t < 16.9) timing.push({ text: '9 ms', x: 196, y: 920 });
  if (t >= 5.0 && t < 16.9) timing.push({ text: '31 ms', x: 446, y: 842 });
  if (t >= 11.85 && t < 16.9) timing.push({ text: '0.42 s', x: 350, y: 300 });

  const scan = scanAt(t);
  const dotsIn = ease(seg(t, 6.85, 7.3)) * (1 - ease(seg(t, 14.4, 14.9)));
  const found = hitsBefore(scan);
  const dotCaption = scan < 1016
    ? `逐枚核对 · ${scan.toLocaleString('en-US')} / 1,016 · <tspan fill="var(--red)" font-weight="600">${found}</tspan> 枚命中`
    : '1,016 枚逐一核对 · <tspan fill="var(--red)" font-weight="600">46</tspan> 枚命中';

  const dimLevel = 1 - 0.78 * ease(seg(t, 0.9, 1.7));
  return {
    focus: true, dimLevel, lit, litEdges, drawing, nodeAlpha, pulse, status, chip, timing,
    dots: dotsIn > 0 ? { hits: allHits, caption: dotCaption, scan, appear: dotsIn } : undefined,
    spawned: t >= 16.9 ? [{
      node: { id: 'disposal', x: 186, y: 1040, label: '处置单', kind: 'biz', group: 'qa', anchor: 'right' },
      edges: [['disposal', 'blade', 0.22]],
      appear: ease(seg(t, 16.9, 17.3)),
    }] : undefined,
  };
}

// Close-up inset: the detailed cooled blade in its own small scene, drawn
// into a rectangle of the same canvas after the main view. It opens with a
// top-down wipe, the four coating layers lift off, and the ceramic one turns red.
const INSET = { x: 392, y: 118, w: 300, h: 430 };
const CERAMIC = '#aeb0aa';

async function createInset(renderer: THREE.WebGLRenderer, theme: Theme) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(theme === 'dark' ? '#121a22' : '#f6f7f5');
  const hdr = await new RGBELoader().loadAsync('/environment/studio_kontrast_02_1k.hdr');
  const pmrem = new THREE.PMREMGenerator(renderer);
  hdr.mapping = THREE.EquirectangularReflectionMapping;
  scene.environment = pmrem.fromEquirectangular(hdr).texture;
  hdr.dispose();
  pmrem.dispose();
  scene.environmentIntensity = 0.85;
  scene.add(new THREE.HemisphereLight('#eef3f6', '#1a2026', 0.45));
  const key = new THREE.DirectionalLight('#fff4e6', 1.3);
  key.position.set(-4, 8, 6);
  scene.add(key);
  const rim = new THREE.DirectionalLight('#cfe3ef', 0.55);
  rim.position.set(5, 3, -4);
  scene.add(rim);

  const hero = createHeroBlade();
  const tilt = new THREE.Group();
  tilt.rotation.set(-0.06, -0.12, -0.13);
  tilt.add(hero.root);
  scene.add(tilt);
  tilt.updateMatrixWorld(true);

  const camera = new THREE.PerspectiveCamera(28, INSET.w / INSET.h, 0.1, 100);
  const box = new THREE.Box3(new THREE.Vector3(-0.95, -0.65, -0.4), new THREE.Vector3(2.95, 4.2, 1.3));
  const corners: THREE.Vector3[] = [];
  for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) corners.push(new THREE.Vector3(x, y, z).applyMatrix4(tilt.matrixWorld));
  const target = box.getCenter(new THREE.Vector3()).applyMatrix4(tilt.matrixWorld);
  const dir = new THREE.Vector3(0.18, 0.2, 1).normalize();
  let distance = 12;
  for (let i = 0; i < 6; i++) {
    camera.position.copy(target).addScaledVector(dir, distance);
    camera.lookAt(target);
    camera.updateMatrixWorld();
    let ex = 0, ey = 0;
    for (const c of corners) { const q = c.clone().project(camera); ex = Math.max(ex, Math.abs(q.x)); ey = Math.max(ey, Math.abs(q.y)); }
    distance *= Math.max(ex / 0.86, ey / 0.86);
  }
  camera.position.copy(target).addScaledVector(dir, distance);
  camera.lookAt(target);
  camera.updateMatrixWorld();

  const ceramicId = `${HERO_COMPONENT}.coat-ysz`;
  const red = new THREE.Color(theme === 'dark' ? '#ff4a3a' : '#e0362a');
  // Top of the separated ceramic slab, in blade units (reference rest position).
  const ceramicTop = new THREE.Vector3(1.12 + 3 * 0.46, 2.44 + 0.5, 0.22 + 3 * 0.23);

  function draw(reveal: number, coat: number, redness: number) {
    hero.setCoatings(coat);
    hero.setColor(ceramicId, redness > 0 ? new THREE.Color(CERAMIC).lerp(red, redness) : null);
    const hh = INSET.h * reveal;
    if (hh < 1) return;
    renderer.setScissorTest(true);
    renderer.setScissor(INSET.x, 1080 - INSET.y - hh, INSET.w, hh);
    renderer.setViewport(INSET.x, 1080 - INSET.y - INSET.h, INSET.w, INSET.h);
    renderer.render(scene, camera);
    renderer.setScissorTest(false);
    renderer.setViewport(0, 0, 720, 1080);
  }

  function ceramicOnScreen() {
    const q = ceramicTop.clone().applyMatrix4(tilt.matrixWorld).project(camera);
    return { x: INSET.x + (q.x * 0.5 + 0.5) * INSET.w, y: INSET.y + (-q.y * 0.5 + 0.5) * INSET.h };
  }

  return { draw, ceramicOnScreen };
}

function insetOverlay(t: number, anchor: { x: number; y: number }, ceramic: { x: number; y: number }) {
  const open = ease(seg(t, 5.2, 5.55)) * (1 - ease(seg(t, 6.95, 7.25)));
  if (open <= 0) return { svg: '', html: '', reveal: 0 };
  const { x, y, w, h } = INSET;
  const hh = h * open;
  const redness = ease(seg(t, 6.25, 6.5));
  const svg = `<g>
    <path d="M${anchor.x} ${anchor.y} L${x} ${y + hh}" stroke="var(--lit)" stroke-width="1" fill="none" opacity="${(0.8 * open).toFixed(3)}"/>
    <circle cx="${anchor.x}" cy="${anchor.y}" r="2.5" fill="var(--lit)" opacity="${open.toFixed(3)}"/>
    <rect x="${x - 0.5}" y="${y - 0.5}" width="${w + 1}" height="${hh + 1}" fill="none" stroke="var(--node-ring)" stroke-width="1"/>
    ${open > 0.98 && redness > 0 ? `<path d="M${ceramic.x} ${ceramic.y} V${ceramic.y - 22} H${x + w - 14}" stroke="var(--red)" stroke-width="1" fill="none" opacity="${redness.toFixed(3)}"/>` : ''}
  </g>`;
  const label = open > 0.6
    ? `<div class="inset-label" style="left:${x}px;top:${y - 26}px;opacity:${ease(seg(open, 0.6, 1)).toFixed(3)}"><span>第一级涡轮叶片 · 放大</span><span>涂层分层</span></div>`
    : '';
  const ceramicLabel = open > 0.98 && redness > 0
    ? `<div class="inset-tag" style="left:${x + w - 14}px;top:${ceramic.y - 64}px;opacity:${redness.toFixed(3)}"><b>陶瓷热障层</b><span>YSZ-2410</span></div>`
    : '';
  return { svg, html: label + ceramicLabel, reveal: open };
}

/**
 * What frame=film hands over so this clip draws into the page it already has:
 * its one view, its 7 号发动机, its model caption and a 720-column projection.
 * `ghost7` and `cut7` stand in for setGhost and cutaway on that engine
 * (everything but the first-stage ring and disk).
 */
export type ClipHost = {
  view: ModelView; e7: Engine; caption: HTMLElement;
  project: (world: THREE.Vector3) => { x: number; y: number };
  ghost7: (amount: number) => void; cut7: (amount: number) => void;
};

export async function mountClip(theme: Theme, host?: ClipHost) {
  const dialogRoot = document.querySelector<HTMLElement>('#dialog')!;
  const graphRoot = document.querySelector<SVGSVGElement>('#graph')!;
  const overlay = document.querySelector<SVGSVGElement>('#callouts')!;
  const labels = document.querySelector<HTMLElement>('#callout-labels')!;
  const caption = host?.caption ?? document.createElement('div');
  if (!host) {
    caption.className = 'model-caption';
    document.querySelector('.col-model')!.append(caption);
  }
  overlay.setAttribute('viewBox', '0 0 720 1080');

  const ink = theme === 'dark'
    ? { red: '#ff4a3a', amber: '#f0a93a', ring: '#c9d2d8', probe: '#9fd6f0' }
    : { red: '#e0362a', amber: '#d98a12', ring: '#9aa6af', probe: '#1c5fb8' };
  const view = host?.view ?? await createModelView(document.querySelector('#model')!, theme);
  const inset = await createInset(view.renderer, theme);
  const shell = { solid: [RING, 'turbine.stage-1-disk'] };
  const e7 = host?.e7 ?? view.addEngine({ ...shell, ghostAmount: 0 }, new THREE.Vector3(0, 1.05, 0), 1);
  const e3 = view.addEngine(shell, new THREE.Vector3(0.5, -1.25, 0.35), 0.6);
  for (const engine of host ? [e3] : [e7, e3]) engine.setColor(engine.listParts(RING), ink.ring);
  const project = host?.project ?? view.project;
  const ghost7 = host?.ghost7 ?? ((a: number) => view.setGhost(e7, a));
  const cut7 = host?.cut7 ?? ((a: number) => view.cutaway(e7, a));
  e3.setColor(hit3.map(slot), ink.red);

  const dir = new THREE.Vector3(-0.88, 0.3, 0.42);
  const P0 = view.fit([e7], dir, { x: 0.9, y: 0.66 }, new THREE.Vector2(-0.16, 0.1));
  const P2 = view.fit([e7, e3], dir, { x: 0.92, y: 0.84 }, new THREE.Vector2(-0.2, -0.02));
  e7.root.updateMatrixWorld(true);
  const ringCenter = new THREE.Vector3(-1.355, 0, 0).applyMatrix4(e7.root.matrixWorld);
  const P1 = {
    target: P0.target.clone().lerp(ringCenter, 0.82),
    position: new THREE.Vector3(),
  };
  P1.position.copy(P1.target).add(P0.position.clone().sub(P0.target).multiplyScalar(0.5));
  const ringGroup = (engine: typeof e7) => engine.modules.flatMap(m => m.components).find(c => c.meta.id === RING)!.group;
  const rotorGroups = e3.modules.flatMap(m => m.components).filter(c => c.rotor).map(c => c.group);
  const bladeOut = hit7.map((n, i) => {
    const c = new THREE.Vector3(...e7.getPart(slot(n))!.center);
    return { id: slot(n), center: c, dir: new THREE.Vector3(0, c.y, c.z).normalize(), at: 16.9 + i * 0.04 + noise(i + 5) * 0.06 };
  });
  const COUPON_BLADE = slot(hit7[7]);

  function cameraAt(t: number): Pose {
    const p1 = ease(seg(t, 4.9, 5.7)) * (1 - ease(seg(t, 6.9, 7.6)));
    const p2 = ease(seg(t, 11.1, 12.3));
    const target = P0.target.clone().lerp(P2.target, p2).lerp(P1.target, p1);
    const position = P0.position.clone().lerp(P2.position, p2).lerp(P1.position, p1);
    const offset = position.sub(target).applyAxisAngle(new THREE.Vector3(0, 1, 0), 0.03 * Math.sin(t * 0.33) - 0.015 * t / DURATION);
    return { target, position: target.clone().add(offset) };
  }

  function partOnScreen(engine: typeof e7, id: string, extra?: THREE.Vector3) {
    const meta = engine.getPart(id)!;
    const local = new THREE.Vector3(...meta.center);
    if (extra) return project(local.add(extra).applyMatrix4(engine.root.matrixWorld));
    return project(local.applyMatrix4(ringGroup(engine).matrixWorld));
  }
  const clusterOnScreen = (engine: typeof e7, ids: string[], extras?: THREE.Vector3[]) => {
    const pts = ids.map((id, i) => partOnScreen(engine, id, extras?.[i]));
    return { x: pts.reduce((s, p) => s + p.x, 0) / pts.length, y: pts.reduce((s, p) => s + p.y, 0) / pts.length };
  };

  function tagHTML(p: { x: number; y: number }, tone: string, html: string, alpha: number) {
    const lx = 556;
    return {
      svg: `<g opacity="${alpha.toFixed(3)}"><circle cx="${p.x}" cy="${p.y}" r="2.5" fill="var(--${tone})"/>
        <path d="M${p.x} ${p.y} L${lx - 14} ${p.y}" fill="none" stroke="var(--${tone})" stroke-width="1" opacity="0.8"/></g>`,
      html: `<div class="tag tone-${tone}" style="left:${lx}px;top:${p.y}px;opacity:${alpha.toFixed(3)}">${html}</div>`,
    };
  }

  let moved = false;
  function seek(t: number) {
    t = clamp(t, 0, DURATION);
    // Model state
    ghost7(ease(seg(t, 1.0, 2.6)));
    e3.root.visible = t >= 11.3;
    view.setSweep(e3, t >= 12.4 ? null : THREE.MathUtils.lerp(-0.75, 1.95, ease(seg(t, 11.3, 12.4))));
    for (const g of rotorGroups) g.rotation.x = -0.07 * t;
    const red7 = new THREE.Color(ink.red), ring = new THREE.Color(ink.ring), probe = new THREE.Color(ink.probe);
    hit7.forEach((n, i) => {
      const at = timeOfIndex(hitIndex7[i]);
      const c = ring.clone().lerp(red7, ease(seg(t, at, at + 0.12)));
      if (slot(n) === COUPON_BLADE) c.lerp(probe, bump(t, 5.1, 7.1) * 0.85);
      e7.setColor(slot(n), c);
    });
    const amber = ease(seg(t, 17.7, 18.2));
    e3.setColor(hit3.map(slot), new THREE.Color(ink.red).lerp(new THREE.Color(ink.amber), amber));
    const extras = bladeOut.map(b => {
      const offset = b.dir.clone().multiplyScalar(0.5 * ease(seg(t, b.at, b.at + 0.7)));
      // In frame=film the blades are always placed (they are promoted from the start there).
      if (t >= 16.9 || moved || host) e7.setTransform(b.id, { position: [offset.x, offset.y, offset.z] });
      return offset;
    });
    moved = t >= 16.9;

    view.applyPose(cameraAt(t));
    cut7(ease(seg(t, 1.2, 2.8)));
    view.cutaway(e3, 1);
    view.render();
    const zoom = insetOverlay(t, partOnScreen(e7, COUPON_BLADE), inset.ceramicOnScreen());
    inset.draw(zoom.reveal, ease(seg(t, 5.6, 6.25)), ease(seg(t, 6.25, 6.5)));

    // Overlays
    let svg = '', html = '';
    svg += zoom.svg; html += zoom.html;
    const tag7 = ease(seg(t, 11.55, 11.9));
    if (tag7 > 0) {
      const extracted = t >= 16.9;
      const p = extracted ? clusterOnScreen(e7, hit7.map(slot), extras) : clusterOnScreen(e7, hit7.map(slot));
      const body = extracted && t >= 17.3
        ? `<small>7 号发动机 · 总装中</small><span class="tag-count"><b>16</b><i>已拆下 · 停用</i></span><small>叶环留出 16 个空位</small>`
        : `<small>7 号发动机 · 总装中</small><span class="tag-count"><b>${tick(16, t, 11.55, 0.3)}</b><i>/ 100</i></span><small>已装机，未试车</small>`;
      const tg = tagHTML(p, 'red', body, tag7);
      svg += tg.svg; html += tg.html;
    }
    const tag3 = ease(seg(t, 11.85, 12.2));
    if (tag3 > 0) {
      const p = clusterOnScreen(e3, hit3.map(slot));
      const later = t >= 17.7;
      const body = later
        ? `<small>3 号发动机 · 澜川航空</small><span class="tag-count"><b>30</b><i>/ 100 · 继续飞行</i></span><small>孔探间隔减半</small>`
        : `<small>3 号发动机 · 澜川航空</small><span class="tag-count"><b>${tick(30, t, 11.85, 0.3)}</b><i>/ 100</i></span><small>在役</small>`;
      const tg = tagHTML(p, later ? 'amber' : 'red', body, tag3);
      svg += tg.svg; html += tg.html;
    }
    overlay.innerHTML = svg;
    labels.innerHTML = html;
    caption.innerHTML = t < 1.6
      ? '<span>实物</span><span>7 号发动机 · 总装中</span>'
      : '<span>实物</span><span>第一级涡轮叶环 · 其余部件半透明</span>';

    dialogRoot.innerHTML = dialogHTML(t);
    renderGraph(graphRoot, graphAt(t));
  }

  return { seek, duration: DURATION, e3, hit7: hit7.map(slot), bladeOut, cameraAt, P0, P1, P2, ink, events: clipEvents() };
}

/** Sound events of this clip, local time (主时间轴二 9.7 format). */
export type ClipEvent = { t: number; kind: 'type' | 'line' | 'tick' | 'path' | 'part' | 'alert'; gain: number; src: 'dialog' | 'graph' | '3d' };
/** First 60 fps frame from which a ticking number stays on its final value. */
function settle(final: number, at: number, dur: number) {
  let last = Math.ceil(at * 60);
  for (let f = Math.ceil(at * 60); f <= Math.ceil((at + dur) * 60); f++) if (tick(final, f / 60, at, dur) !== final) last = f + 1;
  return last / 60;
}
function clipEvents(): ClipEvent[] {
  const out: ClipEvent[] = [];
  const add = (t: number, kind: ClipEvent['kind'], gain: number, src: ClipEvent['src']) => out.push({ t, kind, gain, src });
  add(0.6, 'alert', 0.6, 'dialog');                                  // the automatic quality alert
  add(Q3_ASK_AT - 0.15, 'line', 0.4, 'dialog');
  for (const at of typedTimes(Q3_ASK, Q3_ASK_AT, 0.13, 13)) add(at, 'type', 0.32, 'dialog');
  for (const h of hops) add(h.a, 'path', 0.5, 'graph');
  for (const at of [5.0, 7.35, 11.55, 11.85]) add(at, 'line', 0.7, 'dialog');
  add(settle(2, 5.0, 0.25), 'tick', 0.5, 'dialog');
  add(10.6, 'tick', 0.5, 'dialog');                                  // the scan ends on 46
  add(settle(16, 11.55, 0.3), 'tick', 0.5, 'dialog');
  add(settle(30, 11.85, 0.3), 'tick', 0.5, 'dialog');
  add(FOLLOW_AT - 0.2, 'line', 0.4, 'dialog');
  for (const at of typedTimes(FOLLOW_ASK, FOLLOW_AT, 0.055, 29)) add(at, 'type', 0.32, 'dialog');
  for (const at of [16.9, 17.7, 18.5]) add(at, 'line', 0.7, 'dialog');
  add(settle(16, 16.9, 0.3), 'tick', 0.5, 'dialog');
  add(settle(200, 17.95, 0.3), 'tick', 0.5, 'dialog');
  for (let i = 0; i < hit7.length; i++) add(16.9 + i * 0.04 + noise(i + 5) * 0.06, 'part', 0.35, '3d');
  add(19.0, 'alert', 0.7, 'dialog');                                 // question two's answer turns red
  return out.sort((a, b) => a.t - b.t);
}
