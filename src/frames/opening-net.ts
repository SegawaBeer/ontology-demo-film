// Opening 3B, right column: 23.0-30.0, the tree turns into a net. Every value
// here is a pure function of t; the 3D side reads the same table for its
// flashes and the combustor highlight.
import { edges, nodes, groups, type GraphState } from './data';

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const seg = (t: number, a: number, b: number) => clamp01((t - a) / (b - a));
const smoother = (p: number) => p * p * p * (p * (p * 6 - 15) + 10);
const smootherAt = (t: number, a: number, b: number) => smoother(seg(t, a, b));
// Integral of smoother over [0, u].
const smootherIntegral = (u: number) => u ** 6 - 3 * u ** 5 + 2.5 * u ** 4;

/** Tree nodes already on screen at 23.0 (every tree node but engine three). */
export const TREE_NODES = nodes.filter(n => n.kind !== 'biz' && n.id !== 'e3').map(n => n.id);
const TREE_EDGES = edges.filter(e => e.kind === 'tree').map(e => [e.from, e.to] as [string, string]);

export const E3_START = 23.0;
/** The tree goes from lit to its resting colours while engine three fades in. */
export const TREE_SETTLE: [number, number] = [23.0, 23.6];
export const GROUP_START: Record<string, number> = { rd: 23.4, mfg: 23.8, qa: 24.2, scm: 24.6 };
const NODE_GAP = 0.08;
const NODE_FADE = 0.3;
/** Business nodes in fade-in order: by group, then data order inside a group. */
export const BIZ_PLAN = groups.flatMap(g => nodes.filter(n => n.group === g.id)
  .map((n, i) => ({ id: n.id, group: g.id, start: GROUP_START[g.id] + NODE_GAP * i })));

export type RelPlan = { from: string; to: string; start: number; end: number; litUntil: number; fade: number };
const REL_DUR = 0.35;
const rel = (from: string, to: string, start: number, end = start + REL_DUR, litUntil = end, fade = 0.4): RelPlan =>
  ({ from, to, start, end, litUntil, fade });
/** The 15 relation lines, each drawn from its business node towards the tree. */
export const REL_PLAN: RelPlan[] = [
  rel('design', 'blade', 25.0),
  rel('coat', 'powder', 25.2),
  rel('drill', 'blade', 25.4),
  rel('powder', 'spray', 25.6),
  rel('std', 'blade', 25.8),
  rel('awo', 'e7', 26.0),
  rel('mwo', 'blade', 26.2),
  rel('powder', 'supplier', 26.4),
  rel('spray', 'blade', 26.6),
  rel('insp', 'blade', 26.8),
  rel('blade', 'e3', 27.0),
  rel('po', 'blade', 27.2),
  rel('po', 'm-comb', 27.3, 27.65, 28.8, 0.6),
  rel('stock', 'blade', 27.6, 28.6, 28.8, 0.6),
  rel('po', 'supplier', 28.0, 28.6, 28.8, 0.6),
];

// 库存 → 叶片 eases in over 0.1 s, runs at a constant 1.2 per second and eases
// out over the last 0.2333 s, so it is at exactly 42 % when 28.0 comes.
const STOCK_UP = 0.1;
const STOCK_DOWN = (0.29 * STOCK_UP + 0.02) / 0.21;
const STOCK_SPEED = 1 / (1 - STOCK_UP / 2 - STOCK_DOWN / 2);
function stockProgress(tau: number) {
  if (tau <= 0) return 0;
  if (tau >= 1) return 1;
  const a = STOCK_UP, b = STOCK_DOWN, v = STOCK_SPEED;
  if (tau < a) return v * a * smootherIntegral(tau / a);
  if (tau <= 1 - b) return v * (a / 2 + (tau - a));
  const u = (tau - (1 - b)) / b;
  return v * (a / 2 + (1 - b - a) + b * (u - smootherIntegral(u)));
}

export function relProgress(r: RelPlan, t: number) {
  if (r.from === 'stock' && r.to === 'blade') return stockProgress((t - r.start) / (r.end - r.start));
  return smootherAt(t, r.start, r.end);
}

export const HIGHLIGHT_IN: [number, number] = [27.65, 27.95];
export const HIGHLIGHT_OUT: [number, number] = [28.8, 29.4];
/** Combustor highlight, PO tag, chip and fresh ring all share this amount. */
export function highlightAt(t: number) {
  return smootherAt(t, HIGHLIGHT_IN[0], HIGHLIGHT_IN[1]) * (1 - smootherAt(t, HIGHLIGHT_OUT[0], HIGHLIGHT_OUT[1]));
}
/** Strength of a flash train at t: the strongest of the flashes under way. */
export function flashAt(times: number[], spec: { amp: number; dur: number }, t: number) {
  let a = 0;
  for (const T of times) {
    const p = seg(t, T, T + spec.dur);
    if (p > 0 && p < 1) a = Math.max(a, Math.sin(Math.PI * p) * spec.amp);
  }
  return a;
}
/** Rotor speed as a share of cruise: the derivative of the 21.6 angle formula. */
export function rotorSpeed(t: number) {
  if (t <= 22.0 || t >= 28.0) return 0;
  if (t < 23.2) return smoother((t - 22.0) / 1.2);
  if (t <= 26.0) return 1;
  return 1 - smoother((t - 26.0) / 2);
}
/** A line landing on the first-stage blade flashes the ring; on engine seven, the whole engine. */
export const RING_FLASHES = REL_PLAN.filter(r => r.to === 'blade').map(r => r.end);
export const ENGINE_FLASHES = REL_PLAN.filter(r => r.to === 'e7').map(r => r.end);
export const RING_FLASH = { amp: 0.25, dur: 0.4 };
export const ENGINE_FLASH = { amp: 0.15, dur: 0.5 };

