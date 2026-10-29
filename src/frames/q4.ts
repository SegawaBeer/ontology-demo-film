// Question four, 供应链 · 02:24 (主时间轴二 第二节 with 第九节), global t 86–101.
// It carries on from the question-three clip at its local 22.0. This file holds the
// timeline table and the dialog; the graph and the 3D parts follow the same table.
import { dialogParts } from './clip-q3';
import type { GraphState } from './data';
import { foldHTML } from './fold';
import { clamp, seg, ease, tick, typed, typingEnd, typedTimes as typedTimesOf, appear } from './timing';

// ------------------------------------------------------------------ timeline
export const Q4_START = 86.0;
export const FOLD3 = [86.0, 87.0] as const;          // the follow-up folds into its answered look
export const META = 87.0;
export const ASK = '7 号发动机缺的 16 枚，最快什么时候补齐？';
export const TYPE = 87.3, PER_CHAR = 0.085, SEED = 61;   // seed 61 ends the typing at 89.70
export const TYPE_END = typingEnd(ASK, TYPE, PER_CHAR, SEED);
export const QUERY = 90.0;                             // typing end + 0.3
export const STEP1 = 91.4;
export const N_STOCK: [number, number, number][] = [[6, 91.4, 0.3], [10, 91.55, 0.3]];
export const PLANS = [93.8, 94.2] as const;            // the two plan cards, 0.32 s each
export const POINTER_IN = [95.1, 95.4] as const, POINTER_MOVE = [95.4, 95.8] as const, POINTER_OUT = [96.6, 96.9] as const;
export const EXEC = 95.8;                              // 执行中 · 调拨库存
export const FLY_AT = 96.0, FLY_GAP = 0.12, FLY_DUR = 0.5;   // 16 blades into the ring
/** Time blade k (0..15, in arrival order) is seated. */
export const landAt = (k: number) => FLY_AT + FLY_GAP * k + FLY_DUR;
export const GAP_TAGS_OUT = [98.4, 98.7] as const;
export const GREEN = 98.6;                             // question two's answer turns green again
export const DONE = 99.0;
const traceKeys: [number, number][] = [[90.0, 0], [90.6, 0.12], [91.2, 0.3], [91.4, 0.4], [92.7, 0.62], [93.4, 0.86], [95.8, 1]];

// ------------------------------------------------------------------ dialog
const FOLLOW_ASK_LINES = ['7 号上的 16 枚拆下停用。3 号发动机还能继续', '飞吗？'];
const FOLLOW_ANSWER = '<p class="answer">已停用 16 枚 · 3 号继续飞行 · 孔探间隔减半</p>';
const PAST_FOLLOW = `<div class="turn past"><div class="meta"><b>质量</b><span>02:17</span></div>
    <p class="ask">7 号上的 16 枚拆下停用。3 号发动机还能继续飞吗？</p>
    ${FOLLOW_ANSWER}</div>`;
export const GREEN_ANSWER = '可以按时上试车台 · 09:00';
const PLAN_TEXT = [
  ['调本库 6 枚、二号厂区 10 枚', '05:10 前到齐 · 上试车台时间不变'],
  ['合格粉末重新喷涂 16 枚', '推迟 6 天'],
];
const num = (t: number, [final, at, dur]: [number, number, number]) => tick(final, t, at, dur);
const opacity = (a: number) => a.toFixed(3);

/** Question two, red since 19.0 in the clip; from GREEN it strikes the red line and types the green one in its place. */
function q2At(t: number, red: string) {
  // 0–0.3 the red line is struck, 0.3–0.5 the old answer fades out, 0.5–0.8 its
  // second row closes up, and from 0.55 the green line types into the first row.
  // The old green line and the new one are never on screen together (主时间轴二 9.2).
  const c = t - GREEN;
  if (c < 0) return red;
  const strike = ease(seg(c, 0, 0.3));
  const old = 1 - ease(seg(c, 0.3, 0.5));
  const rows = 1 - ease(seg(c, 0.5, 0.8));
  const now = typed(GREEN_ANSWER, c, 0.55, 0.035, 71);
  const bar = ease(seg(c, 0.55, 0.8));
  const oldStyle = old > 0 ? `opacity:${opacity(old)}` : 'visibility:hidden';
  return `<div class="turn past changing" style="opacity:1.000">
      <span class="bar" style="transform:scaleY(1.000)${bar > 0 ? `;background:color-mix(in srgb, var(--green) ${(100 * bar).toFixed(1)}%, var(--red))` : ''}"></span>
      <div class="meta"><b>总装</b><span>02:11</span><span class="flag" style="opacity:1.000${bar > 0 ? `;color:color-mix(in srgb, var(--green) ${(100 * bar).toFixed(1)}%, var(--red))` : ''}">自动更新 · 02:17</span></div>
      <p class="ask">7 号发动机明早 9 点能按时上试车台吗？</p>
      <p class="answer reanswer"><span class="old-rows" style="grid-template-rows:${rows.toFixed(4)}fr"><span class="old-clip"><span class="old" style="${oldStyle}"><span class="was" style="background-size:100.0% 1px">可以按时上试车台 09:00</span><span class="now struck" style="background-size:${(strike * 100).toFixed(1)}% 1px">暂不能上试车台 · 等待 16 枚叶片</span></span></span></span><span class="now green">${now}</span></p></div>`;
}

