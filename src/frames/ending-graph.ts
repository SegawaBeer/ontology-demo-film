// The ending's graph (主时间轴二 第三节, 9.4, 9.5), global t 101–120. Pure functions of t,
// shared by frame=film (101–103) and frame=ending (103–120).
import { nodes, edges, groups, type GraphState } from './data';
import { NET_GRAPH } from './net';
import { seg, ease } from './timing';

export const BACK = [101.0, 103.0] as const;       // three columns back to the split view
export const RELIGHT = [103.0, 104.2] as const;    // the four paths draw again, all at once
export const FLASH = [105.0, 105.6] as const;      // the blade node flashes and pulses
export const FADE = [105.6, 111.4] as const, FADE_DUR = 0.5;
export const OPEN_STYLE_AT = 112.0;

const DISPOSAL = { id: 'disposal', x: 186, y: 1040, label: '处置单', kind: 'biz' as const, group: 'qa' as const, anchor: 'right' as const };
/** The resting net with the disposal node question three added (35 nodes, 36 links). */
export const REST: GraphState = {
  ...NET_GRAPH, counter: undefined, spawnedPlain: true,
  spawned: [{ node: DISPOSAL, edges: [['disposal', 'blade', 0.22]], appear: 1 }],
};

/** 101–103: lit links and nodes, chips, status colours and the green transfer fade; links back to the net's strong style. */
export function graphBack(t: number, q4End: GraphState): GraphState {
  const k = ease(seg(t, BACK[0], BACK[1]));
  if (k >= 1) return REST;
  const chipAmount: Record<string, number> = {}, statusAmount: Record<string, number> = {};
  // Chips go first, before the resting links under them brighten past 0.3 (as chipFade in clip-q12).
  const chipK = 1 - ease(seg(t, BACK[0], BACK[0] + 0.4));
  for (const id of Object.keys(q4End.chip)) chipAmount[id] = chipK;
  for (const id of Object.keys(q4End.status)) statusAmount[id] = 1 - k;
  return {
    ...q4End, relStyle: 'strong', relMix: 1 - k, release: k, dimLevel: 0.22 + 0.78 * k, chipAmount, statusAmount,
    toneEdges: (q4End.toneEdges ?? []).map(e => ({ ...e, amount: (e.amount ?? 1) * (1 - k) })),
  };
}

// The four questions' paths, only along relations in the list (9.4), each in walking order.
const tree = (...ids: string[]) => ids.slice(1).map((id, i) => [ids[i], id] as [string, string]);
const MODULES = nodes.filter(n => n.kind === 'module').map(n => n.id);
export const PATHS: [string, string][][] = [
  [['design', 'blade'], ['drill', 'blade'], ['std', 'blade'], ['mwo', 'blade'], ['po', 'blade']],
  [...MODULES.map(m => ['e7', m] as [string, string]), ['m-comb', 'po'], ['po', 'supplier'], ['awo', 'e7']],
  [...tree('coat', 'powder', 'spray', 'blade', 'c-t1', 'm-turb', 'e7'), ['blade', 'e3']],
  [...tree('e7', 'm-turb', 'c-t1', 'blade', 'stock'), ['blade', 'insp'], ...tree('blade', 'spray', 'powder')],
];
const key = (a: string, b: string) => [a, b].sort().join('|');
const pathEdges = [...new Map(PATHS.flat().map(e => [key(...e), e])).values()];
const pathNodes = [...new Set(pathEdges.flat())];

