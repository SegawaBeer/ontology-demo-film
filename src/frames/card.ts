// frame=card&id=N&bg=<png>: the transition title cards (脚本/字幕方案-v1.1.md 第二节), cut into
// the film when it is assembled. u runs from 0 to the card's length D: __start = 0,
// __duration = D, __seek(u) like the other pages, and every frame is a pure function of u.
// bg is the film frame at the insertion point (3840×2160), laid over the whole 1920×1080 frame.
// The fade-out ends on the card's last exported frame (u = D − 1/60), so that frame is the
// background picture alone and the film carries on from it.
import { seg, ease } from './timing';

type Card = { label?: string; alert?: string; title: string; sub?: string; dur: number };
/** Copied from 字幕方案-v1.1 2.1, word for word. `alert` is the part of the label in status red. */
export const CARDS: readonly Card[] = [
  { label: '航空发动机制造 · 本体演示', title: '一枚叶片，牵动整个工厂', dur: 2.4 },
  { title: '这张网，就是本体', sub: '接下来一个夜里，四个部门都来查它', dur: 2.4 },
  { label: '01 · 研发 · 02:07', title: '改一个设计，会牵动哪里？', dur: 2.0 },
  { label: '02 · 总装 · 02:11', title: '明早九点，能上试车台吗？', dur: 2.0 },
  { label: '03 · 质量 · 02:15 · ', alert: '自动提示', title: '一批涂层粉末，杂质超标', dur: 2.0 },
  { label: '04 · 供应链 · 02:24', title: '缺的 16 枚，最快何时补齐？', dur: 2.0 },
  { label: '早上 09:00', title: '7 号发动机，按时上试车台', sub: '一个夜里，四个部门，查的是同一张网', dur: 2.4 },
];

const FPS = 60;
const SCRIM = [0, 0.3] as const, SCRIM_MAX = 0.8;
const RULE = [0.25, 0.6] as const;
const WIPE = [0.45, 0.95] as const, SOFT = 48;   // px: the wipe's soft edge
const SUB = [0.8, 1.1] as const;
const OUT = 0.35;
const TONE = { t: 0.25, kind: 'tone', gain: 0.35, src: '3d' } as const;

function el(cls: string, text?: string) {
  const d = document.createElement('div');
  d.className = cls;
  if (text) d.textContent = text;
  return d;
}

export async function mountCard() {
  const params = new URLSearchParams(location.search);
  const id = Number(params.get('id') ?? 0);
  const card = CARDS[id];
  if (!card) throw new Error(`frame=card: no card ${params.get('id')}`);
  const D = card.dur;

  const root = el('card');
  document.querySelector('#frame')!.append(root);
  const bg = params.get('bg');
  if (bg) {
    const img = new Image();
    img.className = 'card-bg';
    img.src = bg;
    root.append(img);
    await img.decode();
  }
  const scrim = el('card-scrim');
  const stack = el('card-stack');
  let label: HTMLElement | null = null;
  if (card.label) {
    label = el('card-label', card.label);
    if (card.alert) {
      const red = document.createElement('span');
      red.className = 'alert';
      red.textContent = card.alert;
      label.append(red);
    }
    stack.append(label);
  }
  const rule = el('card-rule');
  const title = el('card-title', card.title);
  const sub = card.sub ? el('card-sub', card.sub) : null;
  stack.append(rule, title, ...(sub ? [sub] : []));
  root.append(scrim, stack);
  await document.fonts.load('20px "Plex Mono"');
  await document.fonts.ready;

  // Label and title are wiped by one edge that crosses the wider of the two.
  const wiped = [label, title].filter((e): e is HTMLElement => e !== null);
  const widths = wiped.map(e => e.offsetWidth);
  const span = Math.max(...widths);

  function seek(u: number) {
    let out = 1 - ease(seg(u, D - OUT, D - 1 / FPS));
    if (out < 1e-6) out = 0;
    const cover = id === 0 ? 1 : SCRIM_MAX * ease(seg(u, SCRIM[0], SCRIM[1]));
    scrim.style.opacity = (cover * out).toFixed(4);
    stack.style.display = out === 0 ? 'none' : '';
    rule.style.opacity = out.toFixed(4);
    rule.style.transform = `scaleX(${ease(seg(u, RULE[0], RULE[1])).toFixed(4)})`;
    const w = ease(seg(u, WIPE[0], WIPE[1]));
    const edge = w * (span + SOFT);
    wiped.forEach((e, i) => {
      const local = edge - (span - widths[i]) / 2;
      const mask = w >= 1 ? 'none' : `linear-gradient(90deg, #000 ${(local - SOFT).toFixed(2)}px, transparent ${local.toFixed(2)}px)`;
      e.style.setProperty('mask-image', mask);
      e.style.setProperty('-webkit-mask-image', mask);
      e.style.opacity = out.toFixed(4);
    });
    if (sub) sub.style.opacity = (ease(seg(u, SUB[0], SUB[1])) * out).toFixed(4);
  }

  const w = window as unknown as Record<string, unknown>;
  let driven = false;
  w.__seek = (u: number) => { driven = true; seek(u); };
  w.__start = 0;
  w.__duration = D;
  w.__events = [{ ...TONE }];
  const hold = params.get('t');
  if (hold !== null) { seek(Number(hold)); return; }
  seek(0);
  if (params.get('play') === '0') return;
  const start = performance.now();
  const loop = (now: number) => {
    if (driven) return;
    seek(((now - start) / 1000) % (D + 1.0));
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}
