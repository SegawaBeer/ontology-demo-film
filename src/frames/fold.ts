// A question folding into its answered (grey) form without two copies of any
// text on screen at once (task 主时间轴一 12.1). u runs 0..1 over the fold:
//   0.00–0.30  the answer lines fade out
//   0.30–0.70  their space closes up; the next turn below moves up with it
//   0.30–0.70  the question line shrinks 22 → 16 px and the turn dims to the grey look
//   0.62–0.80  a question that wrapped onto a second line: that part fades out,
//              the line becomes one, and the part fades back in at its end
//   0.75–1.00  the folded answer fades in where it ends up
// At u ≥ 1 the caller shows its own past-turn markup, which this converges to.
import { ease, seg } from './timing';

export type FoldParts = {
  /** Inner markup of `.meta`. */
  meta: string;
  /** The question as laid out at 22 px: one entry per line. */
  askLines: string[];
  /** The `<div class="steps">` block of the open turn. */
  steps: string;
  /** The `<p class="answer">` of the folded turn. */
  answer: string;
};

export function foldHTML(u: number, p: FoldParts) {
  const stepsAlpha = 1 - ease(seg(u, 0, 0.3));
  const close = 1 - ease(seg(u, 0.3, 0.7));
  const shrink = ease(seg(u, 0.3, 0.7));
  const size = 22 + (16 - 22) * shrink;
  const weight = shrink < 0.5 ? 500 : 400;
  const turnAlpha = 1 - 0.5 * shrink;
  const answerAlpha = ease(seg(u, 0.75, 1));
  let ask: string;
  if (p.askLines.length < 2) ask = p.askLines.join('');
  else if (u < 0.7) {
    const rest = 1 - ease(seg(u, 0.62, 0.7));
    ask = `<span class="fold-line">${p.askLines[0]}</span><br><span class="fold-line" style="opacity:${rest.toFixed(3)}">${p.askLines.slice(1).join('')}</span>`;
  } else {
    const back = ease(seg(u, 0.7, 0.8));
    ask = `<span class="fold-line">${p.askLines[0]}<span style="opacity:${back.toFixed(3)}">${p.askLines.slice(1).join('')}</span></span>`;
  }
  const answer = p.answer.replace('<p class="answer', `<p style="opacity:${answerAlpha.toFixed(3)}" class="answer`);
  return `<div class="turn folding" style="opacity:${turnAlpha.toFixed(3)}"><div class="meta">${p.meta}</div>
    <p class="ask" style="font-size:${size.toFixed(3)}px;font-weight:${weight}">${ask}</p>
    <div class="fold-slot"><div class="fold-steps" style="grid-template-rows:${close.toFixed(4)}fr"><div class="fold-clip">${stepsAlpha > 0 ? p.steps.replace('<div class="steps"', `<div class="steps" style="opacity:${stepsAlpha.toFixed(3)}"`) : p.steps.replace('<div class="steps"', '<div class="steps" style="visibility:hidden"')}</div></div>${answerAlpha > 0 ? answer : answer.replace('<p style="', '<p style="visibility:hidden;')}</div></div>`;
}
