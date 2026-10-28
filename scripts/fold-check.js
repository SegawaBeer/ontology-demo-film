() => {
  // 12.1: no sentence visible twice (both copies > 0.05), no two visible text boxes overlapping.
  const root = document.querySelector('#dialog');
  const op = el => { let o = 1; for (let e = el; e && e !== root.parentElement; e = e.parentElement) { const s = getComputedStyle(e); if (s.display === 'none' || s.visibility === 'hidden') return 0; o *= +s.opacity; } return o; };
  const items = [...root.querySelectorAll('.meta, .ask, .step .line, .answer, .trace span, .col-head span, .step .n')]
    .map(el => ({ el, o: op(el), text: el.innerText.replace(/\s+/g, ' ').trim() })).filter(x => x.o > 0.05 && x.text);
  const bad = [];
  const seen = new Map();
  for (const x of items) { if (seen.has(x.text) && !x.el.contains(seen.get(x.text).el) && !seen.get(x.text).el.contains(x.el)) bad.push(['twice', x.text.slice(0, 20)]); else seen.set(x.text, x); }
  // Fragments: the folding question split into spans counts as one line; compare spans too.
  const boxes = [];
  for (const x of items) for (const r of x.el.getClientRects()) boxes.push({ x, r });
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const a = boxes[i], b = boxes[j]; if (a.x === b.x || a.x.el.contains(b.x.el) || b.x.el.contains(a.x.el)) continue;
    const ox = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left), oy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
    if (ox > 0.5 && oy > 0.5) bad.push(['overlap', a.x.text.slice(0, 14), b.x.text.slice(0, 14), +ox.toFixed(1), +oy.toFixed(1)]); }
  return bad;
}
