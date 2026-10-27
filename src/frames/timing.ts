// Shared timeline helpers for the timed clips. Everything is a pure function
// of t, so a frame can be rendered by seeking straight to it.

export const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const seg = (t: number, a: number, b: number) => clamp((t - a) / (b - a));
export const ease = (p: number) => p * p * p * (p * (p * 6 - 15) + 10);
export const easeOut = (p: number) => 1 - (1 - p) ** 3;
// Deterministic jitter so a re-render of the same frame is identical.
export const noise = (n: number) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
// Bump that rises to 1 and falls back to 0 inside [a, b].
export const bump = (t: number, a: number, b: number) => { const p = seg(t, a, b); return p <= 0 || p >= 1 ? 0 : Math.sin(Math.PI * p); };

// Numbers flicker through values before landing, like a count still coming in.
export function tick(final: number, t: number, start: number, dur = 0.45) {
  const p = seg(t, start, start + dur);
  if (p >= 1) return final;
  const frame = Math.floor(t * 60);
  return Math.max(0, Math.min(final, Math.round(final * easeOut(p) + (noise(frame + final) - 0.5) * final * 0.6 * (1 - p))));
}

const beat = (ch: string, perChar: number, seed: number, i: number) =>
  perChar * (0.55 + 0.9 * noise(seed + i)) * ('，。？、·'.includes(ch) ? 2.2 : 1);

// Characters typed by t: uneven keystrokes, a longer beat after punctuation.
export function typed(text: string, t: number, start: number, perChar: number, seed: number) {
  let clock = start, count = 0;
  for (const ch of text) {
    clock += beat(ch, perChar, seed, count);
    if (t < clock) break;
    count++;
  }
  return [...text].slice(0, count).join('');
}
export const typingEnd = (text: string, start: number, perChar: number, seed: number) => {
  let clock = start, i = 0;
  for (const ch of text) { clock += beat(ch, perChar, seed, i); i++; }
  return clock;
};
/** The moment each character appears, for the sound events. */
export function typedTimes(text: string, start: number, perChar: number, seed: number) {
  let clock = start, i = 0;
  const out: number[] = [];
  for (const ch of text) { clock += beat(ch, perChar, seed, i); i++; out.push(clock); }
  return out;
}

export const appear = (t: number, at: number, dur = 0.32) => {
  const p = ease(seg(t, at, at + dur));
  return `opacity:${p.toFixed(3)};transform:translateY(${((1 - p) * 8).toFixed(2)}px)`;
};
