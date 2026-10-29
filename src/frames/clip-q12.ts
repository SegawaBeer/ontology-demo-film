// Main timeline part one, global t 30–64 (script v1.3): the split view turns
// into three columns (30–33), then question one, 研发 · 02:07 (33–49).
// then question two, 总装 · 02:11 (49–64): the engine opens along its axis.
// Every frame is a pure function of t. The few cached flags below only mirror
// what the engine already shows, so seeking anywhere and back gives the same picture.
import * as THREE from 'three';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { renderGraph } from './graph';
import { nodes as graphNodes, type GraphState } from './data';
import { createModelView, type Theme, type Pose } from './scene';
import { createHeroBlade, HERO_COMPONENT } from '../hero-blade';
import { NET_GRAPH, NET_VIEW } from './net';
import { clamp, seg, ease, noise, bump, tick, typed, typingEnd, typedTimes, appear } from './timing';
import { foldHTML } from './fold';

export const START = 30;
export const DURATION = 64;
export const Q2_START = 49.0;

// ------------------------------------------------------------------ timeline
// 5.1 three columns
const SLIDE = [30.3, 32.4] as const;      // panel in; view offset, camera net -> P0, engine up to clip-q3's spot
const UNSHELL = [30.8, 32.4] as const;    // the net's ghost shell and cut go away
const HEAD = [32.4, 33.0] as const;       // column head and trace fade in
// 5.2 question one
const Q1_META = 33.0;
const Q1_TYPE = 33.3, Q1_PER_CHAR = 0.085, Q1_SEED = 150;   // seed 150 ends the typing at 35.90
const Q1_ASK = '第一级涡轮叶片的冷却孔缩小 0.1 毫米，会影响到哪些东西？';
// How the question breaks at 22 px in the 464 px dialog column (measured), for the fold.
const Q1_ASK_LINES = ['第一级涡轮叶片的冷却孔缩小 0.1 毫米，会影响', '到哪些东西？'];
const Q1_QUERY = 36.2;                    // typing end + 0.3
const GHOST_IN = [36.2, 37.2] as const;
const DIM_IN = [36.2, 37.0] as const;
const CLEAR_PATH = [36.4, 36.95] as const; // the two solid neighbour blades fade to 0 before it moves
const STEP_AT = [36.8, 40.8, 43.9] as const;
const PULL = [37.0, 38.2] as const;       // along the slot (axial) to about 37.6, then radial
const CAM_IN = [37.0, 38.2] as const;
const CAPTION_AT = [37.0, 48.0] as const, CAPTION_FADE = 0.3;
const INSET_OPEN = [38.0, 38.6] as const, INSET_CLOSE = [46.6, 47.1] as const;
const TURN = [38.4, 40.0] as const;       // window blade turns to the pressure side and opens
const ROWS_AT = 40.8, ROW_STEP = 0.2;
const TAGS_AT = [44.0, 44.25, 44.5] as const, TAGS_OUT = [46.6, 46.9] as const;
const TRACE_DONE = 44.6;
const DRIFT = [44.6, 46.6] as const, DRIFT_ANGLE = 0.022;
const CAM_OUT = [46.6, 48.6] as const;
const RETURN = [47.0, 48.0] as const;     // same path backwards: radial first, then axial
const GHOST_OUT = [47.4, 48.4] as const;
const GRAPH_REST = [47.0, 48.0] as const;
const FOLD = [47.6, 48.4] as const;
const UNCLEAR = [48.0, 48.4] as const;
// 5.3 question two
const Q2_META = 49.0;
const Q2_TYPE = 49.3, Q2_SEED = 135;     // seed 135 ends the typing at 51.00
const Q2_ASK = '7 号发动机明早 9 点能按时上试车台吗？';
const Q2_QUERY = 51.3;                    // typing end + 0.3
const DIM2_IN = [51.3, 52.1] as const;
const EXPLODE_OPEN = [51.6, 53.4] as const, EXPLODE_CLOSE = [60.6, 62.4] as const;
const CAM2_OUT = [51.6, 53.4] as const, CAM2_BACK = [60.0, 62.6] as const;
// The core casing interlocks with the combustor (its transition drum runs through the
// cans), so it cannot slide away; it turns to ghost while the engine is apart.
const CORE_GHOST_IN = [51.6, 52.6] as const, CORE_GHOST_OUT = [61.4, 62.4] as const;
const GLASS_AT = 52.6, GLASS_RAMP = 0.3, GLASS_HZ = 1.4, GLASS_OUT = [60.3, 61.0] as const;
const STEP2_AT = [53.8, 55.8, 57.7] as const;
const TAG2_AT = 56.0, TAG2_OUT = [60.0, 60.3] as const;
const TRACE2_DONE = 58.0, READY_AT = 62.6;
const GRAPH2_REST = [60.6, 61.8] as const;
const FOLD2 = [61.0, 61.8] as const;
const CAPTION2_AT = [51.6, 62.4] as const;
// Exploded view, engine-local x offsets (axis is x, + is forward). Compressor, nacelle,
// combustor, core casing and shaft interlock and stay; turbine and exhaust move as one
// rigid group (the tail cone wraps the rear turbine stages).
export const EXPLODE: Record<string, number> = { fan: 0.7, 'fan-cowl': 0.7, turbine: -1.0, exhaust: -1.0 };
// Where the opened engine sits in the column (NDC centre and half extents of its parts).
const EXP_FRAME = { cx: 0, cy: -0.04, lx: 0.8, ly: 0.6 };
const COMB_ANCHOR: [number, number, number] = [0.05, 0.62, 0.12];   // engine-local, on the casing top
const TAG2_DX = 60, TAG2_DY = -150;                                    // tag offset from the anchor, px

