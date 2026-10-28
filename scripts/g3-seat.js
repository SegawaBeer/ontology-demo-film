// G3 (主时间轴二 第四节): the 16 blades flying into the ring, checked with F8's axial-section
// method. Setup samples every ring blade and disk part at rest; step(t) shifts each blade in
// flight by its own offset and compares its section with every solid ring or disk part that
// is drawn (opacity > 0.02). Overlap a blade already has in its seated place is not counted;
// for the disk only while the blade has no radial offset left (the slide along the slot).
window.__g3 = {
  setup(W) {
    const { e7, q4, clip } = window.__filmDebug;
    const X0 = -1.44, NB = Math.ceil(0.22 / W);
    const dense = (s, step) => { const geo = s.group.mesh.geometry, g = geo.getAttribute('position'), ix = geo.index, m = s.matrix.elements, out = [];
      const T = i => { const x = g.getX(i), y = g.getY(i), z = g.getZ(i); return [m[0]*x+m[4]*y+m[8]*z+m[12], m[1]*x+m[5]*y+m[9]*z+m[13], m[2]*x+m[6]*y+m[10]*z+m[14]]; };
      const n = ix ? ix.count : g.count;
      for (let t = 0; t < n; t += 3) { const A = T(ix ? ix.getX(t) : t), B = T(ix ? ix.getX(t+1) : t+1), C = T(ix ? ix.getX(t+2) : t+2);
        const L = Math.max(Math.hypot(A[0]-B[0], A[1]-B[1], A[2]-B[2]), Math.hypot(A[0]-C[0], A[1]-C[1], A[2]-C[2]), Math.hypot(B[0]-C[0], B[1]-C[1], B[2]-C[2]));
        const k = Math.max(1, Math.ceil(L / step));
        for (let i = 0; i <= k; i++) for (let j = 0; j <= k - i; j++) { const u = i/k, v = j/k, w = 1-u-v; out.push(w*A[0]+u*B[0]+v*C[0], w*A[1]+u*B[1]+v*C[1], w*A[2]+u*B[2]+v*C[2]); } }
      return out; };
    const section = (P, sx = 0, sy = 0, sz = 0) => { const lo = new Float32Array(NB).fill(9), hi = new Float32Array(NB).fill(-9);
      for (let i = 0; i < P.length; i += 3) { const b = Math.floor((P[i] + sx - X0) / W); if (b < 0 || b >= NB) continue; const r = Math.hypot(P[i+1] + sy, P[i+2] + sz); if (r < lo[b]) lo[b] = r; if (r > hi[b]) hi[b] = r; }
      return { lo, hi }; };
    const flying = new Set(clip.hit7);
    const cands = [];
    for (const [id, s] of e7.parts) {
      const comp = s.meta.component;
      if (comp !== 'turbine.stage-1-blades' && comp !== 'turbine.stage-1-disk') continue;
      cands.push({ id, comp, sec: section(dense(s, 0.0015)) });
    }
    const blades = q4.order.map(o => { const P = dense(e7.parts.get(o.id), 0.0012); return { o, P, rest: section(P) }; });
    this.F = { W, NB, X0, section, cands, blades, flying };
    return { cands: cands.length, blades: blades.length };
  },
  step(t) {
    const { e7, view, q4 } = window.__filmDebug; const F = this.F;
    const ov = (a, b, i) => Math.max(0, Math.min(a.hi[i], b.hi[i]) - Math.max(a.lo[i], b.lo[i]));
    const bad = []; let worst = 0, n = 0;
    for (const b of F.blades) {
      const k = b.o.k, start = 96.0 + 0.12 * k, land = start + 0.5;
      if (t < start || t >= land) continue;
      n++;
      const off = q4.offsetAt(b.o, t);
      const rad = Math.hypot(off.y, off.z) > 1e-9 ? off.clone().setX(0).dot(b.o.radial) : 0;
      const now = F.section(b.P, off.x, off.y, off.z);
      for (const c of F.cands) {
        if (c.id === b.o.id) continue;
        // Other blades of the 16: drawn only once seated (in flight they are checked as the moving one).
        if (F.flying.has(c.id) && !(t >= 96.0 + 0.12 * q4.order.find(o => o.id === c.id).k + 0.5)) continue;
        if (view.partOpacity(e7, c.id) <= 0.02) continue;
        const exempt = c.comp === 'turbine.stage-1-blades' || (c.comp === 'turbine.stage-1-disk' && Math.abs(rad) < 1e-6);
        for (let i = 0; i < F.NB; i++) {
          const o = ov(now, c.sec, i) - (exempt ? ov(b.rest, c.sec, i) : 0);
          if (o > worst) worst = o;
          if (o > 0.003 && bad.length < 6) bad.push([b.o.id.slice(-3), c.id.slice(-12), +(F.X0 + i * F.W).toFixed(3), +o.toFixed(4)]);
        }
      }
    }
    return { n, worst, bad };
  },
};