// Fade order: graph hops from the blade node, farthest first; equal hops, farther on screen first.
const all = [...nodes, DISPOSAL];
const links = [...edges.map(e => [e.from, e.to] as [string, string]), ['disposal', 'blade'] as [string, string]];
const hops = new Map<string, number>([['blade', 0]]);
for (let frontier = ['blade']; frontier.length;) {
  const next: string[] = [];
  for (const id of frontier) for (const [a, b] of links) {
    const o = a === id ? b : b === id ? a : null;
    if (o && !hops.has(o)) { hops.set(o, hops.get(id)! + 1); next.push(o); }
  }
  frontier = next;
}
const blade = nodes.find(n => n.id === 'blade')!;
const order = all.filter(n => n.id !== 'blade')
  .sort((p, q) => (hops.get(q.id)! - hops.get(p.id)!) || (Math.hypot(q.x - blade.x, q.y - blade.y) - Math.hypot(p.x - blade.x, p.y - blade.y)));
const fadeStart = new Map(order.map((n, i) => [n.id, FADE[0] + (FADE[1] - FADE[0]) * i / (order.length - 1)]));
const appearOf = (id: string, t: number) => id === 'blade' ? 1 : 1 - ease(seg(t, fadeStart.get(id)!, fadeStart.get(id)! + FADE_DUR));

/** frame=open's graph: the blade node alone, lit (the ending lands on it). */
export const OPEN_GRAPH: GraphState = {
  focus: false, lit: ['blade'], litEdges: [], chip: {}, status: {}, timing: [],
  only: ['blade'], sub: { blade: '×1' }, appear: { blade: 1 }, counter: '1 个节点 · 0 条关系',
};

/** 103–120. `bladesLeft`: first-stage blades still on the ring in the 3D column (100 down to 1). */
export function endingGraphAt(t: number, bladesLeft: number): GraphState {
  if (t >= OPEN_STYLE_AT) return OPEN_GRAPH;
  if (t <= RELIGHT[0]) return REST;
  // The paths light up over their resting links (a lit stroke fading in on top), so
  // nothing underneath ever disappears.
  const p = ease(seg(t, RELIGHT[0], RELIGHT[1]));
  // Path nodes take a lit copy as the lines reach them; the blade becomes lit outright on its flash.
  const bladeLit = t >= FLASH[0];
  const litAmount: Record<string, number> = {};
  for (const id of pathNodes) if (!(id === 'blade' && bladeLit)) litAmount[id] = ease(seg(t, RELIGHT[1] - 0.5, RELIGHT[1]));
  const pulse: Record<string, number> = {};
  if (t > FLASH[0] && t < FLASH[1]) pulse.blade = seg(t, FLASH[0], FLASH[1]);
  const appear: Record<string, number> = {}, edgeAlpha: Record<string, number> = {}, groupAppear: Record<string, number> = {};
  let nodesLeft = 0, linksLeft = 0;
  for (const n of all) { const a = appearOf(n.id, t); if (a < 1) appear[n.id] = a; if (a > 0) nodesLeft++; }
  for (const [a, b] of links) { const v = Math.min(appearOf(a, t), appearOf(b, t)); if (v < 1) edgeAlpha[`${a}>${b}`] = v; if (v > 0) linksLeft++; }
  const fading = pathEdges.map(([from, to]) => ({ from, to, amount: p * Math.min(appearOf(from, t), appearOf(to, t)) })).filter(f => f.amount > 0);
  for (const g of groups) { const v = Math.max(...all.filter(n => n.group === g.id).map(n => appearOf(n.id, t))); if (v < 1) groupAppear[g.id] = v; }
  const captionAppear = Math.max(...nodes.filter(n => n.kind === 'component').map(n => appearOf(n.id, t)));
  const spawnAppear = appearOf('disposal', t);
  return {
    ...REST, lit: bladeLit ? ['blade'] : [], fading, litAmount, pulse, appear, edgeAlpha, groupAppear,
    captionAppear: captionAppear < 1 ? captionAppear : undefined,
    spawned: spawnAppear > 0 ? [{ ...REST.spawned![0], appear: spawnAppear }] : [],
    sub: { blade: `×${bladesLeft}` }, counter: `${nodesLeft} 个节点 · ${linksLeft} 条关系`,
  };
}