function traceAt(t: number): [string, string] {
  if (t < QUERY) return ['已执行 2 个动作 · 更新 20 个对象 · 新建 1 个', '1.1 秒'];
  if (t >= DONE) return ['已检索 5 类对象 · 64 条关系', '0.5 秒'];
  if (t >= EXEC) return ['执行中 · 调拨库存', ''];
  let share = 1;
  for (let i = 1; i < traceKeys.length; i++) {
    const [t1, v1] = traceKeys[i], [t0, v0] = traceKeys[i - 1];
    if (t <= t1) { share = v0 + (v1 - v0) * (t - t0) / (t1 - t0); break; }
  }
  const objects = 1 + Number(t >= 90.6) + Number(t >= 91.2) + Number(t >= 92.7) + Number(t >= 93.4);
  return [`检索中 · ${objects} 类对象 · ${Math.round(64 * share)} 条关系`, `${(0.5 * share).toFixed(2)} 秒`];
}

/** The pointer: fades in below the cards, glides onto plan ①, and leaves after the click. */
function pointerHTML(t: number) {
  const a = ease(seg(t, POINTER_IN[0], POINTER_IN[1])) * (1 - ease(seg(t, POINTER_OUT[0], POINTER_OUT[1])));
  if (a <= 0) return '';
  const m = ease(seg(t, POINTER_MOVE[0], POINTER_MOVE[1]));
  const x = 300 + (150 - 300) * m, y = 118 + (44 - 118) * m;
  return `<svg class="pointer" viewBox="0 0 14 20" style="left:${x.toFixed(2)}px;top:${y.toFixed(2)}px;opacity:${opacity(a)}"><path d="M1 1 L1 16 L5 12 L8 19 L10.5 18 L7.5 11 L13 11 Z" fill="var(--ink)" stroke="var(--bg-col)" stroke-width="1"/></svg>`;
}

function plansHTML(t: number) {
  if (t < PLANS[0]) return '';
  const pick = ease(seg(t, POINTER_MOVE[1], POINTER_MOVE[1] + 0.25));   // the click lands at 95.8
  const cards = PLAN_TEXT.map(([head, note], i) => {
    if (t < PLANS[i]) return `<div class="plan" style="visibility:hidden"><b>${head}</b><span>${note}</span></div>`;
    const style = [appear(t, PLANS[i])];
    if (i === 0 && pick > 0) style.push(`border-color:color-mix(in srgb, var(--lit) ${(100 * pick).toFixed(1)}%, var(--node-ring))`);
    if (i === 1 && pick > 0) style[0] = `opacity:${opacity(1 - 0.55 * pick)}`;
    return `<div class="plan" style="${style.join(';')}"><b>${head}</b><span>${note}</span></div>`;
  });
  return `<div class="plans">${cards.join('')}${pointerHTML(t)}</div>`;
}

function q4Turn(t: number) {
  if (t < META) return '';
  const blinkOff = Math.floor(t * 2.4) % 2 === 1;
  const askText = typed(ASK, t, TYPE, PER_CHAR, SEED);
  const askDone = t >= TYPE_END;
  const cursor = !askDone || t < STEP1 ? (askDone && blinkOff ? ' typing blink-off' : ' typing') : '';
  let steps = '';
  if (t >= STEP1) {
    const live = t < PLANS[0] ? ` live${blinkOff ? ' blink-off' : ''}` : '';
    steps = `<div class="steps"><div class="step${live}" style="${appear(t, STEP1)}"><span class="n">01</span><span class="line">本库 <em>${num(t, N_STOCK[0])}</em> 枚，二号厂区 <em>${t < N_STOCK[1][1] ? 0 : num(t, N_STOCK[1])}</em> 枚</span></div></div>`;
  }
  return `<div class="turn" style="${appear(t, META, 0.2)}"><div class="meta"><b>供应链</b><span>02:24</span></div>
      <p class="ask${cursor}">${askText}</p>${steps}${plansHTML(t)}</div>`;
}