// Graph query path, same structure as clip-q3.
const hops = [
  { from: 'design', to: 'blade', a: 36.2, b: 36.8 },
  { from: 'blade', to: 'drill', a: 40.2, b: 40.6 },
  { from: 'blade', to: 'std', a: 40.3, b: 40.7 },
  { from: 'blade', to: 'mwo', a: 42.8, b: 43.3 },
  { from: 'blade', to: 'po', a: 43.0, b: 43.6 },
];
const probes: [string, number][] = [['insp', 40.85], ['spray', 40.98], ['stock', 41.1], ['e7', 43.3], ['e3', 43.5]];
const litAt: [string, number][] = [['design', 36.8], ['blade', 36.8], ['drill', 40.6], ['std', 40.7], ['mwo', 43.3], ['po', 43.6]];
const pulses: [string, number, number][] = [['blade', 36.8, 37.5], ['mwo', 43.3, 44.0], ['po', 43.6, 44.3]];
// [node, at, text, optional move]: v3.2 sits 8 px right of its default spot, clear of the drilling link.
type ChipMove = { dx?: number; dy?: number; anchor?: 'start' | 'middle' | 'end' };
const chips: [string, number, string, ChipMove?][] = [
  ['design', 36.8, 'v3.2', { dx: 8, dy: 2 }], ['drill', 40.6, 'LD-17 · LD-18'], ['std', 40.7, 'QS-T1-07', { dx: -4, anchor: 'end' }],
  ['mwo', 43.3, 'JG-2608…2610 · 8–10 号'], ['po', 43.6, 'PO-26-1163 · 11、12 号'],
];
// '0.21 s' sits beside its own link (blade -> work orders), below the line, clear of it.
const timings: [number, string, number, number][] = [[36.8, '12 ms', 96, 540], [43.3, '0.21 s', 462, 590]];
const CORE_COMPS = ['core-casing.bolts', 'core-casing.drum', 'core-casing.inner-wall', 'core-casing.tiles'];
const COMB_COMPS = ['combustor.cans', 'combustor.casing', 'combustor.injectors', 'combustor.inner-shell'];
const GLASS_TINT = new THREE.Color('#e2a23a');
// Question two: 7 号发动机 -> its 9 modules (data.ts order, 0.2 s apart, 0.15 s each), then the
// combustor's purchase order and supplier, then the assembly work order.
const MODULE_NODES = graphNodes.filter(n => n.kind === 'module').map(n => n.id);
const hops2 = [
  ...MODULE_NODES.map((id, i) => ({ from: 'e7', to: id, a: 51.6 + 0.2 * i, b: 51.75 + 0.2 * i })),
  { from: 'm-comb', to: 'po', a: 54.6, b: 55.1 },
  { from: 'po', to: 'supplier', a: 55.1, b: 55.6 },
  { from: 'e7', to: 'awo', a: 57.0, b: 57.5 },
];
const litAt2: [string, number][] = [['e7', Q2_QUERY], ...hops2.map((h): [string, number] => [h.to, h.b])];
const pulses2: [string, number, number][] = [['e7', 51.3, 52.0], ['m-comb', 52.35, 53.05], ['po', 55.1, 55.8], ['e7', 57.7, 58.4]];
// ZP-0707 is centred under its node, clear of the combustor -> purchase order link.
const chips2: [string, number, string, ChipMove?][] = [['po', 55.1, 'PO-26-1187 · 在途'], ['supplier', 55.6, '启衡航空'], ['awo', 57.5, 'ZP-0707 · 09:00 前完成', { dx: -22, dy: 4, anchor: 'middle' }]];
const timings2: [number, string, number, number][] = [[53.35, '9 ms', 575, 300], [55.6, '0.12 s', 452, 878]];
const NQ1: [number, number, number][] = [[9, 53.8, 0.3], [8, 53.9, 0.3], [1, 54.0, 0.3]];
const NQ2: [number, number, number][] = [[1, 55.8, 0.3], [160, 55.9, 0.4]];   // 160 min = 02:40
const trace2Keys: [number, number][] = [
  [51.3, 0], [51.75, 0.1], [52.2, 0.17], [53.35, 0.41], [54.6, 0.5], [55.6, 0.74], [57.0, 0.79], [57.5, 0.95], [58.0, 1],
];
// Answer numbers: [final, tick start, tick duration].
const N2: [number, number, number][] = [[2, 40.8, 0.3], [1, 40.9, 0.3]];
const N3: [number, number, number][] = [[300, 43.9, 0.35], [200, 44.05, 0.35], [5, 44.2, 0.3]];
// Search record: share of the work done by t (uneven on purpose).
const traceKeys: [number, number][] = [
  [36.2, 0], [36.8, 0.06], [37.4, 0.09], [40.2, 0.2], [40.8, 0.42], [41.3, 0.47], [42.8, 0.55], [43.6, 0.86], [44.2, 0.97], [44.6, 1],
];

// ------------------------------------------------------------------ layout
const W = 1280;            // one canvas under the dialog and model columns
const COL_X = 561;         // first canvas pixel of the 720-wide model column (clip-q3's canvas pixel 0)
const COL_W = 720;
export const LIFT = 1.05;         // clip-q3 keeps 7 号发动机 at (0, 1.05, 0)
const RING = 'turbine.stage-1-blades';
const DISK = 'turbine.stage-1-disk';
// Ghosted parts on the pulled blade's way (inner cone, shaft, stage-1 tip ring,
// stage-2 hub) stay as they are: a blade passing through a ghost reads as being
// inside it (supervisor decision, task section 十一.3). Only the solid neighbours fade.
// Pull path: forward (+x) along the slot, then outward. The root (x -1.3785…-1.3315)
// clears the disk rim (x -1.340) after 0.0385; plus 20 % of the root length that is
// PULL_MIN. The axial slide runs on to PULL_AXIAL so the radial move can start the
// moment PULL_MIN is reached while the slide is still decelerating: each component
// is C2 in time, so the velocity is continuous through the corner.
const PULL_MIN = 0.0479, PULL_RADIAL = 0.063;
const PULL_JOINT = 37.6, PULL_AXIAL_END = 37.72;
// Axial distance chosen so the slide is exactly at PULL_MIN when the radial move starts.
const PULL_AXIAL = PULL_MIN / ease(seg(PULL_JOINT, PULL[0], PULL_AXIAL_END));
/** Engine-local displacement of the pulled blade: [axial, radial]. Returns run the same path backwards. */
function pullAt(t: number): [number, number] {
  const out = (u: number): [number, number] => [PULL_AXIAL * ease(seg(u, PULL[0], PULL_AXIAL_END)), PULL_RADIAL * ease(seg(u, PULL_JOINT, PULL[1]))];
  if (t < RETURN[0]) return out(t);
  // Time-reversed and scaled to the 1.0 s return: radial back first, then axial.
  return out(PULL[0] + (RETURN[1] - t) * (PULL[1] - PULL[0]) / (RETURN[1] - RETURN[0]));
}
// Overlay layout in model-column pixels (720 wide); see the report for how it was measured.
const INSET = { x: 380, y: 138, w: 280, h: 400 };
const TAG_X = 380, TAG_Y = [744, 824, 904];

/** 0 = assembled, 1 = fully exploded. */
export function explodeAt(t: number) {
  return ease(seg(t, EXPLODE_OPEN[0], EXPLODE_OPEN[1])) * (1 - ease(seg(t, EXPLODE_CLOSE[0], EXPLODE_CLOSE[1])));
}
/** The flickering see-through combustor, eased in over GLASS_RAMP so it does not jump on one frame. */
function glassAt(t: number) {
  if (t < GLASS_AT || t >= GLASS_OUT[1]) return null;
  const flick = 0.35 + 0.15 * Math.sin(2 * Math.PI * GLASS_HZ * (t - GLASS_AT));
  const on = ease(seg(t, GLASS_AT, GLASS_AT + GLASS_RAMP)) * (1 - ease(seg(t, GLASS_OUT[0], GLASS_OUT[1])));
  return { opacity: 1 + (flick - 1) * on, mix: 0.35 * on };
}
// ------------------------------------------------------------------ dialog
const PAST_Q1 = `<div class="turn past"><div class="meta"><b>研发</b><span>02:07</span></div>
    <p class="ask">第一级涡轮叶片的冷却孔缩小 0.1 毫米，会影响到哪些东西？</p>
    <p class="answer">在制叶片 300 枚 · 在途铸件 200 件 · 涉及发动机 5 台</p></div>`;
const Q1_TYPE_END = typingEnd(Q1_ASK, Q1_TYPE, Q1_PER_CHAR, Q1_SEED);