export const CAPTION_FADE: [number, number] = [23.0, 23.3];
const TOTAL_EDGES = edges.length;

export function netGraph(t: number) {
  const lit: string[] = [];
  const litAmount: Record<string, number> = {};
  const litEdges: [string, string][] = [];
  const fading: NonNullable<GraphState['fading']> = [];
  const hidden: [string, string][] = [];
  const drawing: NonNullable<GraphState['drawing']> = [];
  const appear: Record<string, number> = {};
  const groupAppear: Record<string, number> = {};
  const pulses: Record<string, number[]> = {};
  const progress: Record<string, number> = {};
  const shownNodes = [...TREE_NODES];

  const k = smootherAt(t, TREE_SETTLE[0], TREE_SETTLE[1]);
  if (k <= 0) {
    lit.push(...TREE_NODES);
    litEdges.push(...TREE_EDGES);
  } else if (k < 1) {
    for (const id of TREE_NODES) litAmount[id] = 1 - k;
    for (const [from, to] of TREE_EDGES) fading.push({ from, to, amount: 1 - k, width: 1.5 });
  }
  if (t >= E3_START) shownNodes.push('e3');
  const e3 = smootherAt(t, E3_START, E3_START + 0.4);
  if (e3 < 1) appear.e3 = e3;
  for (const b of BIZ_PLAN) {
    if (t >= b.start) shownNodes.push(b.id);
    const a = smootherAt(t, b.start, b.start + NODE_FADE);
    if (a < 1) appear[b.id] = a;
  }
  for (const [id, start] of Object.entries(GROUP_START)) {
    const a = smootherAt(t, start, start + NODE_FADE);
    if (a < 1) groupAppear[id] = a;
  }

  let done = TOTAL_EDGES - REL_PLAN.length;
  const sourceLit: Record<string, number> = {};
  for (const r of REL_PLAN) {
    const p = relProgress(r, t);
    progress[`${r.from}>${r.to}`] = p;
    if (p >= 1) done++;
    if (p <= 0) { hidden.push([r.from, r.to]); continue; }
    if (t < r.litUntil) drawing.push({ from: r.from, to: r.to, progress: Math.min(1, p) });
    else {
      const amount = 1 - smootherAt(t, r.litUntil, r.litUntil + r.fade);
      if (amount > 0) fading.push({ from: r.from, to: r.to, amount, width: 1.6 });
    }
    // The node a line starts from is lit while that line is being laid.
    const on = smootherAt(t, r.start, r.start + 0.15) * (1 - smootherAt(t, r.litUntil, r.litUntil + r.fade));
    sourceLit[r.from] = Math.max(sourceLit[r.from] ?? 0, on);
  }
  const h = highlightAt(t);
  sourceLit['m-comb'] = Math.max(sourceLit['m-comb'] ?? 0, h);
  for (const [id, a] of Object.entries(sourceLit)) {
    if (a >= 1) lit.push(id);
    else if (a > 0) litAmount[id] = Math.max(litAmount[id] ?? 0, a);
  }
  // Two lines can land on the blade less than a flash apart; each gets its ring.
  for (const [id, times, spec] of [['blade', RING_FLASHES, RING_FLASH], ['e7', ENGINE_FLASHES, ENGINE_FLASH]] as const) {
    for (const T of times) {
      const v = seg(t, T, T + spec.dur);
      if (v > 0 && v < 1) (pulses[id] ??= []).push(v);
    }
  }

  const n = shownNodes.length;
  const counter = t >= 28.0 && t < 29.0 ? `${n} 个节点 · ${done} / ${TOTAL_EDGES} 条关系` : `${n} 个节点 · ${done} 条关系`;
  const state: GraphState = {
    focus: false,
    relStyle: 'strong',
    lit,
    litEdges,
    chip: h > 0 ? { po: { text: 'PO-26-1187' } } : {},
    status: {},
    timing: [],
    fresh: h > 0 ? ['m-comb'] : [],
    hidden,
    drawing,
    counter,
    appear,
    groupAppear,
    litAmount,
    fading,
    pulses,
  };
  if (h > 0 && h < 1) { state.chipAmount = { po: h }; state.freshAmount = { 'm-comb': h }; }
  return { state, nodes: shownNodes, progress, done };
}