/** Dialog column for t ≥ 86. At 86.0 exactly it is clip-q3's own 22.0 markup. */
export function q4DialogHTML(input: number, clipAt22: string) {
  const t = clamp(input, Q4_START, 120);
  if (t <= FOLD3[0]) return clipAt22;
  const d = dialogParts(22);
  const u = seg(t, FOLD3[0], FOLD3[1]);
  const follow = u >= 1 ? PAST_FOLLOW : foldHTML(u, {
    meta: '<b>质量</b><span>02:17</span>', askLines: FOLLOW_ASK_LINES,
    steps: `<div class="steps">${d.actionsHTML}</div>`, answer: FOLLOW_ANSWER,
  });
  const [left, right] = traceAt(t);
  return `<div class="dialog"><header class="col-head"><span>提问</span><span>4 个部门 · 同一套对象</span></header>
    <div class="turns">${d.q1}${q2At(t, d.q2)}${d.q3Past}${follow}${q4Turn(t)}</div>
    <div class="trace"><span>${left}</span><span class="spin">${right}</span></div></div>`;
}

// ------------------------------------------------------------------ graph
// 86–87 question three's path fades back to the 0.22 dim; the disposal node and the
// statuses and chips that still hold (7 号 red, the frozen batch, the disposal) stay.
const UNLIT = [86.0, 87.0] as const;
const KEEP = new Set(['e7', 'powder', 'disposal']);
// Query path, only along relations in the list (第九节 9.4): 7 号 → 涡轮 → 叶环 → 叶片 → 库存,
// then the stock blades' inspection records and, through the spray orders, their powder.
export const hops4 = [
  { from: 'e7', to: 'm-turb', a: 90.0, b: 90.3 },
  { from: 'm-turb', to: 'c-t1', a: 90.3, b: 90.6 },
  { from: 'c-t1', to: 'blade', a: 90.6, b: 90.9 },
  { from: 'blade', to: 'stock', a: 90.9, b: 91.2 },
  { from: 'blade', to: 'insp', a: 92.0, b: 92.35 },
  { from: 'blade', to: 'spray', a: 92.1, b: 92.45 },
  { from: 'spray', to: 'powder', a: 92.45, b: 92.75 },
];
// 95.8: the transfer, green, along the same relations back to 7 号, 0.15 s a segment.
export const greenHops = [['stock', 'blade'], ['blade', 'c-t1'], ['c-t1', 'm-turb'], ['m-turb', 'e7']]
  .map(([from, to], i) => ({ from, to, a: EXEC + 0.15 * i, b: EXEC + 0.15 * (i + 1) }));
const litAt4: [string, number][] = [['e7', QUERY], ...hops4.map((h): [string, number] => [h.to, h.b])];
const pulses4: [string, number, number][] = [['e7', 90.0, 90.7], ['blade', 90.9, 91.6], ['stock', 91.2, 91.9], ['powder', 92.75, 93.45], ['e7', 98.55, 99.25]];
export const E7_GREEN = [98.4, 98.55, 98.8] as const;   // red out, then green in
const POWDER_RED_OUT = [92.45, 92.75] as const, POWDER_GREEN = [92.75, 93.0, 93.4, 93.7] as const, POWDER_RED_IN = [93.7, 94.0] as const;

