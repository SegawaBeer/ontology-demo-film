// Opening assembly, milestone one: 0:00–0:09.6. Every frame is a pure
// function of t, so the exporter can seek backwards or forwards freely.
import * as THREE from 'three';
import { LineSegments2 } from 'three/examples/jsm/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/examples/jsm/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import { createOpenScene, type OpenScene } from './open';
import { bladePoint } from '../hero-blade';
import { renderGraph } from './graph';
import type { GraphState } from './data';
import type { Theme } from './scene';

export const DURATION = 9.6;

const RING = 'turbine.stage-1-blades';
const DISC = 'turbine.stage-1-disk';
const SPAN = 3.65;
const RING_CENTER = new THREE.Vector3(-1.355, 0, 0);
const VIEW_DIR = new THREE.Vector3(0.836, 0.271, 0.477).normalize();
const LIT = new THREE.Color('#1c5fb8');

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const seg = (t: number, a: number, b: number) => clamp01((t - a) / (b - a));
const smoother = (p: number) => p * p * p * (p * (p * 6 - 15) + 10);
const smootherAt = (t: number, a: number, b: number) => smoother(seg(t, a, b));
const lerp = THREE.MathUtils.lerp;

const bladeId = (n: number) => `${RING}.${String(n).padStart(3, '0')}`;
// Blade k (2..100) starts here; the gaps shorten as the ring fills.
const bladeStart = (k: number) => 7.45 + 1.15 * Math.sqrt((k - 2) / 98);
// How long each blade shows only its outline, before turning solid.
const outlineFor = (k: number) => 0.3 - 0.2 * ((k - 2) / 98);
function bladesShown(t: number) {
  if (t < 7.4) return 0;
  let n = 1;
  for (let k = 2; k <= 100; k++) {
    if (t >= bladeStart(k)) n = k;
    else break;
  }
  return n;
}
// Integral of the decaying spin rate, so the landing starts at 8°/s exactly.
const spinIntegral = (u: number) => u - u ** 6 + 3 * u ** 5 - 2.5 * u ** 4;

