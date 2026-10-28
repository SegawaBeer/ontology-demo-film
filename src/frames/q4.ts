// Question four, 供应链 · 02:24 (主时间轴二 第二节 with 第九节), global t 86–101.
// It carries on from the question-three clip at its local 22.0. This file holds the
// timeline table and the dialog; the graph and the 3D parts follow the same table.
import { dialogParts } from './clip-q3';
import { foldHTML } from './fold';
import { clamp, seg, ease, tick, typed, typingEnd, appear } from './timing';

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
  const pick = ease(seg(t, POINTER_MOVE[1] - 0.15, POINTER_MOVE[1] + 0.1));
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
