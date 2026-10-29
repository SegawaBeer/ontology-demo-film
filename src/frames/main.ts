import * as THREE from 'three';
import './frames.css';
import { renderDialog, type Turn } from './dialog';
import { renderGraph } from './graph';
import { fleetBlocks, type GraphState } from './data';
import { createModelView, type Theme } from './scene';
import { mountOpen } from './open';
import { mountOpening } from './clip-open';
import { NET_GRAPH, NET_VIEW } from './net';

const params = new URLSearchParams(location.search);
const theme: Theme = params.get('theme') === 'dark' ? 'dark' : 'light';
const frameName = params.get('frame') ?? 'q3';
document.documentElement.dataset.theme = theme;
const num = (key: string, fallback: number) => Number(params.get(key) ?? fallback);

// Exports run at exactly 1920×1080; any other window gets the frame scaled to fit.
function fitToWindow() {
  const frame = document.querySelector<HTMLElement>('#frame')!;
  const exact = innerWidth === 1920 && innerHeight === 1080;
  document.documentElement.classList.toggle('fit', !exact && innerWidth > 0);
  if (exact || innerWidth === 0) { frame.style.transform = ''; return; }
  const k = Math.min(innerWidth / 1920, innerHeight / 1080);
  frame.style.transform = `translate(${(innerWidth - 1920 * k) / 2}px, ${(innerHeight - 1080 * k) / 2}px) scale(${k})`;
}
fitToWindow();
addEventListener('resize', fitToWindow);
const ink = theme === 'dark'
  ? { red: '#ff4a3a', amber: '#f0a93a', ring: '#c9d2d8', lit: '#9fd6f0' }
  : { red: '#e0362a', amber: '#d98a12', ring: '#9aa6af', lit: '#1c5fb8' };

// Blades hit by batch YSZ-2410. The graph dots use the same ring slots, so the
// red cells on the right match the red blades in the middle.
const RING = 'turbine.stage-1-blades';
const slot = (n: number) => `${RING}.${String(((n - 1 + 100) % 100) + 1).padStart(3, '0')}`;
const range = (from: number, count: number) => Array.from({ length: count }, (_, i) => from + i);
const hit7 = range(num('s7', 9), 16);
const hit3 = range(num('s3', 2), 30);

function fleetOffset(key: string) {
  let offset = 0;
  for (const block of fleetBlocks) {
    if (block.key === key) return offset;
    offset += block.count;
  }
  return 0;
}

const q1: Turn = {
  type: 'ask', dept: '研发', time: '02:07', past: true,
  text: '第一级涡轮叶片的冷却孔缩小 0.1 毫米，会影响到哪些东西？',
  answer: '<p class="answer">在制叶片 300 枚 · 在途铸件 200 件 · 涉及发动机 5 台</p>',
};
const q2: Turn = {
  type: 'ask', dept: '总装', time: '02:11', past: true,
  text: '7 号发动机明早 9 点能按时上试车台吗？',
  answer: '<p class="answer green"><span>可以按时上试车台</span><span class="state">09:00</span></p>',
};
const alert: Turn = {
  type: 'alert', dept: '质量', time: '02:15',
  text: '涂层检测：批次 YSZ-2410 粉末杂质超标',
  detail: 'CT-1024-03 · 实测 0.42% / 上限 0.30%',
};

const svg = document.querySelector<SVGSVGElement>('#callouts')!;
const labels = document.querySelector<HTMLElement>('#callout-labels')!;
const modelColumn = document.querySelector<HTMLElement>('.col-model')!;

function caption(left: string, right: string) {
  modelColumn.insertAdjacentHTML('beforeend', `<div class="model-caption"><span>${left}</span><span>${right}</span></div>`);
}

function tag(p: { x: number; y: number }, lx: number, tone: 'red' | 'amber' | 'lit', html: string, ly = p.y) {
  const colour = `var(--${tone})`;
  svg.insertAdjacentHTML('beforeend',
    `<circle cx="${p.x}" cy="${p.y}" r="2.5" fill="${colour}"/>` +
    `<path d="M${p.x} ${p.y} L${lx - 30} ${ly} H${lx - 10}" fill="none" stroke="${colour}" stroke-width="1" opacity="0.8"/>`);
  labels.insertAdjacentHTML('beforeend', `<div class="tag tone-${tone}" style="left:${lx}px;top:${ly}px">${html}</div>`);
}

