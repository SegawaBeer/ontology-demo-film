() => {
  // 主时间轴一 12.2 / 12.3: lines over graph labels. Opacity = product over the element and its ancestors.
  const svg = document.querySelector('#graph'); const sr = svg.getBoundingClientRect();
  const op = el => { let o = 1; for (let e = el; e && e !== svg.parentElement; e = e.parentElement) { const s = getComputedStyle(e);
    if (s.display === 'none' || s.visibility === 'hidden') return 0; o *= +s.opacity; const a = e.getAttribute && e.getAttribute('opacity'); if (a !== null && a !== undefined && e !== svg) o *= +a; } return o; };
  const texts = [...svg.querySelectorAll('text')].filter(t => t.textContent.trim());
  const kind = t => { const fs = t.getAttribute('font-size'); const mono = (t.getAttribute('class') || '').includes('mono');
    if (fs === '11.5' || (fs === '12.5' && t.getAttribute('font-weight') === '600')) return 'chip';
    if (fs === '10.5' && mono && t.getAttribute('fill') === 'var(--lit)') return 'timing';
    if (t.closest('g[data-node]') && ['15', '14', '13', '12', '10.5'].includes(fs) && !mono) return 'name';
    return 'other'; };
  const boxes = texts.map(t => { const r = t.getBoundingClientRect(); return { t, k: kind(t), o: op(t), x0: r.left - sr.left - 3, y0: r.top - sr.top - 3, x1: r.right - sr.left + 3, y1: r.bottom - sr.top + 3 }; })
    .filter(b => b.o > 0.05 && (b.k === 'chip' || b.k === 'timing' || b.k === 'name'));
  const out = [];
  for (const p of svg.querySelectorAll('path')) {
    const o = op(p); if (o <= 0.3) continue;
    const stroke = p.getAttribute('stroke'); if (!stroke || stroke === 'none') continue;
    const lit = stroke === 'var(--lit)';
    const L = p.getTotalLength(); if (!L) continue;
    // A link being drawn is a dasharray "drawn rest": only the drawn part counts.
    const da = p.getAttribute('stroke-dasharray'); let upto = L;
    if (p.hasAttribute('data-draw') && da) upto = Math.min(L, parseFloat(da.split(/[ ,]+/)[0]));
    const name = p.getAttribute('data-edge') || p.getAttribute('data-draw') || (p.getAttribute('d') || '').slice(0, 24);
    const hit = new Map();
    for (let s = 0; s <= upto; s += 2) { const q = p.getPointAtLength(s);
      for (const b of boxes) { if (b.k === 'name' && !lit) continue; if (q.x >= b.x0 && q.x <= b.x1 && q.y >= b.y0 && q.y <= b.y1) hit.set(b, (hit.get(b) || 0) + 1); } }
    for (const [b, n] of hit) out.push({ line: name, lit, lineOpacity: +o.toFixed(3), text: b.t.textContent, kind: b.k, textOpacity: +b.o.toFixed(3), points: n });
  }
  return out;
}
