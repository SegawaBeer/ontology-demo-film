import { nodes, edges, groups, captions, fleetBlocks, type GraphEdge, type GraphNode, type GraphState, type Tone } from './data';

const NS = 'http://www.w3.org/2000/svg';
const toneVar: Record<Tone, string> = { red: 'var(--red)', amber: 'var(--amber)', green: 'var(--green)' };

function el<K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number> = {}, parent?: Element) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  parent?.append(node);
  return node;
}

const radius: Record<GraphNode['kind'], number> = { engine: 7, module: 4.5, component: 2.8, part: 6.5, biz: 5 };

function treePath(a: GraphNode, b: GraphNode) {
  const mid = a.y + (b.y - a.y) * 0.5;
  if (Math.abs(a.x - b.x) < 0.5) return `M${a.x} ${a.y + radius[a.kind]} V${b.y - radius[b.kind]}`;
  const r = Math.min(5, Math.abs(a.x - b.x) / 2);
  const dir = b.x > a.x ? 1 : -1;
  return `M${a.x} ${a.y + radius[a.kind]} V${mid - r} Q${a.x} ${mid} ${a.x + dir * r} ${mid} H${b.x - dir * r} Q${b.x} ${mid} ${b.x} ${mid + r} V${b.y - radius[b.kind]}`;
}

function relPath(a: { x: number; y: number }, b: { x: number; y: number }, bend = 0) {
  const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
  const dx = b.x - a.x, dy = b.y - a.y;
  return `M${a.x} ${a.y} Q${mx - dy * bend} ${my + dx * bend} ${b.x} ${b.y}`;
}

// A link walked from `a` to `b`; `forward` is false when `a` is the edge's own `to` end.
function linkPath(e: GraphEdge, a: { x: number; y: number }, b: { x: number; y: number }, forward: boolean) {
  if (!e.via) return relPath(a, b, forward ? e.bend : -(e.bend ?? 0));
  const [x1, y1, x2, y2] = e.via;
  return forward ? `M${a.x} ${a.y} C${x1} ${y1} ${x2} ${y2} ${b.x} ${b.y}` : `M${a.x} ${a.y} C${x2} ${y2} ${x1} ${y1} ${b.x} ${b.y}`;
}

// The same polyline walked from the other end, so a tree edge can be drawn upward.
function reversePath(svg: SVGSVGElement, d: string) {
  const probe = el('path', { d }, svg);
  const length = probe.getTotalLength();
  const points: string[] = [];
  for (let i = 0; i <= 40; i++) {
    const pt = probe.getPointAtLength(length * (1 - i / 40));
    points.push(`${pt.x.toFixed(2)} ${pt.y.toFixed(2)}`);
  }
  probe.remove();
  return `M${points.join(' L')}`;
}

function label(n: GraphNode, parent: Element, lit: boolean, sub?: string) {
  const r = radius[n.kind];
  const size = n.kind === 'engine' ? 15 : n.kind === 'part' ? 14 : n.kind === 'biz' ? 13 : n.kind === 'module' ? 12 : 10.5;
  const pos = {
    below: { x: n.x, y: n.y + r + size + 3, anchor: 'middle' },
    above: { x: n.x, y: n.y - r - 10, anchor: 'middle' },
    left: { x: n.x - r - 12, y: n.y + size * 0.36, anchor: 'end' },
    right: { x: n.x + r + 10, y: n.y + size * 0.36, anchor: 'start' },
  }[n.anchor];
  const isDigit = n.kind === 'component' && /^\d$/.test(n.label);
  el('text', {
    x: pos.x, y: pos.y, 'text-anchor': pos.anchor, 'font-size': size,
    class: isDigit ? 'mono' : '', fill: lit ? 'var(--ink)' : 'var(--ink-2)',
    'font-weight': n.kind === 'engine' || lit ? 500 : 400,
  }, parent).textContent = n.label;
  const text = sub ?? n.sub;
  if (text) {
    const y = n.anchor === 'above' ? pos.y - size - 2 : pos.y + 16;
    el('text', { x: pos.x, y, 'text-anchor': pos.anchor, 'font-size': 11, class: 'mono', fill: 'var(--ink-3)' }, parent).textContent = text;
  }
}