async function questionThree() {
  renderDialog(document.querySelector('#dialog')!, [q1, q2, alert, {
    type: 'ask', dept: '质量', time: '02:15',
    text: '这批粉末都用到哪儿了？',
    steps: [
      '喷涂工单 <em>2</em> 张',
      '第一级涡轮叶片 <em class="red">46</em> 枚',
      '7 号发动机 <em class="red">16</em> 枚 · 已装机，未试车<br>3 号发动机 <em class="red">30</em> 枚 · 在役',
    ],
    live: 2,
  }], { left: '已检索 1,016 枚叶片 · 2,140 条关系', right: '0.8 秒' });

  renderGraph(document.querySelector('#graph')!, {
    focus: true,
    lit: ['coat', 'powder', 'spray', 'blade', 'c-t1', 'm-turb', 'e7', 'e3'],
    litEdges: [['coat', 'powder'], ['powder', 'spray'], ['spray', 'blade'], ['blade', 'c-t1'], ['c-t1', 'm-turb'], ['m-turb', 'e7'], ['blade', 'e3']],
    chip: {
      coat: { text: 'CT-1024-03', tone: 'red' },
      powder: { text: 'YSZ-2410', tone: 'red' },
      spray: { text: 'PT-0817 · PT-0903' },
      e7: { text: '16 枚', tone: 'red' },
      e3: { text: '30 枚', tone: 'red' },
    },
    status: { powder: 'red', coat: 'red', e7: 'red', e3: 'red' },
    timing: [{ text: '9 ms', x: 196, y: 920 }, { text: '31 ms', x: 446, y: 842 }, { text: '0.42 s', x: 350, y: 300 }],
    dots: {
      hits: [...hit3.map(n => fleetOffset('3') + ((n - 1 + 100) % 100)), ...hit7.map(n => fleetOffset('7') + ((n - 1 + 100) % 100))],
      caption: '1,016 枚逐一核对 · <tspan fill="var(--red)" font-weight="600">46</tspan> 枚命中',
    },
  });

  const view = await createModelView(document.querySelector('#model')!, theme);
  const shell = { solid: [RING, 'turbine.stage-1-disk'] };
  const e7 = view.addEngine(shell, new THREE.Vector3(0, 1.05, 0), 1);
  const e3 = view.addEngine(shell, new THREE.Vector3(0.5, -1.25, 0.35), 0.6);
  for (const engine of [e7, e3]) engine.setColor(engine.listParts(RING), ink.ring);
  e7.setColor(hit7.map(slot), ink.red);
  e3.setColor(hit3.map(slot), ink.red);
  view.frame([e7, e3], new THREE.Vector3(-0.88, 0.3, 0.42), { x: 0.92, y: 0.84 }, new THREE.Vector2(-0.2, -0.02));
  view.cutaway(e7);
  view.cutaway(e3);
  view.render();

  for (const [engine, slots, head, big, note] of [
    [e7, hit7, '7 号发动机 · 总装中', '16', '已装机，未试车'],
    [e3, hit3, '3 号发动机 · 澜川航空', '30', '在役'],
  ] as const) {
    const mid = slots.map(n => view.worldOf(engine, slot(n))!).reduce((a, b) => a.add(b), new THREE.Vector3()).multiplyScalar(1 / slots.length);
    tag(view.project(mid), 556, 'red', `<small>${head}</small><span class="tag-count"><b>${big}</b><i>/ 100</i></span><small>${note}</small>`);
  }
  caption('实物', '第一级涡轮叶环 · 其余部件半透明');
}

