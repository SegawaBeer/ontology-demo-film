// Question four, the 3D column (主时间轴二 第二节, 第四节), global t 86–101.
// It works on the engine as clip-q3 leaves it at 22.0: everything but the first-stage
// ring and disk ghosted, the 16 stopped blades promoted and parked outside the ring.
import * as THREE from 'three';
import { LineSegments2 } from 'three/examples/jsm/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/examples/jsm/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import type { Engine } from '../model';
import type { ModelView, Pose } from './scene';
import { blendPose } from './clip-q12';
import { seg, ease } from './timing';
import { STEP1, FLY_AT, FLY_GAP, landAt } from './q4';

export const TAGS_OUT = [86.0, 86.2] as const;     // clip-q3's two engine tags
export const CAM4 = [86.0, 87.0] as const;         // push in to 7 号's first-stage ring
export const E3_OUT = [86.2, 87.2] as const;       // 3 号 shrinks and fades
export const RED_OUT = [86.4, 87.0] as const;      // the 16 stopped blades fade
export const FRAMES_IN = [86.6, 87.2] as const;    // red outlines in the 16 empty slots
export const COLOUR_BACK = [98.4, 99.0] as const;
export const GAP_TAGS = STEP1;
// Insertion, the part-one pull run backwards: line up radially outside the slot with the
// root forward of the disk rim, move in, then slide back along the slot (engine-local).
const AXIAL = 0.06, RADIAL = 0.063, FAR = 0.55;
const FLY = [0, 0.6] as const, IN = [0.6, 0.78] as const, SLIDE = [0.78, 1] as const;

type Ctx = {
  view: ModelView; e7: Engine; e3: Engine; hit7: string[]; ring: THREE.Color; red: string; green: string;
  from: Pose; to: Pose; project: (w: THREE.Vector3) => { x: number; y: number };
};