const num = (t: number, [final, at, dur]: [number, number, number]) => tick(final, t, at, dur);
function q1Steps(t: number) {
  const steps: string[] = [];
  if (t >= STEP_AT[0]) steps.push(`<div class="step" style="${appear(t, STEP_AT[0])}"><span class="n">01</span><span class="line">设计版本 v3.2 → 第一级涡轮叶片</span></div>`);
  if (t >= STEP_AT[1]) steps.push(`<div class="step" style="${appear(t, STEP_AT[1])}"><span class="n">02</span><span class="line">打孔程序 <em>${num(t, N2[0])}</em> 套 · 检验标准 <em>${num(t, N2[1])}</em> 份</span></div>`);
  if (t >= STEP_AT[2]) {
    // 16 characters: folded after the second count (the separator stays at the end
    // of the first line), as clip-q3 folds its long lines.
    const second = t >= N3[2][1]
      ? `<br><span style="${appear(t, N3[2][1])};display:inline-block">涉及发动机 <em>${num(t, N3[2])}</em> 台</span>` : '';
    steps.push(`<div class="step" style="${appear(t, STEP_AT[2])}"><span class="n">03</span><span class="line">在制叶片 <em>${num(t, N3[0])}</em> 枚 · 在途铸件 <em>${t < N3[1][1] ? 0 : num(t, N3[1])}</em> 件${second ? ' ·' : ''}${second}</span></div>`);
  }
  return steps;
}

const PAST_Q2 = `<div class="turn past"><div class="meta"><b>总装</b><span>02:11</span></div>
      <p class="ask">7 号发动机明早 9 点能按时上试车台吗？</p>
      <p class="answer green"><span>可以按时上试车台</span><span class="state">09:00</span></p></div>`;
const Q2_TYPE_END = typingEnd(Q2_ASK, Q2_TYPE, Q1_PER_CHAR, Q2_SEED);
const clock = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
function q2Steps(t: number) {
  const steps: string[] = [];
  if (t >= STEP2_AT[0]) steps.push(`<div class="step" style="${appear(t, STEP2_AT[0])}"><span class="n">01</span><span class="line">核对 <em>${num(t, NQ1[0])}</em> 个模块：<em class="green">${num(t, NQ1[1])}</em> 个到位，<em class="amber">${num(t, NQ1[2])}</em> 个缺件</span></div>`);
  if (t >= STEP2_AT[1]) steps.push(`<div class="step" style="${appear(t, STEP2_AT[1])}"><span class="n">02</span><span class="line">缺燃烧室组件 <em>${num(t, NQ2[0])}</em> 套，采购单在途，<em>${clock(t < NQ2[1][1] ? 0 : num(t, NQ2[1]))}</em> 到厂</span></div>`);
  if (t >= STEP2_AT[2]) steps.push(`<div class="step" style="${appear(t, STEP2_AT[2])}"><span class="n">03</span><span class="line ok">可以按时上试车台<span class="state">09:00</span></span></div>`);
  return steps;
}

function traceAt(t: number): [string, string] {
  if (t >= READY_AT) return ['就绪', ''];
  if (t >= TRACE2_DONE) return ['已检索 5 类对象 · 27 条关系', '0.3 秒'];
  if (t >= Q2_QUERY) {
    let share = 1;
    for (let i = 1; i < trace2Keys.length; i++) {
      const [t1, v1] = trace2Keys[i], [t0, v0] = trace2Keys[i - 1];
      if (t <= t1) { share = v0 + (v1 - v0) * (t - t0) / (t1 - t0); break; }
    }
    const objects = 1 + Number(t >= 53.35) + Number(t >= 55.1) + Number(t >= 55.6) + Number(t >= 57.5);
    return [`检索中 · ${objects} 类对象 · ${Math.round(27 * share)} 条关系`, `${(0.3 * share).toFixed(2)} 秒`];
  }
  if (t < Q1_QUERY) return ['就绪', ''];
  if (t < TRACE_DONE) {
    let share = 1;
    for (let i = 1; i < traceKeys.length; i++) {
      const [t1, v1] = traceKeys[i], [t0, v0] = traceKeys[i - 1];
      if (t <= t1) { share = v0 + (v1 - v0) * (t - t0) / (t1 - t0); break; }
    }
    const objects = 1 + hops.filter(h => t >= h.b).length + Number(t >= 43.5);
    return [`检索中 · ${objects} 类对象 · ${Math.round(1284 * share).toLocaleString('en-US')} 条关系`, `${(0.6 * share).toFixed(2)} 秒`];
  }
  return ['已检索 7 类对象 · 1,284 条关系', '0.6 秒'];
}