// Right after the stop-use action: question two's answer rewrites itself.
async function staleAnswer() {
  renderDialog(document.querySelector('#dialog')!, [
    q1,
    {
      ...q2, changed: '自动更新 · 02:17',
      answer: '<p class="answer"><span class="was">可以按时上试车台 09:00</span><span class="now">暂不能上试车台 · 等待 16 枚叶片</span></p>',
    } as Turn,
    {
      type: 'ask', dept: '质量', time: '02:15', past: true,
      text: '这批粉末都用到哪儿了？',
      answer: '<p class="answer">第一级涡轮叶片 46 枚 · 7 号发动机 16 枚 · 3 号发动机 30 枚</p>',
    },
    {
      type: 'ask', dept: '质量', time: '02:17',
      text: '7 号上的 16 枚拆下停用。3 号发动机还能继续飞吗？',
      steps: [
        '已停用 <em class="red">16</em> 枚 · 批次 YSZ-2410 已冻结',
        '3 号发动机按设计余量可继续飞行<br>孔探间隔 <em>400</em> → <em class="amber">200</em> 循环',
        '2027 年 3 月进厂时更换 <em>30</em> 枚 · 已通知澜川航空',
      ],
      live: 2,
    },
  ], { left: '已执行 2 个动作 · 更新 20 个对象 · 新建 1 个', right: '1.1 秒' });

  renderGraph(document.querySelector('#graph')!, {
    focus: true,
    lit: ['powder', 'spray', 'blade', 'c-t1', 'm-turb', 'e7', 'e3', 'awo'],
    litEdges: [['powder', 'spray'], ['spray', 'blade'], ['blade', 'c-t1'], ['c-t1', 'm-turb'], ['m-turb', 'e7'], ['blade', 'e3'], ['awo', 'e7']],
    chip: {
      powder: { text: 'YSZ-2410 · 已冻结', tone: 'red' },
      e7: { text: '暂不能上试车台', tone: 'red' },
      e3: { text: '孔探间隔减半', tone: 'amber' },
      awo: { text: '+ 更换 16 枚叶片', tone: 'amber' },
      disposal: { text: 'CZ-1024-01', tone: 'red' },
    },
    status: { powder: 'red', e7: 'red', e3: 'amber', awo: 'amber', disposal: 'red' },
    timing: [],
    fresh: ['disposal'],
    spawned: [{
      node: { id: 'disposal', x: 186, y: 1040, label: '处置单', kind: 'biz', group: 'qa', anchor: 'right' },
      edges: [['disposal', 'blade', 0.22]],
    }],
  });

  const view = await createModelView(document.querySelector('#model')!, theme);
  const shell = { solid: [RING, 'turbine.stage-1-disk'] };
  const e7 = view.addEngine(shell, new THREE.Vector3(0, 1.05, 0), 1);
  const e3 = view.addEngine(shell, new THREE.Vector3(0.5, -1.25, 0.35), 0.6);
  for (const engine of [e7, e3]) engine.setColor(engine.listParts(RING), ink.ring);
  e7.setColor(hit7.map(slot), ink.red);
  e3.setColor(hit3.map(slot), ink.amber);

  // The 16 stopped blades slide out radially, leaving their slots empty.
  const pull = num('pull', 0.5);
  const out: THREE.Vector3[] = [];
  for (const n of hit7) {
    const c = new THREE.Vector3(...e7.getPart(slot(n))!.center);
    const radial = new THREE.Vector3(0, c.y, c.z).normalize();
    const offset = radial.multiplyScalar(pull);
    e7.setTransform(slot(n), { position: [offset.x, offset.y, offset.z] });
    out.push(c.add(offset));
  }

  view.frame([e7, e3], new THREE.Vector3(-0.88, 0.3, 0.42), { x: 0.92, y: 0.84 }, new THREE.Vector2(-0.2, -0.02));
  view.cutaway(e7);
  view.cutaway(e3);
  view.render();

  e7.root.updateMatrixWorld(true);
  const mid7 = out.reduce((a, b) => a.add(b.clone()), new THREE.Vector3()).multiplyScalar(1 / out.length).applyMatrix4(e7.root.matrixWorld);
  tag(view.project(mid7), 556, 'red', '<small>7 号发动机 · 总装中</small><span class="tag-count"><b>16</b><i>已拆下 · 停用</i></span><small>叶环留出 16 个空位</small>');
  const mid3 = hit3.map(n => view.worldOf(e3, slot(n))!).reduce((a, b) => a.add(b), new THREE.Vector3()).multiplyScalar(1 / hit3.length);
  tag(view.project(mid3), 556, 'amber', '<small>3 号发动机 · 澜川航空</small><span class="tag-count"><b>30</b><i>/ 100 · 继续飞行</i></span><small>孔探间隔减半</small>');
  caption('实物', '第一级涡轮叶环 · 其余部件半透明');
}

// 0:28 in the opening: the tree has become a net and the last links are still
// being laid. The link that lands on a part makes that part flash on the engine.
async function treeToNet() {
  document.querySelector('#frame')!.classList.add('layout-split');
  const graph: GraphState = {
    focus: false,
    relStyle: 'strong',
    lit: ['po', 'm-comb', 'stock'],
    litEdges: [],
    chip: { po: { text: 'PO-26-1187' } },
    status: {},
    timing: [],
    fresh: ['m-comb'],
    hidden: [['po', 'supplier']],
    drawing: [
      { from: 'po', to: 'm-comb', progress: 1 },
      { from: 'stock', to: 'blade', progress: num('progress', 0.42) },
    ],
    counter: '34 个节点 · 33 / 35 条关系',
  };
  renderGraph(document.querySelector('#graph')!, graph);

  const width = 1280;
  svg.setAttribute('viewBox', `0 0 ${width} 1080`);
  const view = await createModelView(document.querySelector('#model')!, theme, width);
  const e7 = view.addEngine({ ghost: ['nacelle', 'fan-cowl', 'core-casing'] }, new THREE.Vector3(0, 0, 0), 1);
  e7.setColor('combustor', ink.lit);
  view.frame([e7], new THREE.Vector3(0.78, 0.34, 0.92), { x: 0.78, y: 0.7 }, new THREE.Vector2(-0.06, 0.02));
  view.cutaway(e7);
  view.render();

  const p = view.project(view.worldOf(e7, 'combustor.inner-shell.001')!);
  tag(p, num('lx', 780), 'lit', '<small>燃烧室 · 外购</small><span class="tag-count"><b class="mono-sm">PO-26-1187</b></span><small>刚连上：采购订单 → 燃烧室</small>', num('ly', 250));
  caption('实物', '7 号发动机 · 总装中');
}

