// Opening 3B: thin airflow lines along the engine axis while the fan turns.
// Lines are drawn only where the air can be seen: in front of the intake, and
// behind the two exits (the bypass duct's rear edge and the exhaust nozzle).
// Inside the engine every radius runs into some solid part, so nothing is
// drawn there. Behind an exit a line keeps the exit radius and opens outwards
// by 0.08 per unit. The dashes move by a fixed multiple of the rotor angle,
// so every frame is a function of t alone.
import * as THREE from 'three';
import { LineSegments2 } from 'three/examples/jsm/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/examples/jsm/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';

const FLARE = 0.08;
// Engine space, +x is the front; air runs from +x to -x. The intake pieces end
// at 2.065, just in front of the cowl (2.063) and clear of the fan's inner
// shroud (2.047), so no 0.02 slice they touch holds a solid part at their radius.
type Piece = { from: number; to: number; r0: number; r1: number };
const exit = (from: number, to: number, r: number): Piece => ({ from, to, r0: r, r1: r + FLARE * (from - to) });
export const FLOW_PATHS: { name: string; count: number; phase: number; pieces: Piece[]; hidden: number }[] = [
  // Bypass: out of the duct's rear edge (x 0.2035) above the combustor
  // injectors, which reach radius 0.772 right behind it.
  { name: 'bypass', count: 24, phase: 0, hidden: 2.065 - 0.20,
    pieces: [{ from: 2.75, to: 2.065, r0: 0.50, r1: 0.58 }, exit(0.20, -0.90, 0.79)] },
  // Core: out of the nozzle (rear edge -1.924 with its bolts), just inside its
  // lip (inner radius 0.661).
  { name: 'core', count: 18, phase: 0.5, hidden: 2.065 + 1.95,
    pieces: [{ from: 2.75, to: 2.065, r0: 0.30, r1: 0.34 }, exit(-1.95, -2.80, 0.64)] },
];
const STEP = 0.05;
const DASH = 0.12;
const GAP = 0.20;
/** World units of dash travel per degree of rotor angle. */
const TRAVEL = 0.0147;
export const FLOW_COLOR = '#8fa6b8';

/** `only`: keep just that piece of the path (same dash distances as the whole line). */
function build(path: (typeof FLOW_PATHS)[number], material: LineMaterial, only?: number) {
  const positions: number[] = [];
  const distances: number[] = [];
  const period = DASH + GAP;
  for (let i = 0; i < path.count; i++) {
    const angle = (2 * Math.PI * (i + path.phase)) / path.count;
    const c = Math.cos(angle), s = Math.sin(angle);
    // A different start on every line, so the dashes do not line up in rings.
    let d = period * ((i * 0.618034 + path.phase) % 1);
    path.pieces.forEach((p, k) => {
      if (k > 0) d += path.hidden;
      const n = Math.max(1, Math.round((p.from - p.to) / STEP));
      for (let j = 0; j < n; j++) {
        const xa = THREE.MathUtils.lerp(p.from, p.to, j / n), xb = THREE.MathUtils.lerp(p.from, p.to, (j + 1) / n);
        const ra = THREE.MathUtils.lerp(p.r0, p.r1, j / n), rb = THREE.MathUtils.lerp(p.r0, p.r1, (j + 1) / n);
        const len = Math.hypot(xb - xa, rb - ra);
        if (only === undefined || only === k) {
          positions.push(xa, ra * c, ra * s, xb, rb * c, rb * s);
          distances.push(d, d + len);
        }
        d += len;
      }
    });
  }
  const geometry = new LineSegmentsGeometry().setPositions(positions);
  const buffer = new THREE.InstancedInterleavedBuffer(new Float32Array(distances), 2, 1);
  geometry.setAttribute('instanceDistanceStart', new THREE.InterleavedBufferAttribute(buffer, 1, 0));
  geometry.setAttribute('instanceDistanceEnd', new THREE.InterleavedBufferAttribute(buffer, 1, 1));
  const lines = new LineSegments2(geometry, material);
  lines.name = `flow-${path.name}`;
  lines.frustumCulled = false;
  lines.castShadow = false;
  lines.receiveShadow = false;
  // Drawn before the translucent shells, so a shell that still writes depth
  // never hides a line outright and the depth-write switch cannot pop.
  lines.renderOrder = -1;
  return lines;
}