export function renderGraph(svg: SVGSVGElement, state: GraphState) {
  svg.innerHTML = '';
  svg.setAttribute('viewBox', '0 0 640 1080');
  const spawnedNodes = (state.spawned ?? []).map(s => s.node);
  const all = [...nodes, ...spawnedNodes];
  const only = state.only ? new Set(state.only) : null;
  const visible = only ? all.filter(n => only.has(n.id)) : all;
  const byId = new Map(all.map(n => [n.id, n]));
  const allEdges = [
    ...edges,
    ...(state.spawned ?? []).flatMap(s => s.edges.map(([from, to, bend]) => ({ from, to, kind: 'rel' as const, bend }))),
  ];
  const lit = new Set([...state.lit, ...spawnedNodes.map(n => n.id)]);
  const appearOf = new Map((state.spawned ?? []).map(s => [s.node.id, s.appear ?? 1]));
  const same = (a: string, b: string, pairs: [string, string][] = []) => pairs.some(([x, y]) => (x === a && y === b) || (x === b && y === a));
  const dimming = state.dimLevel !== undefined ? state.dimLevel < 0.999 : state.focus;
  const dimValue = state.dimLevel ?? (state.focus ? 0.22 : 1);
  const dim = state.dimLevel !== undefined ? String(state.dimLevel) : state.focus ? 'var(--dim)' : '1';
  const strong = state.relStyle === 'strong';
  const litWidth = state.edgeWidth ?? 1.5;
  const drawing = state.drawing ?? [];
  const drawingPairs = drawing.map(d => [d.from, d.to] as [string, string]);
  const spawnedPairs = (state.spawned ?? []).flatMap(s => s.edges.map(([f, t]) => [f, t] as [string, string]));
  const shownEdges = allEdges.filter(e => {
    if (same(e.from, e.to, state.hidden) || same(e.from, e.to, drawingPairs)) return false;
    if (!only) return true;
    if (!only.has(e.from) || !only.has(e.to)) return false;
    return (state.onlyEdges ?? []).some(([a, b]) => same(a, b, [[e.from, e.to]]));
  });

  el('text', { x: 32, y: 64, 'font-size': 12, class: 'mono', fill: 'var(--ink-3)', 'letter-spacing': '0.14em' }, svg).textContent = '对象与关系';
  el('text', { x: 608, y: 64, 'font-size': 12, class: 'mono', fill: 'var(--ink-3)', 'text-anchor': 'end' }, svg)
    .textContent = state.counter ?? `${visible.length} 个节点 · ${allEdges.length} 条关系`;
  el('line', { x1: 32, x2: 608, y1: 84, y2: 84, stroke: 'var(--rule)' }, svg);

  for (const g of only ? [] : groups) {
    const shown = state.groupAppear?.[g.id];
    if (shown !== undefined && shown <= 0) continue;
    const gLit = all.some(n => n.group === g.id && lit.has(n.id));
    let fill = gLit || strong ? 'var(--ink-2)' : 'var(--ink-3)';
    // Blends: the net's strong style easing into the soft one, and lit groups easing back.
    const toSoft = state.relMix !== undefined && !gLit ? state.relMix : state.release !== undefined && gLit ? state.release : null;
    if (toSoft !== null && toSoft > 0 && toSoft < 1) fill = `color-mix(in srgb, var(--ink-2) ${(100 * (1 - toSoft)).toFixed(2)}%, var(--ink-3))`;
    else if (toSoft !== null && toSoft >= 1) fill = 'var(--ink-3)';
    const t = el('text', { x: g.x, y: g.y, 'font-size': 12, 'letter-spacing': '0.12em', 'text-anchor': g.align, fill }, svg);
    t.textContent = g.label;
    if (!gLit && dimming) t.style.opacity = String(0.5 + 0.5 * Math.max(0, (dimValue - 0.22) / 0.78));
    if (shown !== undefined && shown < 1) t.style.opacity = String(shown);
  }
  for (const c of only ? captions.filter(x => (state.captions ?? []).includes(x.text)) : captions) {
    if (state.captionAppear !== undefined && state.captionAppear <= 0) continue;
    const t = el('text', { x: c.x, y: c.y + 12, 'font-size': 10.5, 'text-anchor': 'middle', fill: 'var(--ink-3)' }, svg);
    t.textContent = c.text;
    t.style.opacity = state.captionAppear !== undefined && state.captionAppear < 1 ? String(+dim * state.captionAppear) : dim;
  }

  const dimLayer = el('g', {}, svg);
  dimLayer.style.opacity = dim;
  const litLayer = el('g', {}, svg);
  const mix = state.relMix;
  const release = state.release ?? 0;
  const releasing = state.release !== undefined;
  for (const e of shownEdges) {
    if ((state.edgeAlpha?.[`${e.from}>${e.to}`] ?? 1) <= 0) continue;
    const a = byId.get(e.from)!, b = byId.get(e.to)!;
    const lit = same(e.from, e.to, state.litEdges) || same(e.from, e.to, spawnedPairs);
    // While releasing, a lit link is drawn unlit underneath and lit on top, fading out.
    for (const on of releasing && lit ? (release < 1 ? [false, true] : [false]) : [lit]) {
      let relStroke = strong ? 'var(--tree)' : 'var(--rel)';
      let dash = strong ? '3 3' : '2 4';
      if (mix !== undefined && mix > 0 && mix < 1) {
        relStroke = `color-mix(in srgb, var(--tree) ${(100 * (1 - mix)).toFixed(2)}%, var(--rel))`;
        dash = `${(3 - mix).toFixed(3)} ${(3 + mix).toFixed(3)}`;
      } else if (mix !== undefined) {
        relStroke = mix >= 1 ? 'var(--rel)' : 'var(--tree)';
        dash = mix >= 1 ? '2 4' : '3 3';
      }
      const path = el('path', {
        d: e.kind === 'tree' ? treePath(a, b) : linkPath(e, a, b, true), fill: 'none',
        stroke: on ? 'var(--lit)' : e.kind === 'tree' ? 'var(--tree)' : relStroke,
        'stroke-width': on ? litWidth : 1,
        'stroke-dasharray': e.kind === 'rel' && !on ? dash : 'none',
      }, on ? litLayer : dimLayer);
      path.setAttribute('data-edge', `${e.from}>${e.to}`);
      const appear = Math.min(appearOf.get(e.from) ?? 1, appearOf.get(e.to) ?? 1);
      if (appear < 1) path.style.opacity = String(Math.max(0, appear));
      if (releasing && lit && on) path.style.opacity = String(1 - release);
      const ea = state.edgeAlpha?.[`${e.from}>${e.to}`];
      if (ea !== undefined && ea < 1) path.style.opacity = String(Math.max(0, ea) * +(path.style.opacity || 1));
    }
  }

  // Edges being laid down right now: a partial stroke with a bright head.
  for (const d of drawing) {
    if (d.progress <= 0) continue;
    const e = allEdges.find(x => same(x.from, x.to, [[d.from, d.to]]))!;
    const a = byId.get(d.from)!, b = byId.get(d.to)!;
    const forward = e.from === d.from;
    const dpath = e.kind === 'tree'
      ? (forward ? treePath(a, b) : reversePath(svg, treePath(b, a)))
      : linkPath(e, a, b, forward);
    const ink = d.tone ? toneVar[d.tone] : 'var(--lit)';
    const path = el('path', { d: dpath, fill: 'none', stroke: ink, 'stroke-width': state.edgeWidth ?? 1.6 }, litLayer);
    path.setAttribute('data-draw', `${d.from}>${d.to}`);
    const length = path.getTotalLength();
    const p = Math.min(1, d.progress);
    path.setAttribute('stroke-dasharray', `${length * p} ${length}`);
    if (p < 1) {
      const head = path.getPointAtLength(length * p);
      el('circle', { cx: head.x, cy: head.y, r: 6, fill: ink, opacity: 0.16 }, litLayer);
      el('circle', { cx: head.x, cy: head.y, r: 2.6, fill: ink }, litLayer).setAttribute('data-head', `${d.from}>${d.to}`);
    }
  }
  for (const te of state.toneEdges ?? []) {
    const e = allEdges.find(x => same(x.from, x.to, [[te.from, te.to]]));
    if (!e) continue;
    const a = byId.get(te.from)!, b = byId.get(te.to)!;
    const forward = e.from === te.from;
    const d = e.kind === 'tree' ? (forward ? treePath(a, b) : reversePath(svg, treePath(b, a))) : linkPath(e, a, b, forward);
    if ((te.amount ?? 1) <= 0) continue;
    const tp = el('path', { d, fill: 'none', stroke: toneVar[te.tone], 'stroke-width': litWidth }, litLayer);
    tp.setAttribute('data-edge', `${te.from}>${te.to}`);
    if (te.amount !== undefined && te.amount < 1) tp.style.opacity = String(te.amount);
  }

  // Finished edges whose lit stroke is fading back to the resting look.
  for (const f of state.fading ?? []) {
    if (f.amount <= 0) continue;
    const e = allEdges.find(x => same(x.from, x.to, [[f.from, f.to]]));
    if (!e) continue;
    const a = byId.get(f.from)!, b = byId.get(f.to)!;
    const forward = e.from === f.from;
    const d = e.kind === 'tree'
      ? (forward ? treePath(a, b) : reversePath(svg, treePath(b, a)))
      : linkPath(e, a, b, forward);
    const path = el('path', { d, fill: 'none', stroke: 'var(--lit)', 'stroke-width': f.width ?? litWidth }, litLayer);
    path.style.opacity = String(Math.min(1, f.amount));
  }

  for (const t of state.timing) {
    el('text', { x: t.x, y: t.y, 'font-size': 10.5, class: 'mono', fill: 'var(--lit)', opacity: releasing ? 0.85 * (1 - release) : 0.85 }, litLayer).textContent = t.text;
  }

  const fresh = new Set(state.fresh ?? []);
  // `extras`: fresh ring, pulses and chip (style-frames' lit copy leaves them out).
  // `plain`: drawn without its status colour (film-main's unlit layer under a releasing node).
  const drawNode = (n: GraphNode, on: boolean, g: SVGGElement, extras = true, plain = false) => {
    const r = radius[n.kind];
    const tone = plain ? undefined : state.status[n.id];
    const ring = tone ? toneVar[tone] : on ? 'var(--lit)' : 'var(--node-ring)';
    if (on && n.kind !== 'component') el('circle', { cx: n.x, cy: n.y, r: r + 6, fill: tone ? toneVar[tone] : 'var(--lit)', opacity: 0.12 }, g);
    if (extras && fresh.has(n.id)) {
      const ringEl = el('circle', { cx: n.x, cy: n.y, r: r + 11, fill: 'none', stroke: tone ? toneVar[tone] : 'var(--lit)', 'stroke-width': 1, opacity: 0.45 }, g);
      const k = state.freshAmount?.[n.id];
      if (k !== undefined && k < 1) ringEl.setAttribute('opacity', String(0.45 * Math.max(0, k)));
    }
    const pulse = state.pulse?.[n.id];
    for (const v of extras ? [...(pulse !== undefined ? [pulse] : []), ...(state.pulses?.[n.id] ?? [])] : []) {
      if (v <= 0 || v >= 1) continue;
      el('circle', { cx: n.x, cy: n.y, r: r + 4 + 18 * v, fill: 'none', stroke: tone ? toneVar[tone] : 'var(--lit)', 'stroke-width': 1.4, opacity: 0.7 * (1 - v) }, g);
    }
    if (n.kind === 'biz') {
      el('circle', { cx: n.x, cy: n.y, r, fill: 'var(--bg-col)', stroke: ring, 'stroke-width': on ? 1.6 : 1.1 }, g);
    } else if (n.kind === 'part') {
      el('circle', { cx: n.x, cy: n.y, r: r + 3.5, fill: 'none', stroke: ring, 'stroke-width': 1 }, g);
      el('circle', { cx: n.x, cy: n.y, r, fill: on ? ring : 'var(--node)', stroke: ring, 'stroke-width': 1.2 }, g);
    } else {
      el('circle', { cx: n.x, cy: n.y, r, fill: on ? ring : 'var(--node)', stroke: ring, 'stroke-width': n.kind === 'engine' ? 1.5 : 1.1 }, g);
    }
    label(n, g, on, state.sub?.[n.id]);
    const chip = extras && !(releasing && lit.has(n.id) && !on) ? state.chip[n.id] : undefined;
    if (chip) {
      const fill = chip.tone ? toneVar[chip.tone] : 'var(--lit)';
      let text!: SVGTextElement;
      if (n.kind === 'engine') {
        text = el('text', { x: n.x + (chip.dx ?? 0), y: n.y + r + 20 + (chip.dy ?? 0), 'font-size': 12.5, class: 'mono', 'font-weight': 600, 'text-anchor': chip.anchor ?? 'middle', fill }, g);
        text.textContent = chip.text;
      } else {
        const toLeft = n.anchor === 'left';
        const below = n.anchor === 'below';
        // A chip text with a line break is drawn as one text element per line, 15 px apart.
        const rows = chip.text.split('\n');
        rows.forEach((row, i) => {
          text = el('text', {
            x: (below ? n.x : toLeft ? n.x - r - 12 : n.x + r + 10) + (chip.dx ?? 0), y: (below ? n.y + r + 34 : n.y + 22) + (chip.dy ?? 0) + 15 * i,
            'font-size': 11.5, class: 'mono', 'font-weight': 500, 'text-anchor': chip.anchor ?? (below ? 'middle' : toLeft ? 'end' : 'start'), fill,
          }, g);
          text.textContent = row;
          const k = state.chipAmount?.[n.id];
          if (i < rows.length - 1 && k !== undefined && k < 1) text.style.opacity = String(Math.max(0, k));
        });
      }
      const k = state.chipAmount?.[n.id];
      if (k !== undefined && k < 1) text.style.opacity = String(Math.max(0, k));
    }
  };
  for (const n of visible) {
    const on = lit.has(n.id);
    const appear = state.appear?.[n.id] ?? appearOf.get(n.id);
    if (appear !== undefined && appear <= 0) continue;
    // While releasing, a lit node is drawn plain underneath and lit on top, fading out.
    // A fading status colour: plain underneath, the coloured node on top.
    const sk = state.statusAmount?.[n.id];
    const statusFade = sk !== undefined && sk < 1 && !!state.status[n.id] && !(releasing && on);
    const layers: [boolean, number | undefined, boolean][] = releasing && on
      ? (release < 1 ? [[false, 1, true], [true, 1 - release, false]] : [[false, 1, true]])
      : statusFade ? [[on, undefined, true]] : [[on, undefined, false]];
    let g!: SVGGElement;
    for (const [o, overlay, plain] of layers) {
      g = el('g', {}, svg);
      g.setAttribute('data-node', n.id);
      const floor = state.nodeAlpha?.[n.id];
      if (dimming && !o) g.style.opacity = floor !== undefined ? String(Math.max(dimValue, floor)) : dim;
      if (overlay !== undefined) g.style.opacity = String(overlay);
      if (appear !== undefined) {
        g.style.opacity = String(appear);
        g.setAttribute('transform', `translate(${n.x} ${n.y}) scale(${0.4 + 0.6 * appear}) translate(${-n.x} ${-n.y})`);
      }
      drawNode(n, o, g, true, plain);
    }
    if (statusFade && sk! > 0) {
      const top = el('g', {}, svg);
      const base = dimming && !on ? (state.nodeAlpha?.[n.id] !== undefined ? Math.max(dimValue, state.nodeAlpha[n.id]) : dimValue) : 1;
      top.style.opacity = String(sk! * base * (appear ?? 1));
      if (appear !== undefined) top.setAttribute('transform', g.getAttribute('transform')!);
      drawNode(n, on, top, false);
    }
    // A lit copy on top, for a node crossing between lit and resting.
    const k = state.litAmount?.[n.id];
    if (!on && k !== undefined && k > 0) {
      const top = el('g', {}, svg);
      top.style.opacity = String(Math.min(1, k) * (appear ?? 1));
      if (appear !== undefined) top.setAttribute('transform', g.getAttribute('transform')!);
      drawNode(n, true, top, false);
    }
  }

  if (state.dots && (state.dots.appear ?? 1) > 0) drawDots(svg, byId.get('blade')!, state.dots);
}