export async function mountOpening(theme: Theme) {
  const params = new URLSearchParams(location.search);
  const mask = params.get('mask') === '1';
  const open = await createOpenScene(theme, mask);
  const { view, scene, camera, hero, tilt, spin, center, Y3 } = open;

  // ---- engine -------------------------------------------------------------
  const engine = view.addEngine({}, new THREE.Vector3(0, 0, 0), 1);
  view.setGhost(engine, 0);
  const components = engine.modules.flatMap(m => m.components);
  const allComponentIds = components.map(c => c.meta.id);
  engine.setVisible(allComponentIds, false);
  engine.root.updateMatrixWorld(true);

  const seat = engine.hero.poseFor(bladeId(1))!;
  engine.hero.hide();
  const seatMatrix = seat.matrix.clone();
  const s = seat.scale;
  const up = new THREE.Vector3(0, 1, 0);
  const H = SPAN * s;

  // ---- similarity that carries the whole opening rig next to the engine ----
  // Until 5 s the picture is rendered in the opening frame's own space, and the
  // engine is pulled back into that space with the inverse transform. From 5 s
  // on, everything lives in engine space and the rig is placed by Q.
  const tiltRot = new THREE.Matrix4().makeRotationFromEuler(tilt.rotation);
  const rigMatrix = (yawDeg: number) => new THREE.Matrix4()
    .makeTranslation(-center.x, -center.y, -center.z)
    .premultiply(new THREE.Matrix4().makeRotationY(THREE.MathUtils.degToRad(yawDeg)))
    .premultiply(new THREE.Matrix4().makeTranslation(center.x, center.y, center.z))
    .premultiply(tiltRot);
  const yaw5 = Y3 + 8 * 2;
  const yaw64 = yaw5 + 8 * 1.4 * spinIntegral(1);
  const inner = rigMatrix(yaw5);
  const rootAt5 = new THREE.Vector3(0, 0, 0).applyMatrix4(inner);
  const seatPos = new THREE.Vector3().setFromMatrixPosition(seatMatrix);
  const T = seatPos.clone().addScaledVector(up, H).sub(rootAt5.clone().multiplyScalar(s));
  const engineGroup = new THREE.Group();
  engineGroup.matrixAutoUpdate = false;
  engineGroup.matrix.makeScale(1 / s, 1 / s, 1 / s).premultiply(new THREE.Matrix4().makeTranslation(-T.x / s, -T.y / s, -T.z / s));
  scene.add(engineGroup);
  engineGroup.add(engine.root);
  const Qinv = engineGroup.matrix.clone();

  // Where the rig has to be once the blade is seated.
  const inner64 = rigMatrix(yaw64);
  const Q1 = seatMatrix.clone().multiply(inner64.invert());
  const q1Pos = new THREE.Vector3();
  const q1Quat = new THREE.Quaternion();
  Q1.decompose(q1Pos, q1Quat, new THREE.Vector3());

  function stageAt(t: number) {
    const p = smootherAt(t, 5.0, 6.4);
    const pos = T.clone().lerp(q1Pos, p);
    const quat = new THREE.Quaternion().slerpQuaternions(new THREE.Quaternion(), q1Quat, p);
    const m = new THREE.Matrix4().compose(pos, quat, new THREE.Vector3(s, s, s));
    tilt.matrixAutoUpdate = false;
    tilt.matrix.copy(m.multiply(tiltRot));
    tilt.updateMatrixWorld(true);
  }

  // ---- camera -------------------------------------------------------------
  const camOpen = camera.position.clone();
  const openCamQuat = camera.quaternion.clone();
  const targetOpen = open.openTarget.clone();
  const camOpenLocal = camOpen.clone();
  const targetOpenLocal = targetOpen.clone();
  const nearFarRatio = { near: camera.near / camOpen.distanceTo(targetOpen), far: camera.far / camOpen.distanceTo(targetOpen) };

  // Ring view: aim at the ring and pull back until it fills the left column.
  engineGroup.matrix.identity();
  engineGroup.updateMatrixWorld(true);
  const ringPoints: number[] = [];
  // Frame to what is on screen at 7.3 s: the disc and the one seated blade.
  {
    const pts = engine.partWorldPoints(bladeId(1));
    if (pts) for (let i = 0; i < pts.length; i++) ringPoints.push(pts[i]);
  }
  for (const part of engine.listParts(DISC)) {
    const pts = engine.partWorldPoints(part);
    if (pts) for (let i = 0; i < pts.length; i++) ringPoints.push(pts[i]);
  }
  const ringBox = new THREE.Box3();
  for (let i = 0; i < ringPoints.length; i += 3) ringBox.expandByPoint(new THREE.Vector3(ringPoints[i], ringPoints[i + 1], ringPoints[i + 2]));
  engineGroup.matrix.copy(Qinv);
  engineGroup.updateMatrixWorld(true);
  const ringCenter = ringBox.getCenter(new THREE.Vector3());
  const ringCorners: THREE.Vector3[] = [];
  for (const x of [ringBox.min.x, ringBox.max.x]) for (const y of [ringBox.min.y, ringBox.max.y]) for (const z of [ringBox.min.z, ringBox.max.z]) ringCorners.push(new THREE.Vector3(x, y, z));
  function ringPose() {
    const cam = new THREE.PerspectiveCamera(24, 1280 / 1080, 0.01, 100);
    const target = RING_CENTER.clone();
    let distance = 6;
    for (let i = 0; i < 10; i++) {
      cam.position.copy(target).addScaledVector(VIEW_DIR, distance);
      cam.lookAt(target);
      cam.updateMatrixWorld();
      let ex = 0, ey = 0;
      for (const c of ringCorners) {
        const p = c.clone().project(cam);
        ex = Math.max(ex, Math.abs(p.x));
        ey = Math.max(ey, Math.abs(p.y));
      }
      distance *= Math.max(ey / (560 / 1080), ex / (680 / 1280));
    }
    cam.position.copy(target).addScaledVector(VIEW_DIR, distance);
    cam.lookAt(target);
    cam.updateMatrixWorld();
    const px = ringCenter.clone().project(cam);
    const sx = (px.x * 0.5 + 0.5) * 1280, sy = (-px.y * 0.5 + 0.5) * 1080;
    const wpp = (2 * distance * Math.tan(THREE.MathUtils.degToRad(cam.fov / 2))) / 1080;
    const right = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0);
    const upv = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 1);
    target.addScaledVector(right, (sx - 640) * wpp).addScaledVector(upv, (540 - sy) * wpp);
    const position = target.clone().addScaledVector(VIEW_DIR, distance);
    return { position, target, distance };
  }
  const ring = ringPose();
  const camStart = camOpen.clone().multiplyScalar(s).add(T);
  const targetStart = targetOpen.clone().multiplyScalar(s).add(T);
  const startDist = camStart.distanceTo(targetStart);
  const dirStart = camStart.clone().sub(targetStart).normalize();
  const dirEnd = ring.position.clone().sub(ring.target).normalize();

  let camTargetNow = new THREE.Vector3();
  function cameraAt(t: number) {
    if (t <= 5.0) {
      camera.position.copy(camStart);
      camera.lookAt(targetStart);
    } else {
      const u = smootherAt(t, 5.0, 7.3);
      const target = targetStart.clone().lerp(ring.target, u);
      const qa = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), dirStart);
      const qb = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), dirEnd);
      const dir = new THREE.Vector3(0, 0, 1).applyQuaternion(qa.slerp(qb, u));
      const distance = Math.exp(lerp(Math.log(startDist), Math.log(ring.distance), u));
      const orbit = THREE.MathUtils.degToRad(1.5) * (t > 7.6 ? (t - 7.6 - 0.6 * smoother(seg(t, 7.6, 8.2))) : 0);
      dir.applyAxisAngle(new THREE.Vector3(1, 0, 0), orbit);
      camera.position.copy(target).addScaledVector(dir, distance);
      camera.lookAt(target);
    }
    camTargetNow = t <= 5 ? targetStart.clone()
      : t <= 7.3 ? targetStart.clone().lerp(ring.target, smootherAt(t, 5.0, 7.3))
        : ring.target.clone();
    camera.updateMatrixWorld();
    const dist = camera.position.distanceTo(
      t <= 5 ? targetStart : t <= 7.3 ? targetStart.clone().lerp(ring.target, smootherAt(t, 5.0, 7.3)) : ring.target,
    );
    camera.near = Math.max(0.001, dist * nearFarRatio.near);
    camera.far = dist * nearFarRatio.far;
    camera.updateProjectionMatrix();
  }

  // ---- lights -------------------------------------------------------------
  type LightState = { light: THREE.DirectionalLight; pos: THREE.Vector3; target: THREE.Vector3; shadow: number[] };
  const lights: LightState[] = [];
  scene.traverse(o => {
    const light = o as THREE.DirectionalLight;
    if (!light.isDirectionalLight) return;
    const target = light.target.position.clone();
    lights.push({
      light, pos: light.position.clone(), target,
      shadow: [light.shadow.camera.left, light.shadow.camera.right, light.shadow.camera.top, light.shadow.camera.bottom, light.shadow.camera.near, light.shadow.camera.far],
    });
    light.target.position.copy(target.clone().multiplyScalar(s).add(T));
    if (!light.target.parent) scene.add(light.target);
  });
  const ringShadow = 1.1;
  function lightsOriginal() {
    for (const entry of lights) {
      entry.light.position.copy(entry.pos);
      entry.light.target.position.copy(entry.target);
      entry.light.target.updateMatrixWorld();
      const [l, r, tp, bt, nr, fr] = entry.shadow;
      const cam = entry.light.shadow.camera;
      cam.left = l; cam.right = r; cam.top = tp; cam.bottom = bt; cam.near = nr; cam.far = fr;
      cam.updateProjectionMatrix();
    }
  }
  function lightsAt(t: number) {
    const u = smootherAt(t, 5.0, 7.3);
    for (const entry of lights) {
      const moved = entry.pos.clone().multiplyScalar(s).add(T);
      entry.light.position.copy(moved.lerp(entry.pos, u));
      const movedTarget = entry.target.clone().multiplyScalar(s).add(T);
      entry.light.target.position.copy(movedTarget.lerp(entry.target, u));
      entry.light.target.updateMatrixWorld();
      const [l, r, tp, bt, nr, fr] = entry.shadow;
      const k = lerp(1, ringShadow / (Math.max(r, tp) * 1), u);
      const cam = entry.light.shadow.camera;
      // Widen from the scaled rig frustum to one that covers the ring.
      const ext = Math.hypot(ringBox.getSize(new THREE.Vector3()).length(), 0) * 0.6 + H * 2;
      cam.left = l * lerp(s, ext, u);
      cam.right = r * lerp(s, ext, u);
      cam.top = tp * lerp(s, ext, u);
      cam.bottom = bt * lerp(s, ext, u);
      cam.near = Math.max(0.01, nr * lerp(s, 1, u));
      cam.far = fr * lerp(s, 8, u);
      cam.updateProjectionMatrix();
      void k;
    }
  }

  // ---- blade materials for the colour hand-off ----------------------------
  const heroColors: { material: THREE.Material & { color: THREE.Color }; base: THREE.Color }[] = [];
  hero.root.traverse(o => {
    const mesh = o as THREE.Mesh & { isLineSegments2?: boolean; userData: { openShell?: boolean } };
    if (!mesh.isMesh || mesh.isLineSegments2 || mesh.userData.openShell) return;
    for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
      const mat = m as THREE.Material & { color?: THREE.Color };
      if (mat.color && !heroColors.some(e => e.material === mat)) heroColors.push({ material: mat as THREE.Material & { color: THREE.Color }, base: mat.color.clone() });
    }
  });
  let ringColor = new THREE.Color('#8d9194');
  const bladeComp = components.find(c => c.meta.id === RING);
  bladeComp?.group.traverse(o => {
    const m = o as THREE.Mesh;
    if (m.isMesh) for (const mat of Array.isArray(m.material) ? m.material : [m.material]) if ((mat as THREE.MeshStandardMaterial).color) ringColor = (mat as THREE.MeshStandardMaterial).color.clone();
  });

  // ---- ring outlines ------------------------------------------------------
  const bladeMesh = (() => {
    let found: THREE.InstancedMesh | null = null;
    bladeComp?.group.traverse(o => { const m = o as THREE.InstancedMesh; if (m.isInstancedMesh && !found) found = m; });
    return found as THREE.InstancedMesh | null;
  })();
  const ringOutlines: LineSegments2[] = [];
  const ringLineMat = new LineMaterial({ color: 0x4e5e6b, linewidth: 1.2, transparent: true, opacity: 1, depthWrite: false });
  ringLineMat.resolution.set(1280, 1080);
  if (bladeMesh && !mask) {
    const edges = new THREE.EdgesGeometry(bladeMesh.geometry, 25);
    const base = new LineSegmentsGeometry().fromEdgesGeometry(edges);
    const matrix = new THREE.Matrix4();
    for (let n = 1; n <= 100; n++) {
      bladeMesh.getMatrixAt(n - 1, matrix);
      const local = base.clone();
      const arr: number[] = [];
      const src = (local.attributes.instanceStart as THREE.InterleavedBufferAttribute).data.array as Float32Array;
      const segCount = local.attributes.instanceStart.count;
      const v = new THREE.Vector3();
      for (let i = 0; i < segCount; i++) {
        for (const k of [i * 3, (i + 1) * 3]) {
          v.set(src[k], src[k + 1], src[k + 2]).applyMatrix4(matrix);
          arr.push(v.x, v.y, v.z);
        }
      }
      const geo = new LineSegmentsGeometry().setPositions(arr);
      const lines = new LineSegments2(geo, ringLineMat);
      lines.computeLineDistances();
      lines.visible = false;
      scene.add(lines);
      ringOutlines.push(lines);
    }
    edges.dispose();
  }

  // ---- disc reveal --------------------------------------------------------
  const discComp = components.find(c => c.meta.id === DISC)!;
  const discMaterials: THREE.Material[] = [];
  const discLines: LineSegments2[] = [];
  const discMeshes: THREE.Mesh[] = [];
  discComp.group.traverse(o => {
    const mesh = o as THREE.Mesh & { isLineSegments2?: boolean };
    if (mesh.isMesh && !mesh.isLineSegments2 && mesh.geometry) discMeshes.push(mesh);
  });
  for (const mesh of discMeshes) {
    for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) if (!discMaterials.includes(m)) discMaterials.push(m);
    if (!mask && mesh.geometry) {
      const edges = new THREE.EdgesGeometry(mesh.geometry, 25);
      const lines = new LineSegments2(new LineSegmentsGeometry().fromEdgesGeometry(edges), ringLineMat);
      lines.computeLineDistances();
      lines.visible = false;
      mesh.add(lines);
      discLines.push(lines);
      edges.dispose();
    }
  }
  const discPlane = new THREE.Plane(new THREE.Vector3(1, 0, 0), 0);

  function discAt(t: number) {
    const appear = smootherAt(t, 4.8, 5.3);
    engine.setVisible(DISC, appear > 0.001);
    const sweep = smootherAt(t, 5.4, 6.2);
    for (const line of discLines) line.visible = appear > 0.001 && sweep < 0.999;
    for (const m of discMaterials) {
      m.clippingPlanes = sweep > 0 && sweep < 0.999 ? [discPlane] : null;
    }
    // Sweep from the rear of the disc towards the front.
    const box = new THREE.Box3();
    for (const part of engine.listParts(DISC)) {
      const c = engine.getPart(part)?.center;
      if (c) box.expandByPoint(new THREE.Vector3(c[0], c[1], c[2]));
    }
    const x0 = box.min.x - 0.08, x1 = box.max.x + 0.08;
    discPlane.set(new THREE.Vector3(1, 0, 0), -lerp(x0, x1, sweep));
    for (const line of discLines) line.visible = appear > 0.001 && sweep < 0.999;
    if (sweep >= 0.999) for (const m of discMaterials) m.clippingPlanes = null;
  }

  // ---- blades on the ring -------------------------------------------------
  for (let n = 1; n <= 100; n++) engine.setVisible(bladeId(n), false);
  let shownNow = 0;
  function ringAt(t: number) {
    const shown = bladesShown(t);
    if (shown !== shownNow) {
      for (let n = 1; n <= 100; n++) engine.setVisible(bladeId(n), n <= shown);
      shownNow = shown;
    }
    for (let n = 1; n <= 100; n++) {
      const outline = ringOutlines[n - 1];
      if (!outline) continue;
      const start = n === 1 ? 7.4 : bladeStart(n);
      const width = n === 1 ? 0 : outlineFor(n);
      outline.visible = n <= shown && t < start + width;
    }
  }

  // ---- flash --------------------------------------------------------------
  function flashAt(t: number) {
    const p = seg(t, 8.8, 9.3);
    const amount = p <= 0 || p >= 1 ? 0 : Math.sin(Math.PI * p) * 0.35;
    if (amount <= 0.001) {
      for (let n = 1; n <= 100; n++) engine.setColor(bladeId(n), null);
      return;
    }
    // Instance colours multiply the material colour, so solve for the value
    // that lands on the wanted mix.
    // Mixed in sRGB, which is how the colour reads on screen.
    const want = ringColor.clone().convertLinearToSRGB()
      .lerp(LIT.clone().convertLinearToSRGB(), amount)
      .convertSRGBToLinear();
    const c = new THREE.Color(
      Math.min(4, want.r / Math.max(0.02, ringColor.r)),
      Math.min(4, want.g / Math.max(0.02, ringColor.g)),
      Math.min(4, want.b / Math.max(0.02, ringColor.b)),
    );
    for (let n = 1; n <= 100; n++) engine.setColor(bladeId(n), c);
  }

  // ---- graph --------------------------------------------------------------
  const graphEl = document.querySelector<SVGSVGElement>('#graph')!;
  const thread = document.querySelector<SVGSVGElement>('#thread')!;
  const paths = thread.querySelectorAll('path');
  const dots = thread.querySelectorAll('circle');
  const firstPath = paths[0] as SVGPathElement, firstDot = dots[0] as SVGCircleElement;
  const secondPath = paths[1] as SVGPathElement, secondDot = dots[1] as SVGCircleElement;

  function line(p: SVGPathElement, dot: SVGCircleElement, start: { x: number; y: number }, node: { x: number; y: number }, back: number, progress: number, opacity = 1) {
    const dx0 = node.x - start.x, dy0 = node.y - start.y;
    const len = Math.hypot(dx0, dy0) || 1;
    const end = { x: node.x - (dx0 / len) * back, y: node.y - (dy0 / len) * back };
    const dx = end.x - start.x;
    p.setAttribute('d', `M${start.x} ${start.y} C${start.x + 0.45 * dx} ${start.y} ${end.x - 0.45 * dx} ${end.y} ${end.x} ${end.y}`);
    dot.setAttribute('cx', String(start.x));
    dot.setAttribute('cy', String(start.y));
    const total = p.getTotalLength();
    p.style.strokeDasharray = `${total}`;
    p.style.strokeDashoffset = `${total * (1 - progress)}`;
    p.style.opacity = progress > 0 ? String(opacity) : '0';
    dot.style.opacity = progress > 0 ? String(opacity) : '0';
  }

  function bladeTipScreen(n: number) {
    const pts = engine.partWorldPoints(bladeId(n));
    if (!pts) return null;
    let best: THREE.Vector3 | null = null;
    let bestX = -Infinity;
    for (let i = 0; i < pts.length; i += 3) {
      const p = new THREE.Vector3(pts[i], pts[i + 1], pts[i + 2]);
      const q = view.project(p);
      if (q.x > bestX) { bestX = q.x; best = p; }
    }
    return best ? view.project(best) : null;
  }

  function graphAt(t: number) {
    const shown = bladesShown(t);
    const two = t >= 8.8;
    const appear = smootherAt(t, 1.0, 1.4);
    if (mask) return;
    if (appear <= 0) {
      renderGraph(graphEl, { focus: false, lit: [], litEdges: [], chip: {}, status: {}, timing: [], only: [], counter: '0 个节点 · 0 条关系' });
      return;
    }
    const state: GraphState = {
      focus: false, lit: ['blade', ...(two ? ['c-t1'] : [])], litEdges: [], chip: {}, status: {}, timing: [],
      only: two ? ['blade', 'c-t1'] : ['blade'],
      sub: { blade: `×${Math.max(1, shown)}` },
      appear: { blade: appear, ...(two ? { 'c-t1': smootherAt(t, 8.8, 9.2) } : {}) },
      counter: two ? '2 个节点 · 1 条关系' : '1 个节点 · 0 条关系',
      drawing: t > 8.6 ? [{ from: 'blade', to: 'c-t1', progress: smootherAt(t, 8.6, 8.85) }] : [],
      captions: two ? ['涡轮叶环'] : [],
    };
    renderGraph(graphEl, state);
  }

  // ---- frame --------------------------------------------------------------
  function apply(t: number, render = true) {
    if (t < 5.0) {
      // Opening-frame space: untouched rig and camera, engine pulled in.
      tilt.matrixAutoUpdate = true;
      tilt.updateMatrixWorld(true);
      engineGroup.matrix.copy(Qinv);
      engineGroup.updateMatrixWorld(true);
      camera.position.copy(camOpen);
      camera.quaternion.copy(openCamQuat);
      camera.near = 0.05;
      camera.far = 80;
      camera.updateProjectionMatrix();
      camera.updateMatrixWorld();
      lightsOriginal();
      open.setTime(t, false);
      hero.root.updateMatrixWorld(true);
      open.hero.root.visible = true;
      discAt(t);
      ringAt(t);
      if (!mask) { secondPath.style.opacity = '0'; secondDot.style.opacity = '0'; }
      if (render) view.render();
      return;
    }
    {
      const u = seg(t, 5.0, 6.4);
      spin.rotation.y = THREE.MathUtils.degToRad(yaw5 + 8 * 1.4 * spinIntegral(u));
      stageAt(t);
      engineGroup.matrix.identity();
      engineGroup.updateMatrixWorld(true);
      spin.updateMatrixWorld(true);
      open.hero.root.visible = t < 7.4;
      open.setSweep(1);
      open.lineMat.visible = false;
      open.lineMat.opacity = 0;
    }
    hero.root.updateMatrixWorld(true);
    open.hero.root.visible = t < 7.4;
    cameraAt(t);
    lightsAt(t);
    discAt(t);
    ringAt(t);
    flashAt(Math.min(t, 9.3));
    if (t >= 6.4) {
      const p = smootherAt(t, 6.4, 7.35);
      for (const entry of heroColors) entry.material.color.copy(entry.base).lerp(ringColor, p);
    }
    if (t >= 7.4) {
      open.hero.root.visible = false;
      engine.setVisible(bladeId(1), bladesShown(t) >= 1);
    }
    graphAt(t);
    if (!mask) {
      const first = firstBladeTip();
      const fade = 1 - seg(t, 6.6, 7.1);
      if (first && t >= 1.8 && fade > 0) line(firstPath, firstDot, first, { x: 1573, y: 410 }, 9, clamp01((t - 1.8) / 1.4), 0.85 * fade);
      else { firstPath.style.opacity = '0'; firstDot.style.opacity = '0'; }
      const tip = t >= 8.8 ? bladeTipScreen(100) : null;
      if (tip) line(secondPath, secondDot, tip, { x: 1573, y: 330 }, 6, seg(t, 8.8, 9.2), 0.85);
      else { secondPath.style.opacity = '0'; secondDot.style.opacity = '0'; }
    }
    if (render) view.render();
  }

  function firstBladeTip() {
    const m = hero.root.matrixWorld;
    const a = view.project(bladePoint(0, 0.55, 1).clone().applyMatrix4(m));
    const b = view.project(bladePoint(1, 0.55, 1).clone().applyMatrix4(m));
    return a.x >= b.x ? a : b;
  }

  (window as unknown as { __seek: (t: number) => void }).__seek = (t: number) => apply(t);
  (window as unknown as { __duration: number }).__duration = DURATION;
  if (mask) {
    document.querySelector<HTMLElement>('.col-graph')!.style.visibility = 'hidden';
    thread.style.display = 'none';
  } else {
    thread.setAttribute('viewBox', '0 0 1920 1080');
    for (const p of [firstPath, secondPath]) {
      p.setAttribute('fill', 'none'); p.setAttribute('stroke', 'var(--lit)');
      p.setAttribute('stroke-width', '1.25'); p.setAttribute('opacity', '0.85');
    }
    for (const d of [firstDot, secondDot]) {
      d.setAttribute('r', '2.5'); d.setAttribute('fill', 'var(--lit)'); d.setAttribute('opacity', '0.85');
    }
  }
  (window as unknown as { __openingProbe: () => unknown }).__openingProbe = () => {
    const threads = [firstPath, secondPath].map(p => {
      const d = p.getAttribute('d');
      if (!d) return { start: [0, 0], end: [0, 0], total: 0, off: 0, opacity: 0 };
      const total = p.getTotalLength();
      const off = parseFloat(p.style.strokeDashoffset || '0');
      const opacity = parseFloat(p.style.opacity || '1');
      const start = p.getPointAtLength(0);
      const end = p.getPointAtLength(total);
      return { start: [start.x, start.y], end: [end.x, end.y], total, off, opacity };
    });
    const gtexts = [...graphEl.querySelectorAll('text')].map(t => t.textContent ?? '');
    const nodes = [...graphEl.querySelectorAll('g')].filter(g => g.querySelector('circle')).length;
    const box = new THREE.Box3().setFromObject(hero.root);
    let bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity;
    for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) {
      const p = view.project(new THREE.Vector3(x, y, z));
      bx0 = Math.min(bx0, p.x); by0 = Math.min(by0, p.y); bx1 = Math.max(bx1, p.x); by1 = Math.max(by1, p.y);
    }
    return {
      camera: { position: camera.position.toArray(), target: camTargetNow.toArray() },
      hero: {
        visible: hero.root.visible,
        matrix: hero.root.matrixWorld.elements.slice(),
        screen: view.project(new THREE.Vector3().setFromMatrixPosition(hero.root.matrixWorld)),
        box: [bx0, by0, bx1, by1],
      },
      blades: { count: shownNow, ids: Array.from({ length: shownNow }, (_, i) => bladeId(i + 1)) },
      graph: { nodes, counter: gtexts.find(x => x.includes('个节点')) ?? '', sub: gtexts.find(x => x.startsWith('×')) ?? '', texts: gtexts },
      threads,
      seat: view.project(seatPos.clone()),
      seatMatrix: seatMatrix.elements.slice(),
    };
  };

  if (mask) {
    const black = new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.DoubleSide, toneMapped: false });
    scene.traverse(o => {
      const m = o as THREE.Mesh & { isLineSegments2?: boolean; userData: { openShell?: boolean } };
      if (m.isMesh && !m.isLineSegments2 && !m.userData.openShell) m.material = black;
    });
  }

  const hold = params.get('t');
  if (hold !== null) {
    apply(Number(hold));
  } else if (params.get('play') === '0') {
    apply(0);
  } else {
    const start = performance.now();
    const loop = (now: number) => {
      apply(((now - start) / 1000) % (DURATION + 1.5));
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }
}