function dialogHTML(t: number) {
  const head = ease(seg(t, HEAD[0], HEAD[1]));
  const alpha = (a: number) => a >= 1 ? '' : ` style="opacity:${a.toFixed(3)}"`;
  const blinkOff = Math.floor(t * 2.4) % 2 === 1;
  let turns = '';
  if (t >= Q1_META) {
    const askText = typed(Q1_ASK, t, Q1_TYPE, Q1_PER_CHAR, Q1_SEED);
    const askDone = t >= Q1_TYPE_END;
    const steps = q1Steps(t);
    const live = steps.length - 1;
    const stepsHTML = steps.map((s, i) => i === live ? s.replace('class="step"', `class="step live${blinkOff ? ' blink-off' : ''}"`) : s).join('');
    const cursor = !askDone || t < STEP_AT[0] ? (askDone && blinkOff ? ' typing blink-off' : ' typing') : '';
    const active = `<div class="turn" style="${appear(t, Q1_META, 0.2)}"><div class="meta"><b>研发</b><span>02:07</span></div>
        <p class="ask${cursor}">${askText}</p>${steps.length ? `<div class="steps">${stepsHTML}</div>` : ''}</div>`;
    const fold = seg(t, FOLD[0], FOLD[1]);
    turns = fold <= 0 ? active : fold >= 1 ? PAST_Q1 : foldHTML(fold, {
      meta: '<b>研发</b><span>02:07</span>', askLines: Q1_ASK_LINES, steps: `<div class="steps">${stepsHTML}</div>`,
      answer: '<p class="answer">在制叶片 300 枚 · 在途铸件 200 件 · 涉及发动机 5 台</p>',
    });
  }
  if (t >= Q2_META) {
    const askText = typed(Q2_ASK, t, Q2_TYPE, Q1_PER_CHAR, Q2_SEED);
    const askDone = t >= Q2_TYPE_END;
    const steps = q2Steps(t);
    const live = steps.length - 1;
    const stepsHTML = steps.map((s, i) => i === live ? s.replace('class="step"', `class="step live${blinkOff ? ' blink-off' : ''}"`) : s).join('');
    const cursor = !askDone || t < STEP2_AT[0] ? (askDone && blinkOff ? ' typing blink-off' : ' typing') : '';
    const active = `<div class="turn" style="${appear(t, Q2_META, 0.2)}"><div class="meta"><b>总装</b><span>02:11</span></div>
        <p class="ask${cursor}">${askText}</p>${steps.length ? `<div class="steps">${stepsHTML}</div>` : ''}</div>`;
    const fold = seg(t, FOLD2[0], FOLD2[1]);
    turns += fold <= 0 ? active : fold >= 1 ? PAST_Q2 : foldHTML(fold, {
      meta: '<b>总装</b><span>02:11</span>', askLines: [Q2_ASK], steps: `<div class="steps">${stepsHTML}</div>`,
      answer: '<p class="answer green"><span>可以按时上试车台</span><span class="state">09:00</span></p>',
    });
  }
  const [left, right] = t < HEAD[0] ? ['', ''] : traceAt(t);
  return `<div class="dialog"><header class="col-head"${alpha(head)}><span>提问</span><span>4 个部门 · 同一套对象</span></header>
    <div class="turns">${turns}</div>
    <div class="trace"${alpha(head)}><span>${left}</span><span class="spin">${right}</span></div></div>`;
}
// ------------------------------------------------------------------ graph
/** Chips fade out early in a release, before the resting links under them brighten past 0.3. */
function chipFade(chip: GraphState['chip'], release: number) {
  if (release <= 0) return undefined;
  const k = 1 - ease(seg(release, 0, 0.09));
  return Object.fromEntries(Object.keys(chip).map(id => [id, k]));
}
function graph2At(t: number): GraphState {
  const base: GraphState = { ...NET_GRAPH, relStyle: undefined, focus: true, dimLevel: 1 };
  if (t < Q2_QUERY) return base;
  const release = ease(seg(t, GRAPH2_REST[0], GRAPH2_REST[1]));
  if (release >= 1) return base;
  const lit = litAt2.filter(([, at]) => t >= at).map(([id]) => id);
  const litEdges = hops2.filter(h => t >= h.b).map(h => [h.from, h.to] as [string, string]);
  const drawing = hops2.filter(h => t > h.a && t < h.b).map(h => ({ from: h.from, to: h.to, progress: ease(seg(t, h.a, h.b)) }));
  const status: GraphState['status'] = {};
  for (const h of hops2.slice(0, MODULE_NODES.length)) if (t >= h.b) status[h.to] = h.to === 'm-comb' ? 'amber' : 'green';
  const pulse: Record<string, number> = {};
  for (const [id, a, b] of pulses2) if (t > a && t < b) pulse[id] = seg(t, a, b);
  const chip: GraphState['chip'] = {};
  for (const [id, at, text, move] of chips2) if (t >= at) chip[id] = { text, ...move };
  const timing = timings2.filter(([at]) => t >= at).map(([, text, x, y]) => ({ text, x, y }));
  const dimLevel = 1 - 0.78 * ease(seg(t, DIM2_IN[0], DIM2_IN[1])) * (1 - release);
  return {
    focus: true, dimLevel, lit, litEdges, drawing, nodeAlpha: {}, pulse, status, chip, timing,
    counter: NET_GRAPH.counter, release: release > 0 ? release : undefined, chipAmount: chipFade(chip, release),
  };
}
function graphAt(t: number): GraphState {
  if (t >= Q2_START) return graph2At(t);
  if (t < Q1_QUERY) {
    // 30.3–32.4: the net's strong link style eases into the three-column style.
    const mix = ease(seg(t, SLIDE[0], SLIDE[1]));
    if (mix <= 0) return NET_GRAPH;
    return mix >= 1 ? { ...NET_GRAPH, relStyle: undefined, focus: true, dimLevel: 1 } : { ...NET_GRAPH, relMix: mix };
  }
  const release = ease(seg(t, GRAPH_REST[0], GRAPH_REST[1]));
  if (release >= 1) return { ...NET_GRAPH, relStyle: undefined, focus: true, dimLevel: 1 };
  const lit = litAt.filter(([, at]) => t >= at).map(([id]) => id);
  const litEdges = hops.filter(h => t >= h.b).map(h => [h.from, h.to] as [string, string]);
  const drawing = hops.filter(h => t > h.a && t < h.b).map(h => ({ from: h.from, to: h.to, progress: ease(seg(t, h.a, h.b)) }));
  const nodeAlpha: Record<string, number> = {};
  for (const [id, at] of probes) { const v = bump(t, at, at + 0.34); if (v > 0) nodeAlpha[id] = 0.22 + 0.7 * v; }
  const pulse: Record<string, number> = {};
  for (const [id, a, b] of pulses) if (t > a && t < b) pulse[id] = seg(t, a, b);
  const chip: GraphState['chip'] = {};
  for (const [id, at, text, move] of chips) if (t >= at) chip[id] = { text, ...move };
  const timing = timings.filter(([at]) => t >= at).map(([, text, x, y]) => ({ text, x, y }));
  const dimLevel = 1 - 0.78 * ease(seg(t, DIM_IN[0], DIM_IN[1])) * (1 - release);
  return {
    focus: true, dimLevel, lit, litEdges, drawing, nodeAlpha, pulse, status: {}, chip, timing,
    counter: NET_GRAPH.counter, release: release > 0 ? release : undefined, chipAmount: chipFade(chip, release),
  };
}

// ------------------------------------------------------------------ sound events
/** First 60 fps frame from which a ticking number stays on its final value (small numbers land early). */
export function settleAt([final, at, dur]: [number, number, number]) {
  let last = Math.ceil(at * 60);
  for (let f = Math.ceil(at * 60); f <= Math.ceil((at + dur) * 60); f++) if (tick(final, f / 60, at, dur) !== final) last = f + 1;
  return last / 60;
}
export type FilmEvent = {
  t: number;
  kind: 'type' | 'line' | 'tick' | 'path' | 'slide' | 'part' | 'swap' | 'alert' | 'tone';
  gain: number;
  /** Which column the sound belongs to (主时间轴二 9.7). */
  src: 'dialog' | 'graph' | '3d';
  /** Slides only: length of the move in seconds. */
  dur?: number;
};
export function buildEvents(): FilmEvent[] {
  const out: FilmEvent[] = [];
  const add = (t: number, kind: FilmEvent['kind'], gain: number, src: FilmEvent['src'], dur?: number) => out.push(dur === undefined ? { t, kind, gain, src } : { t, kind, gain, src, dur });
  add(SLIDE[0], 'slide', 0.6, 'dialog', SLIDE[1] - SLIDE[0]);
  // Question one
  add(Q1_META, 'line', 0.4, 'dialog');
  for (const at of typedTimes(Q1_ASK, Q1_TYPE, Q1_PER_CHAR, Q1_SEED)) add(at, 'type', 0.32, 'dialog');
  for (const h of hops) add(h.a, 'path', 0.5, 'graph');
  for (const at of STEP_AT) add(at, 'line', 0.7, 'dialog');
  for (const n of [...N2, ...N3]) add(settleAt(n), 'tick', 0.5, 'dialog');
  add(CAM_IN[0], 'slide', 0.45, '3d', CAM_IN[1] - CAM_IN[0]);
  add(CAM_OUT[0], 'slide', 0.45, '3d', CAM_OUT[1] - CAM_OUT[0]);
  add(PULL[0], 'part', 0.6, '3d'); add(PULL_JOINT, 'part', 0.4, '3d');
  add(RETURN[0], 'part', 0.4, '3d'); add(RETURN[1], 'part', 0.6, '3d');
  for (const at of TAGS_AT) add(at, 'line', 0.35, '3d');
  add(FOLD[0], 'line', 0.3, 'dialog');
  // Question two
  add(Q2_META, 'line', 0.4, 'dialog');
  for (const at of typedTimes(Q2_ASK, Q2_TYPE, Q1_PER_CHAR, Q2_SEED)) add(at, 'type', 0.32, 'dialog');
  hops2.forEach((h, i) => add(h.a, 'path', i < MODULE_NODES.length ? 0.3 : 0.5, 'graph'));
  for (const at of STEP2_AT) add(at, 'line', 0.7, 'dialog');
  for (const n of [...NQ1, ...NQ2]) add(settleAt(n), 'tick', 0.5, 'dialog');
  add(CAM2_OUT[0], 'slide', 0.45, '3d', CAM2_OUT[1] - CAM2_OUT[0]);
  add(CAM2_BACK[0], 'slide', 0.45, '3d', CAM2_BACK[1] - CAM2_BACK[0]);
  for (const at of [EXPLODE_OPEN[0], EXPLODE_OPEN[1], EXPLODE_CLOSE[0], EXPLODE_CLOSE[1]]) add(at, 'part', 0.55, '3d');
  add(GLASS_AT, 'alert', 0.35, '3d');
  add(TAG2_AT, 'line', 0.35, '3d'); add(FOLD2[0], 'line', 0.3, 'dialog');
  return out.sort((a, b) => a.t - b.t);
}
// ------------------------------------------------------------------ close-up window
// Same construction as clip-q3's createInset: the detailed cooled blade in its own
// small scene, drawn into a rectangle of the main canvas after the main view.
const INTERIOR = new THREE.Color('#555a5b');
const COAT_IDS = ['coat-base', 'coat-bond', 'coat-tgo', 'coat-ysz'].map(id => `${HERO_COMPONENT}.${id}`);
const FILM_ROWS = [1, 2, 3, 4].map(n => `${HERO_COMPONENT}.film-ps-${n}`).concat([1, 2, 3, 4].map(n => `${HERO_COMPONENT}.film-ss-${n}`));
const TURN_FROM = 1.15;   // radians about the span: starts edge-on, ends facing the pressure side