export function createQ4Model(c: Ctx) {
  const { e7, e3 } = c;
  const ringParts = e7.listParts('turbine.stage-1-blades');
  const others = ringParts.filter(id => !c.hit7.includes(id));
  // 3 号: every material's own opacity, so the fade can multiply it and put it back exactly.
  const e3Mats: { m: THREE.MeshStandardMaterial; opacity: number; transparent: boolean; depthWrite: boolean }[] = [];
  e3.root.traverse(o => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    const m = mesh.material as THREE.MeshStandardMaterial;
    if (!e3Mats.some(x => x.m === m)) e3Mats.push({ m, opacity: m.opacity, transparent: m.transparent, depthWrite: m.depthWrite });
  });
  const E3_SCALE = e3.root.scale.x;
  let e3Now = -1;
  function fadeE3(k: number) {
    e3.root.scale.setScalar(E3_SCALE * (1 - 0.6 * k));
    if (k >= 1) e3.root.visible = false;
    if (Math.abs(k - e3Now) < 1e-5) return;
    e3Now = k;
    for (const x of e3Mats) {
      const transparent = x.transparent || k > 0;
      const depthWrite = x.depthWrite && k <= 0;
      x.m.opacity = x.opacity * (1 - k);
      if (x.m.transparent !== transparent || x.m.depthWrite !== depthWrite) { x.m.transparent = transparent; x.m.depthWrite = depthWrite; x.m.needsUpdate = true; }
    }
  }
  function promotedOpacity(id: string, opacity: number) {
    const m = e7.parts.get(id)!.promoted?.material as THREE.MeshStandardMaterial | undefined;
    if (!m) return;
    const transparent = opacity < 0.999;
    m.opacity = transparent ? opacity : 1;
    if (m.transparent !== transparent || m.depthWrite !== !transparent) { m.transparent = transparent; m.depthWrite = !transparent; m.needsUpdate = true; }
  }

  // Red outlines of the empty slots: the ring blade's own edges at each slot's matrix.
  const frames = c.hit7.map(id => {
    const state = e7.parts.get(id)!;
    const mat = new LineMaterial({ color: new THREE.Color(c.red).getHex(), linewidth: 1.2, transparent: true, opacity: 0, depthWrite: false });
    mat.resolution.set(720, 1080);
    const edges = new THREE.EdgesGeometry(state.group.mesh.geometry, 25);
    const lines = new LineSegments2(new LineSegmentsGeometry().fromEdgesGeometry(edges), mat);
    edges.dispose();
    lines.matrixAutoUpdate = false;
    lines.matrix.copy(state.matrix);
    lines.visible = false;
    lines.renderOrder = 2;
    state.group.mesh.parent!.add(lines);
    return { lines, mat };
  });

  // Who comes from where: the six gaps highest-left on screen from the home store, the
  // other ten from the second plant. Within each group, outermost first.
  const camAt = new THREE.PerspectiveCamera(c.view.camera.fov, 720 / 1080, c.view.camera.near, c.view.camera.far);
  camAt.position.copy(c.to.position); camAt.lookAt(c.to.target); camAt.updateMatrixWorld();
  e7.root.updateMatrixWorld(true);
  const centre = (id: string) => new THREE.Vector3(...e7.getPart(id)!.center);
  const screen = (id: string) => centre(id).applyMatrix4(e7.root.matrixWorld).project(camAt);
  const ranked = [...c.hit7].sort((p, q) => (screen(p).y - screen(p).x) - (screen(q).y - screen(q).x)).reverse();
  const home = ranked.slice(0, 6), plant = ranked.slice(6);
  const right = new THREE.Vector3().setFromMatrixColumn(camAt.matrixWorld, 0), up = new THREE.Vector3().setFromMatrixColumn(camAt.matrixWorld, 1);
  const order = [...home, ...plant].map((id, k) => {
    const cc = centre(id);
    const radial = new THREE.Vector3(0, cc.y, cc.z).normalize();
    const fromDir = (k < 6 ? up.clone().sub(right) : right.clone().sub(up)).normalize().add(radial.clone().multiplyScalar(0.6)).normalize();
    return { id, k, radial, fromDir, slot: c.hit7.indexOf(id) };
  });
  const offsetAt = (o: typeof order[number], t: number) => {
    const u = seg(t, FLY_AT + FLY_GAP * o.k, landAt(o.k));
    const fly = 1 - ease(seg(u, FLY[0], FLY[1]));
    const rad = RADIAL * (1 - ease(seg(u, IN[0], IN[1])));
    const ax = AXIAL * (1 - ease(seg(u, SLIDE[0], SLIDE[1])));
    return o.radial.clone().multiplyScalar(rad).add(new THREE.Vector3(ax, 0, 0)).addScaledVector(o.fromDir, FAR * fly);
  };

  // engine.setVisible(true) puts an instanced part back in its slot even while it has its
  // own mesh, which would draw a second copy there; a part with its own mesh is shown or
  // hidden on that mesh only.
  function showPart(id: string, on: boolean) {
    const st = e7.parts.get(id)!;
    if (st.promoted) { st.visible = on; st.promoted.visible = on; return; }
    e7.setVisible(id, on);
  }
  const green = new THREE.Color(c.green);
  let seatedAll = false;
  /** Engine state for any t ≥ 64; below 86 it only puts back what question four changes. */
  function apply(t: number) {
    fadeE3(ease(seg(t, E3_OUT[0], E3_OUT[1])));
    const redOut = ease(seg(t, RED_OUT[0], RED_OUT[1]));
    const framesIn = ease(seg(t, FRAMES_IN[0], FRAMES_IN[1]));
    const back = ease(seg(t, COLOUR_BACK[0], COLOUR_BACK[1]));
    const tint = c.ring.clone().lerp(green, 0.4 * (1 - back));
    // Seated blades go back into the ring's own instanced mesh: from the first landing on,
    // the whole ring is put back every frame and only the blades still in the air are lifted out.
    if (t >= landAt(0)) {
      e7.setOpacity(ringParts, 1);
      e7.setVisible(c.hit7, true);
      // A part put back keeps whatever instance colour it had before it was lifted out;
      // write the ring grey again so the picture does not depend on what was shown before.
      e7.setColor(others, c.ring);
    }
    seatedAll = t >= landAt(15);
    for (const o of order) {
      const f = frames[o.slot];
      f.mat.opacity = framesIn * (1 - ease(seg(t, landAt(o.k) - 0.15, landAt(o.k))));
      f.lines.visible = f.mat.opacity > 0.002;
      if (t >= landAt(o.k)) { e7.setColor(o.id, tint); continue; }
      if (t < RED_OUT[0]) { promotedOpacity(o.id, 1); showPart(o.id, true); continue; }
      if (t < FLY_AT + FLY_GAP * o.k) { promotedOpacity(o.id, 1 - redOut); showPart(o.id, redOut < 1); continue; }
      const off = offsetAt(o, t);
      e7.setColor(o.id, tint);
      e7.setTransform(o.id, { position: [off.x, off.y, off.z] });
      // Comes in out of nothing at the far end of its flight.
      promotedOpacity(o.id, ease(seg(t, FLY_AT + FLY_GAP * o.k, FLY_AT + FLY_GAP * o.k + 0.1)));
      showPart(o.id, true);
      e7.setColor(o.id, tint);
    }
  }

  function cameraAt(t: number): Pose {
    return blendPose(c.from, c.to, ease(seg(t, CAM4[0], CAM4[1])));
  }

  /** Centre and box of a set of gaps on screen (model-column pixels), for the tags. */
  const groupScreen = (ids: string[]) => {
    const pts = ids.map(id => c.project(centre(id).applyMatrix4(e7.root.matrixWorld)));
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
    return { x: xs.reduce((a, b) => a + b, 0) / pts.length, y: ys.reduce((a, b) => a + b, 0) / pts.length, x1: Math.max(...xs), y0: Math.min(...ys) };
  };
  return { apply, cameraAt, order, home, plant, groupScreen, frames, seated: () => seatedAll, offsetAt };
}