// 0:30 hand-off: every link laid, nothing highlighted, combustor in its own colour.
async function netEnd() {
  document.querySelector('#frame')!.classList.add('layout-split');
  renderGraph(document.querySelector('#graph')!, NET_GRAPH);
  const width = 1280;
  svg.setAttribute('viewBox', `0 0 ${width} 1080`);
  const view = await createModelView(document.querySelector('#model')!, theme, width);
  const e7 = view.addEngine({ ghost: NET_VIEW.ghost }, new THREE.Vector3(0, 0, 0), 1);
  view.frame([e7], NET_VIEW.direction, NET_VIEW.limits, NET_VIEW.shift);
  view.cutaway(e7);
  view.render();
  caption(...NET_VIEW.caption);
}

// Timed clip: `?frame=clip` previews in real time (or holds `&t=`), and the
// exporter drives it through window.__seek one frame at a time.
async function clip() {
  const { mountClip } = await import('./clip-q3');
  const player = await mountClip(theme);
  const hold = params.get('t');
  (window as unknown as { __seek: (t: number) => void; __duration: number }).__seek = player.seek;
  (window as unknown as { __duration: number }).__duration = player.duration;
  if (hold !== null) { player.seek(Number(hold)); return; }
  if (params.get('play') === '0') { player.seek(0); return; }
  const start = performance.now();
  const loop = (now: number) => {
    player.seek(((now - start) / 1000) % (player.duration + 1.5));
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}

// Main timeline part one, global t 30–64. Same driving as clip: `&t=` holds a
// moment, `&play=0` holds the start, otherwise it previews in real time until
// something (the exporter) calls window.__seek.
async function filmA() {
  const { mountFilmA, START, DURATION } = await import('./clip-q12');
  const player = await mountFilmA(theme);
  const w = window as unknown as Record<string, unknown>;
  let driven = false;
  w.__seek = (t: number) => { driven = true; player.seek(t); };
  w.__duration = DURATION;
  w.__start = START;
  w.__events = player.events;
  w.__filmProbe = player.probe;
  w.__filmDebug = player.debug;
  const hold = params.get('t');
  if (hold !== null) { player.seek(Number(hold)); return; }
  player.seek(START);
  if (params.get('play') === '0') return;
  const start = performance.now();
  const loop = (now: number) => {
    if (driven) return;
    player.seek(START + ((now - start) / 1000) % (DURATION - START + 1.5));
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}

// The whole main timeline, global t 30–120 (主时间轴二). Driven like film-a.
async function film() {
  const { mountFilm, START, DURATION } = await import('./clip-film');
  const player = await mountFilm(theme);
  const w = window as unknown as Record<string, unknown>;
  let driven = false;
  w.__seek = (t: number) => { driven = true; player.seek(t); };
  w.__duration = DURATION;
  w.__start = START;
  w.__events = player.events;
  w.__filmProbe = player.probe;
  w.__filmDebug = player.debug;
  const hold = params.get('t');
  if (hold !== null) { player.seek(Number(hold)); return; }
  player.seek(START);
  if (params.get('play') === '0') return;
  const start = performance.now();
  const loop = (now: number) => {
    if (driven) return;
    player.seek(START + ((now - start) / 1000) % (DURATION - START + 1.5));
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}

// The ending, global t 103–120, on the opening's own engine; frame=film hands over to it at 103.
async function ending() {
  const { mountEnding, START, DURATION } = await import('./ending');
  const player = await mountEnding(theme);
  const w = window as unknown as Record<string, unknown>;
  let driven = false;
  w.__seek = (t: number) => { driven = true; player.seek(t); };
  w.__duration = DURATION;
  w.__start = START;
  w.__events = player.events;
  w.__filmProbe = player.probe;
  w.__filmDebug = player.debug;
  const hold = params.get('t');
  if (hold !== null) { player.seek(Number(hold)); return; }
  player.seek(START);
  if (params.get('play') === '0') return;
  const start = performance.now();
  const loop = (now: number) => {
    if (driven) return;
    player.seek(START + ((now - start) / 1000) % (DURATION - START + 1.5));
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}

const frames: Record<string, () => Promise<void>> = { film, ending, 'film-a': filmA, q3: questionThree, stale: staleAnswer, net: treeToNet, 'net-end': netEnd, clip, open: () => mountOpen(theme), opening: async () => { await mountOpening(theme); } };
await (frames[frameName] ?? questionThree)();
document.documentElement.dataset.ready = '1';