async function createInset(renderer: THREE.WebGLRenderer, theme: Theme, canvasWidth: number) {
  let originX = COL_X, fullWidth = canvasWidth;
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
  for (const id of COAT_IDS) hero.setVisible(id, false);
  const spin = new THREE.Group();
  spin.add(hero.root);
  const tilt = new THREE.Group();
  tilt.rotation.set(-0.06, -0.12, -0.13);
  tilt.add(spin);
  scene.add(tilt);
  tilt.updateMatrixWorld(true);

  // Framed for the blade alone (no coupon), with room for it to turn about its span.
  const camera = new THREE.PerspectiveCamera(28, INSET.w / INSET.h, 0.1, 100);
  const box = new THREE.Box3(new THREE.Vector3(-1.05, -0.7, -0.95), new THREE.Vector3(1.25, 4.25, 0.95));
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
  const probe = new THREE.Color(theme === 'dark' ? '#9fd6f0' : '#1c5fb8');

  /** reveal 0..1 wipes the window open from the top; turn 0..1 also opens the cutaway. */
  function draw(reveal: number, turn: number, rows: number[]) {
    spin.rotation.y = TURN_FROM * (1 - turn);
    hero.setCutaway(turn);
    rows.forEach((a, i) => hero.setColor(FILM_ROWS[i], a > 0 ? INTERIOR.clone().lerp(probe, a) : null));
    const hh = INSET.h * reveal;
    if (hh < 1) return;
    renderer.setScissorTest(true);
    renderer.setScissor(originX + INSET.x, 1080 - INSET.y - hh, INSET.w, hh);
    renderer.setViewport(originX + INSET.x, 1080 - INSET.y - INSET.h, INSET.w, INSET.h);
    renderer.render(scene, camera);
    renderer.setScissorTest(false);
    renderer.setViewport(0, 0, fullWidth, 1080);
  }
  const setOrigin = (x: number, w: number) => { originX = x; fullWidth = w; };
  return { draw, hero, setOrigin };
}

