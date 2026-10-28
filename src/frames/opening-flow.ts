// Opening 3B: thin airflow lines along the engine axis while the fan turns.
// One family enters the intake and leaves through the bypass, the other runs
// through the core and leaves at the exhaust. The dashes move by a fixed
// multiple of the rotor angle, so every frame is a function of t alone.
import * as THREE from 'three';
import { LineSegments2 } from 'three/examples/jsm/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/examples/jsm/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';

// (axial x, radius) in engine space, front (+x) to back. The air flows that way.
const BYPASS: [number, number][] = [
  [2.75, 0.50], [2.30, 0.55], [2.00, 0.60], [1.80, 0.63], [1.50, 0.68], [1.10, 0.69],
  [0.60, 0.69], [0.25, 0.70], [-0.10, 0.79], [-0.50, 0.83], [-0.90, 0.85],
];
const CORE: [number, number][] = [
  [2.75, 0.30], [2.30, 0.32], [2.00, 0.36], [1.70, 0.40], [1.40, 0.44], [1.10, 0.48],
  [0.70, 0.52], [0.30, 0.50], [-0.20, 0.50], [-0.70, 0.47], [-1.20, 0.43], [-1.55, 0.52],
  [-1.85, 0.70], [-2.30, 0.73], [-2.80, 0.75],
];
const DASH = 0.10;
const GAP = 0.22;
/** World units of dash travel per degree of rotor angle. */
const TRAVEL = 0.0147;
export const FLOW_COLOR = '#8fa6b8';

function build(profile: [number, number][], count: number, phase: number, material: LineMaterial) {
  const curve = new THREE.CatmullRomCurve3(profile.map(([x, r]) => new THREE.Vector3(x, r, 0)), false, 'centripetal');
  const samples = curve.getSpacedPoints(120);
  const positions: number[] = [];
  const distances: number[] = [];
  const period = DASH + GAP;
  for (let i = 0; i < count; i++) {
    const angle = (2 * Math.PI * (i + phase)) / count;
    const c = Math.cos(angle), s = Math.sin(angle);
    // A different start on every line, so the dashes do not line up in rings.
    let d = period * ((i * 0.618034 + phase) % 1);
    for (let k = 0; k < samples.length - 1; k++) {
      const a = samples[k], b = samples[k + 1];
      positions.push(a.x, a.y * c, a.y * s, b.x, b.y * c, b.y * s);
      const len = Math.hypot(b.x - a.x, b.y - a.y);
      distances.push(d, d + len);
      d += len;
    }
  }
  const geometry = new LineSegmentsGeometry().setPositions(positions);
  const buffer = new THREE.InstancedInterleavedBuffer(new Float32Array(distances), 2, 1);
  geometry.setAttribute('instanceDistanceStart', new THREE.InterleavedBufferAttribute(buffer, 1, 0));
  geometry.setAttribute('instanceDistanceEnd', new THREE.InterleavedBufferAttribute(buffer, 1, 1));
  const lines = new LineSegments2(geometry, material);
  lines.frustumCulled = false;
  lines.castShadow = false;
  lines.receiveShadow = false;
  // Drawn before the translucent shells, so a shell that still writes depth
  // never hides a line outright and the depth-write switch cannot pop.
  lines.renderOrder = -1;
  return lines;
}

/** `region` draws solid, opaque, wide black lines for a mask of where flow can show. */
export function createFlow(parent: THREE.Object3D, region = false) {
  const material = new LineMaterial({
    color: region ? 0x000000 : FLOW_COLOR, linewidth: region ? 5 : 1,
    transparent: !region, opacity: region ? 1 : 0, depthTest: !region, depthWrite: false,
    dashed: !region, dashSize: DASH, gapSize: GAP,
  });
  material.toneMapped = false;
  material.resolution.set(1280, 1080);
  const group = new THREE.Group();
  group.name = 'flow';
  group.add(build(BYPASS, 16, 0, material), build(CORE, 12, 0.5, material));
  parent.add(group);
  group.visible = false;
  return {
    group,
    /** `speed` is the rotor speed as a share of cruise, `degrees` the rotor angle. */
    set(speed: number, degrees: number, off = false) {
      const opacity = region ? 1 : 0.35 * Math.max(0, speed);
      group.visible = !off && (region || opacity > 1e-4);
      material.opacity = opacity;
      material.dashOffset = -TRAVEL * degrees;
    },
    opacity: () => (group.visible ? material.opacity : 0),
  };
}