export function createFlow(parent: THREE.Object3D) {
  const material = new LineMaterial({
    color: FLOW_COLOR, linewidth: 1, transparent: true, opacity: 0, depthTest: true, depthWrite: false,
    dashed: true, dashSize: DASH, gapSize: GAP,
  });
  material.toneMapped = false;
  material.resolution.set(1280, 1080);
  const group = new THREE.Group();
  group.name = 'flow';
  for (const path of FLOW_PATHS) group.add(build(path, material));
  parent.add(group);
  group.visible = false;
  return {
    group,
    /** `speed` is the rotor speed as a share of cruise, `degrees` the rotor angle. */
    set(speed: number, degrees: number, off = false) {
      const opacity = 0.35 * Math.max(0, speed);
      group.visible = !off && opacity > 1e-4;
      material.opacity = opacity;
      material.dashOffset = -TRAVEL * degrees;
    },
    opacity: () => (group.visible ? material.opacity : 0),
    /** Every drawn segment as [x0, r0, x1, r1] in the space of `root`, rounded, without repeats, per family. */
    segments(root: THREE.Object3D) {
      const out: Record<string, number[][]> = {};
      if (!group.visible || material.opacity <= 0) return out;
      group.updateMatrixWorld(true);
      const toRoot = root.matrixWorld.clone().invert();
      const a = new THREE.Vector3(), b = new THREE.Vector3();
      for (const child of group.children) {
        const lines = child as LineSegments2;
        if (!lines.visible) continue;
        const seen = new Set<string>();
        const list: number[][] = (out[lines.name.replace('flow-', '')] = []);
        const m = toRoot.clone().multiply(lines.matrixWorld);
        const start = lines.geometry.attributes.instanceStart, end = lines.geometry.attributes.instanceEnd;
        for (let i = 0; i < start.count; i++) {
          a.fromBufferAttribute(start, i).applyMatrix4(m);
          b.fromBufferAttribute(end, i).applyMatrix4(m);
          const seg = [a.x, Math.hypot(a.y, a.z), b.x, Math.hypot(b.y, b.z)].map(v => Math.round(v * 1e5) / 1e5);
          const key = seg.join(',');
          if (seen.has(key)) continue;
          seen.add(key);
          list.push(seg);
        }
      }
      return out;
    },
    material,
  };
}

/**
 * The same airflow cut into its pieces, each with its own material, so every piece can
 * fade with the part it runs past (frame=ending, 主时间轴二 10.3). Keys: 'intake' (both
 * lines in front of the intake), 'bypass' (behind the bypass duct), 'core' (behind the nozzle).
 */
export function createFlowPieces(parent: THREE.Object3D) {
  const group = new THREE.Group();
  group.name = 'flow-pieces';
  const mats: Record<'intake' | 'bypass' | 'core', LineMaterial> = {} as never;
  for (const key of ['intake', 'bypass', 'core'] as const) {
    const m = new LineMaterial({
      color: FLOW_COLOR, linewidth: 1, transparent: true, opacity: 0, depthTest: true, depthWrite: false,
      dashed: true, dashSize: DASH, gapSize: GAP,
    });
    m.toneMapped = false;
    m.resolution.set(1280, 1080);
    mats[key] = m;
  }
  for (const path of FLOW_PATHS) {
    group.add(build(path, mats.intake, 0));
    group.add(build(path, path.name === 'bypass' ? mats.bypass : mats.core, 1));
  }
  parent.add(group);
  group.visible = false;
  return {
    group,
    /** `share`: each piece's opacity factor (the part next to it), 0..1. */
    set(speed: number, degrees: number, share: Record<'intake' | 'bypass' | 'core', number>) {
      const base = 0.35 * Math.max(0, speed);
      let any = false;
      for (const key of ['intake', 'bypass', 'core'] as const) {
        const m = mats[key];
        m.opacity = base * share[key];
        m.dashOffset = -TRAVEL * degrees;
        m.visible = m.opacity > 1e-4;
        any ||= m.visible;
      }
      group.visible = any;
    },
    opacity: (key: 'intake' | 'bypass' | 'core') => (group.visible && mats[key].visible ? mats[key].opacity : 0),
  };
}