// ------------------------------------------------------------------ camera helpers
const Y_AXIS = new THREE.Vector3(0, 1, 0);
/** Turn along a slerp, distance and target along the same curve; distance in log space, so no pull-back. */
export function blendPose(a: Pose, b: Pose, p: number): Pose {
  if (p <= 0) return { position: a.position.clone(), target: a.target.clone() };
  if (p >= 1) return { position: b.position.clone(), target: b.target.clone() };
  const da = a.position.clone().sub(a.target), db = b.position.clone().sub(b.target);
  const la = da.length(), lb = db.length();
  const q = new THREE.Quaternion().setFromUnitVectors(da.clone().normalize(), db.clone().normalize());
  const dir = da.normalize().applyQuaternion(new THREE.Quaternion().slerp(q, p));
  const target = a.target.clone().lerp(b.target, p);
  return { target, position: target.clone().addScaledVector(dir, Math.exp(THREE.MathUtils.lerp(Math.log(la), Math.log(lb), p))) };
}
export const shiftPose = (pose: Pose, by: THREE.Vector3): Pose => ({ position: pose.position.clone().add(by), target: pose.target.clone().add(by) });
// ------------------------------------------------------------------ mount
export async function mountFilmA(theme: Theme) {
  const params = new URLSearchParams(location.search);
  const frameEl = document.querySelector<HTMLElement>('#frame')!;
  frameEl.classList.add('layout-film');
  const dialogRoot = document.querySelector<HTMLElement>('#dialog')!;
  const graphRoot = document.querySelector<SVGSVGElement>('#graph')!;
  const overlay = document.querySelector<SVGSVGElement>('#callouts')!;
  const labels = document.querySelector<HTMLElement>('#callout-labels')!;
  overlay.setAttribute('viewBox', `0 0 ${COL_W} 1080`);
  const caption = document.createElement('div');
  caption.className = 'model-caption';
  document.querySelector('.col-model')!.append(caption);

  const ink = theme === 'dark'
    ? { ring: '#c9d2d8', probe: '#9fd6f0' }
    : { ring: '#9aa6af', probe: '#1c5fb8' };
  const view = await createModelView(document.querySelector('#model')!, theme, W);
  const inset = await createInset(view.renderer, theme, W);
  const e7 = view.addEngine({ ghost: NET_VIEW.ghost, solid: [RING, DISK], layered: true }, new THREE.Vector3(0, 0, 0), 1);
  const camera = view.camera;
  const ringParts = e7.listParts(RING);
  const layerIds = view.layerIds(e7);
  const netShell = new Set(e7.modules.filter(m => NET_VIEW.ghost.includes(m.meta.id)).flatMap(m => m.components.map(c => c.meta.id)));
  // Ghost amount each component was last given, for the checks (solid = 0).
  const ghostNow = new Map<string, number>();
  const coreSet = new Set(CORE_COMPS), combSet = new Set(COMB_COMPS);

  // Poses. The net pose is net-end's own fit (1280-wide camera, engine at the origin).
  // P0 is clip-q3's fit (720-wide camera, engine at y 1.05); the canvas then shows
  // it through a view offset, so the right 720 columns match clip-q3's canvas.
  const NET = view.fit([e7], NET_VIEW.direction, NET_VIEW.limits, NET_VIEW.shift);
  camera.aspect = COL_W / 1080;
  camera.updateProjectionMatrix();
  e7.root.position.set(0, LIFT, 0);
  const P0 = view.fit([e7], new THREE.Vector3(-0.88, 0.3, 0.42), { x: 0.9, y: 0.66 }, new THREE.Vector2(-0.16, 0.1));
  // clip-q3 renders t=0 with target + (position − target); keep its exact floats.
  const REST: Pose = { target: P0.target.clone(), position: P0.target.clone().add(P0.position.clone().sub(P0.target)) };
  e7.root.updateMatrixWorld(true);
  const ringCenter = new THREE.Vector3(-1.355, 0, 0).applyMatrix4(e7.root.matrixWorld);
  const P1: Pose = { target: P0.target.clone().lerp(ringCenter, 0.82), position: new THREE.Vector3() };
  P1.position.copy(P1.target).add(P0.position.clone().sub(P0.target).multiplyScalar(0.5));
  const lift = new THREE.Vector3(0, LIFT, 0);
  const setExplode = (p: number) => { for (const m of e7.modules) m.group.position.x = (EXPLODE[m.meta.id] ?? 0) * p; };
  // Exploded framing: P0's viewing direction, distance and target fitted to the opened engine.
  const EXP: Pose = (() => {
    setExplode(1);
    e7.root.updateMatrixWorld(true);
    const pts: THREE.Vector3[] = [];
    for (const [id] of e7.parts) { const P = e7.partWorldPoints(id)!; for (let i = 0; i < P.length; i += 24) pts.push(new THREE.Vector3(P[i], P[i + 1], P[i + 2])); }
    setExplode(0);
    e7.root.updateMatrixWorld(true);
    const cam = new THREE.PerspectiveCamera(camera.fov, COL_W / 1080, camera.near, camera.far);
    const dir = REST.position.clone().sub(REST.target).normalize();
    const target = new THREE.Box3().setFromPoints(pts).getCenter(new THREE.Vector3());
    let dist = REST.position.distanceTo(REST.target) * 1.3;
    const halfH = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)), q = new THREE.Vector3();
    for (let i = 0; i < 40; i++) {
      cam.position.copy(target).addScaledVector(dir, dist); cam.lookAt(target); cam.updateMatrixWorld();
      let x0 = 9, x1 = -9, y0 = 9, y1 = -9;
      for (const p of pts) { q.copy(p).project(cam); x0 = Math.min(x0, q.x); x1 = Math.max(x1, q.x); y0 = Math.min(y0, q.y); y1 = Math.max(y1, q.y); }
      const right = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0), up = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 1);
      target.addScaledVector(right, ((x0 + x1) / 2 - EXP_FRAME.cx) * halfH * dist * COL_W / 1080).addScaledVector(up, ((y0 + y1) / 2 - EXP_FRAME.cy) * halfH * dist);
      dist *= Math.pow(Math.max((x1 - x0) / 2 / EXP_FRAME.lx, (y1 - y0) / 2 / EXP_FRAME.ly), 0.7);
    }
    return { target, position: target.clone().addScaledVector(dir, dist) };
  })();

  // Column camera: the 720-wide camera every overlay position is measured with.
  const colCam = new THREE.PerspectiveCamera(camera.fov, COL_W / 1080, camera.near, camera.far);
  const project = (world: THREE.Vector3) => {
    const q = world.clone().project(colCam);
    return { x: (q.x * 0.5 + 0.5) * COL_W, y: (-q.y * 0.5 + 0.5) * 1080 };
  };
  colCam.position.copy(REST.position); colCam.lookAt(REST.target); colCam.updateMatrixWorld();

  // The pulled blade: in the front half of the ring (nearer the camera than the
  // ring centre), the one highest in the overview picture.
  const ringDist = REST.position.distanceTo(ringCenter);
  const ranked = ringParts.map(id => {
    const w = new THREE.Vector3(...e7.getPart(id)!.center).applyMatrix4(e7.root.matrixWorld);
    return { id, d: REST.position.distanceTo(w), y: project(w).y };
  }).filter(r => r.d < ringDist).sort((a, b) => a.y - b.y);
  const PULLED = params.get('blade') ? `${RING}.${params.get('blade')!.padStart(3, '0')}` : ranked[0].id;
  const pulledMeta = e7.getPart(PULLED)!;
  const radial = new THREE.Vector3(0, pulledMeta.center[1], pulledMeta.center[2]).normalize();
  // Promote it now, so its mesh is the same whatever was shown before.
  e7.setTransform(PULLED, { position: [0, 0, 0] });
  // The two neighbours: the blades are staggered wider than the pitch, so on the
  // way out the pulled aerofoil and platform pass through theirs (tangential
  // overlap up to 0.0114 near the platform). They fade out with the path parts.
  const pulledNo = Number(PULLED.slice(-3));
  const NEIGHBOURS = [-1, 1].map(k => `${RING}.${String(((pulledNo - 1 + k + 100) % 100) + 1).padStart(3, '0')}`);
  e7.setOpacity(NEIGHBOURS, 1);
  // Looked up on every call: in frame=film the promoted meshes can be rebuilt later on.
  function setNeighbours(opacity: number) {
    const transparent = opacity < 0.999;
    for (const id of NEIGHBOURS) {
      if (!e7.parts.get(id)!.promoted) e7.setOpacity([id], 1);
      const m = e7.parts.get(id)!.promoted!.material as THREE.MeshStandardMaterial;
      m.opacity = opacity;
      if (m.transparent !== transparent || m.depthWrite !== !transparent) { m.transparent = transparent; m.depthWrite = !transparent; m.needsUpdate = true; }
    }
  }

  const ringBase = new THREE.Color(), ringGrey = new THREE.Color(ink.ring), probeBlue = new THREE.Color(ink.probe);
  const smooth = (p: number) => p * p * (3 - 2 * p);

  function slideAt(t: number) { return ease(seg(t, SLIDE[0], SLIDE[1])); }
  function cameraAt(t: number): Pose {
    const p = slideAt(t);
    if (t < SLIDE[1]) {
      if (p <= 0) return { position: NET.position.clone(), target: NET.target.clone() };
      const rel = blendPose(NET, shiftPose(P0, lift.clone().negate()), p);
      return shiftPose(rel, lift.clone().multiplyScalar(p));
    }
    if (t >= Q2_START) {
      // Back out along P0's own direction while the engine opens, and in again as it closes.
      const a2 = ease(seg(t, CAM2_OUT[0], CAM2_OUT[1])), b2 = ease(seg(t, CAM2_BACK[0], CAM2_BACK[1]));
      if (a2 <= 0 || b2 >= 1) return { position: REST.position.clone(), target: REST.target.clone() };
      return b2 > 0 ? blendPose(EXP, REST, b2) : blendPose(REST, EXP, a2);
    }
    const a = ease(seg(t, CAM_IN[0], CAM_IN[1])), b = ease(seg(t, CAM_OUT[0], CAM_OUT[1]));
    if (a <= 0 || b >= 1) return { position: REST.position.clone(), target: REST.target.clone() };
    const turn = DRIFT_ANGLE * ease(seg(t, DRIFT[0], DRIFT[1]));
    const P1d: Pose = { target: P1.target.clone(), position: P1.target.clone().add(P1.position.clone().sub(P1.target).applyAxisAngle(Y_AXIS, turn)) };
    return b > 0 ? blendPose(P1d, REST, b) : blendPose(REST, P1d, a);
  }

  /** `given` replaces cameraAt(t) (frame=film's way back to the split view, 101–103). */
  function applyCamera(t: number, given?: Pose) {
    const p = slideAt(t);
    const pose = given ?? cameraAt(t);
    view.applyPose(pose);
    colCam.position.copy(pose.position); colCam.lookAt(pose.target); colCam.updateMatrixWorld();
    if (p <= 0) {
      camera.clearViewOffset();
      camera.aspect = W / 1080;
      camera.updateProjectionMatrix();
    } else if (p >= 1) {
      // Three columns: a plain 720-wide camera drawn into the column's viewport,
      // the same pixel grid as clip-q3's own 720-wide canvas.
      camera.clearViewOffset();
      camera.aspect = COL_W / 1080;
      camera.updateProjectionMatrix();
    } else {
      // Principal point slides from the canvas centre to the model column's centre.
      const cx = W / 2 + (COL_X + COL_W / 2 - W / 2) * p;
      camera.setViewOffset(COL_W, 1080, COL_W / 2 - cx, 0, W, 1080);
    }
    return pose;
  }

  function engineAt(t: number) {
    const p = slideAt(t);
    e7.root.position.set(0, p >= 1 ? LIFT : LIFT * p, 0);
    const unshell = ease(seg(t, UNSHELL[0], UNSHELL[1]));
    const ghostIn = smooth(seg(t, GHOST_IN[0], GHOST_IN[1])) * (1 - smooth(seg(t, GHOST_OUT[0], GHOST_OUT[1])));
    const clear = ease(seg(t, CLEAR_PATH[0], CLEAR_PATH[1])) * (1 - ease(seg(t, UNCLEAR[0], UNCLEAR[1])));
    const coreGhost = smooth(seg(t, CORE_GHOST_IN[0], CORE_GHOST_IN[1])) * (1 - smooth(seg(t, CORE_GHOST_OUT[0], CORE_GHOST_OUT[1])));
    const glass = glassAt(t);
    for (const id of layerIds) {
      if (glass && combSet.has(id)) { view.setGlassOf(e7, [id], glass.opacity, GLASS_TINT, glass.mix); ghostNow.set(id, 0); continue; }
      let amount = netShell.has(id) ? Math.max(1 - unshell, ghostIn) : ghostIn;
      if (coreSet.has(id)) amount = Math.max(amount, coreGhost);
      view.setGhostOf(e7, [id], amount);
      ghostNow.set(id, amount);
    }
    const ex = explodeAt(t);
    setExplode(ex);
    setNeighbours(1 - clear);
    // Ring colour: its own metal in the net picture, clip-q3's grey in the three columns.
    const grey = ease(seg(t, UNSHELL[0], UNSHELL[1]));
    const toProbe = 0.5 * ease(seg(t, PULL[0], PULL[1])) * (1 - ease(seg(t, RETURN[0], RETURN[1])));
    for (const id of ringParts) {
      const state = e7.parts.get(id)!;
      const c = grey >= 1 ? ringGrey.clone() : ringBase.copy(state.baseColor).lerp(ringGrey, grey).clone();
      if (id === PULLED && toProbe > 0) c.lerp(probeBlue, toProbe);
      if (grey <= 0 && !(id === PULLED && toProbe > 0)) e7.setColor(id, null); else e7.setColor(id, c);
    }
    const [ax, rad] = pullAt(t);
    // The promoted blade sits outside the module groups, so it rides along with the turbine here.
    e7.setTransform(PULLED, { position: [ax + EXPLODE.turbine * ex, radial.y * rad, radial.z * rad] });
    return { ax, rad, ex, glass };
  }
  function captionHTML(t: number, slide: number) {
    const A = '7 号发动机 · 总装中';
    const B = t >= Q2_START ? '7 号发动机 · 按模块展开' : '第一级涡轮叶环 · 其余部件半透明';
    const at = t >= Q2_START ? CAPTION2_AT : CAPTION_AT;
    const toB = ease(seg(t, at[0], at[0] + CAPTION_FADE)) * (1 - ease(seg(t, at[1], at[1] + CAPTION_FADE)));
    const right = toB <= 0 ? `<span>${A}</span>` : toB >= 1 ? `<span>${B}</span>`
      : `<span class="xf"><span style="opacity:${(1 - toB).toFixed(3)}">${A}</span><span style="opacity:${toB.toFixed(3)}">${B}</span></span>`;
    caption.style.left = slide <= 0 ? '' : `${(40 + COL_X * slide).toFixed(2)}px`;
    return `<span>实物</span>${right}`;
  }

  // A point on the top of the combustor casing, where the question-two tag hangs from.
  const combAnchor = () => project(new THREE.Vector3(...COMB_ANCHOR).applyMatrix4(e7.root.matrixWorld));
  // Overlays, in model-column pixels.
  function overlays(t: number, bladeAt: { x: number; y: number }) {
    let svg = '', html = '';
    const open = ease(seg(t, INSET_OPEN[0], INSET_OPEN[1])) * (1 - ease(seg(t, INSET_CLOSE[0], INSET_CLOSE[1])));
    if (open > 0) {
      const { x, y, w, h } = INSET;
      const hh = h * open;
      svg += `<g>
        <path d="M${bladeAt.x.toFixed(2)} ${bladeAt.y.toFixed(2)} L${x} ${(y + hh).toFixed(2)}" stroke="var(--lit)" stroke-width="1" fill="none" opacity="${(0.8 * open).toFixed(3)}"/>
        <circle cx="${bladeAt.x.toFixed(2)}" cy="${bladeAt.y.toFixed(2)}" r="2.5" fill="var(--lit)" opacity="${open.toFixed(3)}"/>
        <rect x="${x - 0.5}" y="${y - 0.5}" width="${w + 1}" height="${(hh + 1).toFixed(2)}" fill="none" stroke="var(--node-ring)" stroke-width="1"/></g>`;
      if (open > 0.6) html += `<div class="inset-label" style="left:${x}px;top:${y - 26}px;width:${w}px;opacity:${ease(seg(open, 0.6, 1)).toFixed(3)}"><span>第一级涡轮叶片 · 放大</span><span>冷却剖面</span></div>`;
    }
    const tags = [
      `<span class="tag-count"><b>300</b><i>在制叶片 · 8–10 号</i></span>`,
      `<span class="tag-count"><b>200</b><i>在途铸件 · 11、12 号</i></span>`,
      `<span class="tag-count"><b>5</b><i>台发动机</i></span>`,
    ];
    const out = 1 - ease(seg(t, TAGS_OUT[0], TAGS_OUT[1]));
    tags.forEach((body, i) => {
      const a = ease(seg(t, TAGS_AT[i], TAGS_AT[i] + 0.3)) * out;
      if (a <= 0) return;
      const ty = TAG_Y[i];
      svg += `<g opacity="${a.toFixed(3)}"><path d="M${bladeAt.x.toFixed(2)} ${bladeAt.y.toFixed(2)} L${TAG_X - 30} ${ty} H${TAG_X - 10}" fill="none" stroke="var(--lit)" stroke-width="1" opacity="0.8"/></g>`;
      html += `<div class="tag tone-lit" style="left:${TAG_X}px;top:${ty}px;opacity:${a.toFixed(3)}">${body}</div>`;
    });
    // Question two: the amber tag beside the combustor, placed from its projected anchor.
    const a2 = ease(seg(t, TAG2_AT, TAG2_AT + 0.3)) * (1 - ease(seg(t, TAG2_OUT[0], TAG2_OUT[1])));
    if (a2 > 0) {
      const p = combAnchor();
      const lx = p.x + TAG2_DX, ly = p.y + TAG2_DY;
      svg += `<g opacity="${a2.toFixed(3)}"><circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="2.5" fill="var(--amber)"/>
        <path d="M${p.x.toFixed(2)} ${p.y.toFixed(2)} L${(lx - 14).toFixed(2)} ${ly.toFixed(2)}" fill="none" stroke="var(--amber)" stroke-width="1" opacity="0.8"/></g>`;
      html += `<div class="tag tone-amber" style="left:${lx.toFixed(2)}px;top:${ly.toFixed(2)}px;opacity:${a2.toFixed(3)}"><small>燃烧室组件 · 外购</small><span class="tag-count"><b>02:40</b></span><small>PO-26-1187 · 在途</small></div>`;
    }
    if (tags.some((_, i) => t >= TAGS_AT[i]) && out > 0) svg += `<circle cx="${bladeAt.x.toFixed(2)}" cy="${bladeAt.y.toFixed(2)}" r="2.5" fill="var(--lit)" opacity="${(ease(seg(t, TAGS_AT[0], TAGS_AT[0] + 0.3)) * out).toFixed(3)}"/>`;
    return { svg, html, open };
  }

  // Once the columns have settled the canvas becomes clip-q3's own: 720 wide at
  // x = 561. Drawing into a viewport of the wide canvas instead shifts a few edge
  // samples, so the hand-off to clip-q3 would not be pixel-exact.
  const canvasEl = view.renderer.domElement;
  let narrow: boolean | null = null;
  function setCanvas(toNarrow: boolean) {
    if (narrow === toNarrow) return;
    narrow = toNarrow;
    const w = toNarrow ? COL_W : W;
    view.renderer.setSize(w, 1080, false);
    view.renderer.setViewport(0, 0, w, 1080);
    canvasEl.style.width = `${w}px`;
    canvasEl.style.left = toNarrow ? `${COL_X}px` : '0px';
    inset.setOrigin(toNarrow ? 0 : COL_X, w);
  }

  const panel = dialogRoot;
  let lastGraph: GraphState = NET_GRAPH;
  let lastT = START;
  let last = { pose: cameraAt(START), ax: 0, rad: 0, open: 0, turn: 0, slide: 0, ex: 0, glass: 1 };
  /** `render` false sets every state and writes the DOM but draws nothing (frame=film builds on it). */
  function seek(input: number, render = true) {
    const t = clamp(input, START, DURATION);
    lastT = t;
    const slide = slideAt(t);
    const { ax, rad, ex, glass } = engineAt(t);
    const pose = applyCamera(t);
    view.cutaway(e7, 1 - ease(seg(t, UNSHELL[0], UNSHELL[1])));
    setCanvas(slide >= 1);
    // After a jump some material and shadow state only lands on the next draw,
    // so the first draw can differ from a page opened at t. Drawing twice makes
    // every seek give the same picture as opening at t.
    if (render) { view.render(); view.render(); }
    const turn = ease(seg(t, TURN[0], TURN[1]));
    const rows = FILM_ROWS.map((_, i) => ease(seg(t, ROWS_AT + i * ROW_STEP, ROWS_AT + (i + 1) * ROW_STEP)));
    const bladeWorld = new THREE.Vector3(pulledMeta.center[0] + ax + EXPLODE.turbine * ex, pulledMeta.center[1] + radial.y * rad, pulledMeta.center[2] + radial.z * rad).applyMatrix4(e7.root.matrixWorld);
    const o = overlays(t, project(bladeWorld));
    if (render) inset.draw(o.open, turn, rows);
    overlay.innerHTML = o.svg;
    labels.innerHTML = o.html;
    caption.innerHTML = captionHTML(t, slide);
    panel.style.transform = slide >= 1 || slide <= 0 ? '' : `translateX(${(-(COL_X) * (1 - slide)).toFixed(2)}px)`;
    panel.style.display = slide <= 0 ? 'none' : '';
    dialogRoot.innerHTML = dialogHTML(t);
    lastGraph = graphAt(t);
    renderGraph(graphRoot, lastGraph);
    last = { pose, ax, rad, open: o.open, turn, slide, ex, glass: glass?.opacity ?? 1 };
  }

  const filmProbe = () => {
    const dialogLines = [...dialogRoot.querySelectorAll('.meta, .ask, .step .line, .answer, .trace span, .col-head span')]
      .filter(el => getComputedStyle(el).opacity !== '0')
      .map(el => ({ cls: el.className, text: (el as HTMLElement).innerText.replace(/\s+/g, ' ').trim() }));
    const dialogRect = panel.getBoundingClientRect();
    const modelLeft = Math.max(0, dialogRect.right);
    return {
      t: lastT,
      camera: { position: last.pose.position.toArray(), target: last.pose.target.toArray() },
      columns: { dialog: Math.max(0, dialogRect.right), model: 1280 - modelLeft, graph: 640, modelLeft },
      dialog: dialogLines,
      graph: { lit: lastGraph.lit, litEdges: lastGraph.litEdges, drawing: (lastGraph.drawing ?? []).map(d => [d.from, d.to, +d.progress.toFixed(4)]), counter: graphRoot.querySelector('text:nth-of-type(2)')?.textContent ?? '' },
      hero: { visible: last.open > 0, opacity: last.open > 0 ? 1 : 0, reveal: +last.open.toFixed(4), cutaway: +last.turn.toFixed(4) },
      pulled: { id: PULLED, axial: +last.ax.toFixed(6), radial: +last.rad.toFixed(6), world: e7.partRestWorldMatrix(PULLED) ? new THREE.Vector3().setFromMatrixPosition(e7.partRestWorldMatrix(PULLED)!).toArray().map(v => +v.toFixed(6)) : null },
      explode: Object.fromEntries(e7.modules.map(m => [m.meta.id, +(m.group.position.x).toFixed(6)])) as Record<string, number>,
      combustorOpacity: +last.glass.toFixed(4),
      engineY: e7.root.position.y,
    };
  };

  // For the checks: section profiles and opacities come from the live engine.
  const ghostOf = (partId: string) => ghostNow.get(e7.getPart(partId)?.component ?? '') ?? 0;
  const debug = { view, e7, colCam, PULLED, NEIGHBOURS, ringParts, project, ghostOf, EXPLODE, COMB_COMPS, CORE_COMPS, THREE };
  // What frame=film builds on.
  const film = { caption, netShell, layerIds, NET, REST, ringGrey, ink, captionHTML, dialogRoot, graphRoot, overlay, labels, panel, setCanvas, applyCamera, cameraAt, setNeighbours, lastPose: () => last.pose };
  return { seek, probe: filmProbe, events: buildEvents(), debug, film };
}