// The 1,016 first-stage blades as one cell each, grouped by where they are.
// The field sits below-left of the blade node, clear of the lit query path.
// `scan` is how many cells have been checked; the last few glow as the head.
function drawDots(svg: SVGSVGElement, blade: GraphNode, dots: NonNullable<GraphState['dots']>) {
  const hitSet = new Set(dots.hits);
  const scan = dots.scan ?? Infinity;
  const g = el('g', {}, svg);
  g.style.opacity = String(dots.appear ?? 1);
  const pitch = 3.2, gap = 9, x0 = 40, rowGap = 66;
  const rows = [fleetBlocks.slice(0, 6), fleetBlocks.slice(6)];
  const y0 = 452;
  el('path', { d: `M${blade.x} ${blade.y + 10} V${y0 - 14} H${x0}`, stroke: 'var(--lit)', 'stroke-width': 1.2, fill: 'none', opacity: 0.7 }, g);
  let index = 0;
  rows.forEach((row, r) => {
    let x = x0;
    const y = y0 + r * rowGap;
    for (const block of row) {
      const c = block.key === '库' ? 4 : 10;
      let anyHit = false;
      for (let i = 0; i < block.count; i++) {
        const k = index++;
        const checked = k < scan;
        const hit = checked && hitSet.has(k);
        if (hit) anyHit = true;
        const head = checked && scan - k < 24;
        el('rect', {
          x: x + (i % c) * pitch, y: y + Math.floor(i / c) * pitch, width: 2.3, height: 2.3,
          fill: hit ? 'var(--red)' : head ? 'var(--lit)' : 'var(--ink-3)',
          opacity: hit ? 1 : head ? 0.35 + 0.55 * (1 - (scan - k) / 24) : checked ? 0.32 : 0.12,
        }, g);
      }
      el('text', {
        x: x + (c * pitch) / 2 - 1, y: y + 10 * pitch + 13, 'font-size': 10, class: 'mono', 'text-anchor': 'middle',
        fill: anyHit ? 'var(--red)' : 'var(--ink-3)',
      }, g).textContent = block.key === '库' ? '库存' : `${block.key}号`;
      x += c * pitch + gap;
    }
  });
  const t = el('text', { x: x0, y: y0 + rowGap * 2 + 8, 'font-size': 12, fill: 'var(--ink-2)' }, g);
  t.innerHTML = dots.caption;
}