export function q4GraphAt(t: number, at22: GraphState): GraphState {
  const k = ease(seg(t, UNLIT[0], UNLIT[1]));
  const lit = litAt4.filter(([, at]) => t >= at).map(([id]) => id);
  const litSet = new Set(lit);
  const nodeAlpha: Record<string, number> = {}, litAmount: Record<string, number> = {};
  // A node lit at 22.0 keeps its full opacity and a lit copy, both easing down to the dim.
  if (k < 1) for (const id of at22.lit) if (!litSet.has(id)) { nodeAlpha[id] = 0.22 + 0.78 * (1 - k); litAmount[id] = 1 - k; }
  const fading = k < 1 ? at22.litEdges.map(([from, to]) => ({ from, to, amount: 1 - k })) : [];
  const litEdges = hops4.filter(h => t >= h.b).map(h => [h.from, h.to] as [string, string]);
  const drawing = hops4.filter(h => t > h.a && t < h.b).map(h => ({ from: h.from, to: h.to, progress: ease(seg(t, h.a, h.b)) }));
  const toneEdges = greenHops.filter(h => t > h.a).map(h => ({ from: h.from, to: h.to, tone: 'green' as const, progress: ease(seg(t, h.a, h.b)) }));
  const pulse: Record<string, number> = {};
  for (const [id, a, b] of pulses4) if (t > a && t < b) pulse[id] = seg(t, a, b);

  const status: GraphState['status'] = {}, statusAmount: Record<string, number> = {};
  for (const [id, tone] of Object.entries(at22.status)) {
    if (KEEP.has(id)) status[id] = tone;
    else if (k < 1) { status[id] = tone; statusAmount[id] = 1 - k; }
  }
  const redOut = 1 - ease(seg(t, E7_GREEN[0], E7_GREEN[1])), greenIn = ease(seg(t, E7_GREEN[1], E7_GREEN[2]));
  if (t >= E7_GREEN[1]) { status.e7 = 'green'; if (greenIn < 1) statusAmount.e7 = greenIn; }
  else if (redOut < 1) statusAmount.e7 = redOut;

  const chip: GraphState['chip'] = {}, chipAmount: Record<string, number> = {};
  const gone = 1 - ease(seg(t, 86.0, 86.4));
  for (const [id, c] of Object.entries(at22.chip)) {
    if (KEEP.has(id)) chip[id] = c;
    else if (gone > 0) { chip[id] = c; chipAmount[id] = gone; }
  }
  if (t >= E7_GREEN[1]) { chip.e7 = { ...at22.chip.e7, text: '可以按时上试车台', tone: 'green' }; if (greenIn < 1) chipAmount.e7 = greenIn; }
  else if (redOut < 1) chipAmount.e7 = redOut;
  // From the first arrival the blade chip counts the seated blades up.
  const seated = Array.from({ length: 16 }, (_, k) => landAt(k)).filter(at => t >= at).length;
  // Left of the node's ×100, clear of it and of the links that leave the node downwards.
  const bladeChip = { dx: -40, anchor: 'end' as const };
  if (t >= FLY_AT) chip.blade = { text: `到位 ${seated} / 16`, tone: seated < 16 ? 'red' : 'green', ...bladeChip };
  else if (t >= 90.9) chip.blade = { text: '缺 16 枚', tone: 'red', ...bladeChip };
  if (t >= STEP1) chip.stock = { text: '本厂成品库 · 6 枚\n二号厂区 · 10 枚' };
  // Left of its node: on the right the stock and disposal links run past.
  if (t >= 92.35) chip.insp = { text: '16 枚 · 全部合格', tone: 'green', dx: -32, anchor: 'end' };
  // The frozen batch's red chip makes way for the two good batches, then comes back.
  const green = ease(seg(t, POWDER_GREEN[0], POWDER_GREEN[1])) * (1 - ease(seg(t, POWDER_GREEN[2], POWDER_GREEN[3])));
  const red = t < POWDER_GREEN[0] ? 1 - ease(seg(t, POWDER_RED_OUT[0], POWDER_RED_OUT[1])) : ease(seg(t, POWDER_RED_IN[0], POWDER_RED_IN[1]));
  if (green > 0) { chip.powder = { text: 'YSZ-2398 · YSZ-2421', tone: 'green' }; if (green < 1) chipAmount.powder = green; }
  else if (red <= 0) delete chip.powder;
  else if (red < 1) chipAmount.powder = red;

  return {
    focus: true, dimLevel: 0.22, lit, litEdges, drawing, nodeAlpha, litAmount, fading, pulse, status, statusAmount,
    chip, chipAmount, timing: [], toneEdges, spawned: at22.spawned,
  };
}

// ------------------------------------------------------------------ sound events
/** Question four's sound events (主时间轴二 9.7), global time. */
export function q4Events(settle: (n: [number, number, number]) => number) {
  type Ev = { t: number; kind: 'type' | 'line' | 'tick' | 'path' | 'slide' | 'part'; gain: number; src: 'dialog' | 'graph' | '3d'; dur?: number };
  const out: Ev[] = [];
  const add = (t: number, kind: Ev['kind'], gain: number, src: Ev['src'], dur?: number) => out.push(dur === undefined ? { t, kind, gain, src } : { t, kind, gain, src, dur });
  add(FOLD3[0], 'line', 0.3, 'dialog');
  add(86.0, 'slide', 0.45, '3d', 1.0);                     // push-in to the ring (CAM4)
  add(META, 'line', 0.4, 'dialog');
  for (const at of typedTimesOf(ASK, TYPE, PER_CHAR, SEED)) add(at, 'type', 0.32, 'dialog');
  for (const h of hops4) add(h.a, 'path', 0.5, 'graph');
  add(STEP1, 'line', 0.7, 'dialog');
  for (const n of N_STOCK) add(settle(n), 'tick', 0.5, 'dialog');
  add(STEP1, 'line', 0.35, '3d');                          // the two gap tags
  for (const at of PLANS) add(at, 'line', 0.6, 'dialog');  // one per plan card
  add(POINTER_MOVE[1], 'line', 0.45, 'dialog');            // plan ① picked
  for (const h of greenHops) add(h.a, 'path', 0.5, 'graph');
  for (let k = 0; k < 16; k++) add(landAt(k), 'part', 0.4, '3d');
  add(GREEN, 'line', 0.7, 'dialog');                       // question two's answer turns green
  return out;
}
