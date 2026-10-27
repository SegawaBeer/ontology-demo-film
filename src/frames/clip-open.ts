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

export const DURATION = 23.0;

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
const bladeStart = (k: number) => 7.65 + 0.95 * Math.sqrt((k - 2) / 98);
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
  const maskMode = params.get('mask');
  const mask = maskMode !== null;
  const diskMode = maskMode === 'disk' || maskMode === 'disk-solid';
  const partMask = maskMode && maskMode.startsWith('part:') ? maskMode.slice(5).split(',') : null;
  const solo = params.get('solo') ? params.get('solo')!.split(',') : null;
  // Debug: hide the depth-only shells ('1' or 'all' for every kind).
  const noShells = params.get('noshells') ?? '';
  const hideShell = (kind: string) => noShells === '1' || noShells === 'all' || noShells === kind;
  const open = await createOpenScene(theme, mask);
  const { view, scene, camera, hero, tilt, spin, center, Y3 } = open;

  // ---- engine -------------------------------------------------------------
  const engine = view.addEngine({}, new THREE.Vector3(0, 0, 0), 1);
  view.setGhost(engine, 0);
  const components = engine.modules.flatMap(m => m.components);
  const allComponentIds = components.map(c => c.meta.id);
  // Hiding an instanced part zeroes its instance matrix, so keep a copy for
  // the outlines before that happens.
  const instanceSnapshots = new Map<THREE.InstancedMesh, Float32Array>();
  engine.root.traverse(o => {
    const inst = o as THREE.InstancedMesh;
    if (inst.isInstancedMesh) instanceSnapshots.set(inst, Float32Array.from(inst.instanceMatrix.array));
  });
  // The assembled-engine framing is measured here, while every part still sits
  // visible in assembly position and nothing hangs under the engine: that is the
  // box treeToNet() frames, and it has to be measured in engine space, not in the
  // opening rig's scaled space.
  const m3FitPos = new THREE.Vector3();
  const m3FitTarget = new THREE.Vector3();
  {
    engine.root.updateMatrixWorld(true);
    const pos = camera.position.clone();
    const quat = camera.quaternion.clone();
    const pose = view.fit([engine], new THREE.Vector3(0.78, 0.34, 0.92), { x: 0.78, y: 0.70 }, new THREE.Vector2(-0.06, 0.02));
    camera.position.copy(pos);
    camera.quaternion.copy(quat);
    camera.updateMatrixWorld();
    m3FitPos.copy(pose.position);
    m3FitTarget.copy(pose.target);
  }
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
  const orbitAngle = (t: number) => {
    if (t <= 7.3) return 0;
    const at96 = 1.5 * (9.6 - 7.3 - 0.6 * smoother(seg(9.6, 7.3, 7.9)));
    if (t <= 9.6) return THREE.MathUtils.degToRad(1.5 * (t - 7.3 - 0.6 * smoother(seg(t, 7.3, 7.9))));
    const u = Math.min(1, (t - 9.6) / 0.5);
    const f = u ** 6 - 3 * u ** 5 + 2.5 * u ** 4;
    return THREE.MathUtils.degToRad(at96 + 1.5 * ((t - 9.6) - 0.5 * f));
  };

  // Framing for the assembled engine: box of the components this milestone
  // adds, fitted the same way view.fit() does but without hidden parts.
  const m2Box = new THREE.Box3();
  const m2Corners: THREE.Vector3[] = [];
  const m2Dir = new THREE.Vector3(0.62, 0.27, 0.73).normalize();
  const m2Cam = new THREE.PerspectiveCamera(24, 1280 / 1080, 0.01, 100);
  let m2Target = new THREE.Vector3();
  let m2Distance = 6;

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
      dir.applyAxisAngle(new THREE.Vector3(1, 0, 0), orbitAngle(t));
      camera.position.copy(target).addScaledVector(dir, distance);
      camera.lookAt(target);
      if (t > 10.1) {
        const startDir = dirEnd.clone().applyAxisAngle(new THREE.Vector3(1, 0, 0), orbitAngle(10.1));
        const startTarget = ring.target.clone();
        const qa = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), startDir);
        const qb = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), m2Dir);
        // Front-loaded but still starts and ends at rest.
        // Front-loaded, but with bounded acceleration at both ends.
        const u2 = seg(t, 10.1, 16.6);
        const k = 1 - Math.pow(1 - u2, 3) * (1 + 3 * u2);
        const moveDir = new THREE.Vector3(0, 0, 1).applyQuaternion(qa.slerp(qb, k));
        const moveTarget = startTarget.clone().lerp(m2Target, k);
        const moveDistance = Math.exp(lerp(Math.log(ring.distance), Math.log(m2Distance), k));
        camera.position.copy(moveTarget).addScaledVector(moveDir, moveDistance);
        camera.lookAt(moveTarget);
        camTargetNow = moveTarget;
      }
      if (t > 17.0) {
        const u3 = seg(t, 17.0, 21.9);
        const k3 = 1 - Math.pow(1 - u3, 3) * (1 + 3 * u3);
        const target3 = m2Target.clone().lerp(m3FitTarget, k3);
        const from = m2Target.clone().addScaledVector(m2Dir, m2Distance);
        camera.position.copy(from.lerp(m3FitPos, k3));
        camera.lookAt(target3);
        camTargetNow = target3;
      }
    }
    if (t <= 5) camTargetNow = targetStart.clone();
    else if (t <= 7.3) camTargetNow = targetStart.clone().lerp(ring.target, smootherAt(t, 5.0, 7.3));
    else if (t <= 10.1) camTargetNow = ring.target.clone();
    // beyond 10.1 the move sets its own target
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
  type HeroMat = THREE.MeshStandardMaterial;
  const heroColors: { material: HeroMat; base: THREE.Color; metalness: number; roughness: number; env: number }[] = [];
  hero.root.traverse(o => {
    const mesh = o as THREE.Mesh & { isLineSegments2?: boolean; userData: { openShell?: boolean } };
    if (!mesh.isMesh || mesh.isLineSegments2 || mesh.userData.openShell) return;
    for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
      const mat = m as HeroMat;
      if (!mat.color || heroColors.some(e => e.material === mat)) continue;
      heroColors.push({
        material: mat, base: mat.color.clone(),
        metalness: mat.metalness ?? 1, roughness: mat.roughness ?? 0.5, env: mat.envMapIntensity ?? 1,
      });
    }
  });
  const bladeComp = components.find(c => c.meta.id === RING);
  let ringMat: THREE.MeshStandardMaterial | null = null;
  bladeComp?.group.traverse(o => {
    const m = o as THREE.Mesh;
    if (!m.isMesh || ringMat) return;
    for (const mat of Array.isArray(m.material) ? m.material : [m.material]) {
      const std = mat as THREE.MeshStandardMaterial;
      if (std.color) { ringMat = std; break; }
    }
  });
  // Assigned inside a callback, so read it back through a cast.
  const ringFound = ringMat as THREE.MeshStandardMaterial | null;
  const ringColor = ringFound ? ringFound.color.clone() : new THREE.Color('#8d9194');
  const ringPbr = {
    metalness: ringFound?.metalness ?? 0.9,
    roughness: ringFound?.roughness ?? 0.4,
    env: ringFound?.envMapIntensity ?? 1,
  };

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
      const snap = instanceSnapshots.get(bladeMesh)!;
      matrix.fromArray(snap, (n - 1) * 16);
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

  // One depth-only shell over the whole ring hides the back-side blade lines.
  let ringShell: THREE.Mesh | null = null;
  if (bladeMesh && !mask) {
    const shell = bladeMesh.clone() as THREE.Mesh & { instanceMatrix?: THREE.InstancedBufferAttribute };
    const sm = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: true, side: THREE.DoubleSide });
    sm.polygonOffset = true;
    sm.polygonOffsetFactor = 1;
    sm.polygonOffsetUnits = 1;
    shell.material = sm;
    shell.instanceMatrix = bladeMesh.instanceMatrix;
    shell.matrixAutoUpdate = false;
    shell.matrix.copy(bladeMesh.matrix);
    shell.castShadow = false;
    shell.receiveShadow = false;
    shell.renderOrder = 10;
    bladeMesh.parent!.add(shell);
    ringShell = shell;
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
  // The disc is thin, so the reveal runs downwards across it: every point can
  // only go from outline to metal, whichever side the camera is on.
  const discPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
  const discAbove = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const discBox = new THREE.Box3();
  engineGroup.matrix.identity();
  engineGroup.updateMatrixWorld(true);
  for (const part of engine.listParts(DISC)) {
    const pts = engine.partWorldPoints(part);
    if (!pts) continue;
    for (let i = 0; i < pts.length; i += 3) discBox.expandByPoint(new THREE.Vector3(pts[i], pts[i + 1], pts[i + 2]));
  }
  engineGroup.matrix.copy(Qinv);
  engineGroup.updateMatrixWorld(true);
  const discTop = discBox.max.y + 0.05, discBottom = discBox.min.y - 0.05;

  function discAt(t: number) {
    if (solo) { engine.setVisible(DISC, false); return; }
    const appear = smootherAt(t, 5.0, 5.6);
    engine.setVisible(DISC, appear > 0.001);
    const sweep = smootherAt(t, 5.9, 6.9);
    const y = lerp(discTop, discBottom, sweep);
    // Material keeps what is above the plane (already revealed); the white
    // stand-in for unswept metal keeps what is below it.
    discPlane.set(new THREE.Vector3(0, 1, 0), -y);
    discAbove.set(new THREE.Vector3(0, -1, 0), y);
    for (const line of discLines) line.visible = appear > 0.001 && sweep < 0.999;
    // Keep the plane attached from the first frame: at sweep 0 it sits at the
    // top of the disc, so nothing is drawn as metal until the sweep descends.
    const clip = maskMode === 'disk' ? false : sweep < 0.999;
    for (const m of discMaterials) if (!m.userData.maskFix) m.clippingPlanes = clip ? [discPlane] : null;
  }

  // ---- blades on the ring -------------------------------------------------
  for (let n = 1; n <= 100; n++) engine.setVisible(bladeId(n), false);
  let shownNow = 0;
  function solidBlades(t: number) {
    let n = t >= 7.60 ? 1 : 0;
    for (let k = 2; k <= 100; k++) if (t + 1e-9 >= bladeStart(k) + outlineFor(k)) n = k;
    return n;
  }
  let solidNow = -1;
  function ringAt(t: number) {
    if (solo) { engine.setVisible(RING, false); if (ringShell) ringShell.visible = false; return; }
    const shown = bladesShown(t);
    const solid = solidBlades(t);
    if (shown !== shownNow || solid !== solidNow) {
      for (let n = 1; n <= 100; n++) engine.setVisible(bladeId(n), n <= solid);
      shownNow = shown;
      solidNow = solid;
    }
    for (let n = 1; n <= 100; n++) {
      const outline = ringOutlines[n - 1];
      if (!outline) continue;
      const start = n === 1 ? 7.4 : bladeStart(n);
      const width = n === 1 ? 0 : outlineFor(n);
      outline.visible = n <= shown && t < start + width && !noLines;
    }
    if (ringShell) ringShell.visible = t < 8.75 && !hideShell('ring');
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
    const nodes: string[] = ['blade'];
    const appearMap: Record<string, number> = { blade: appear };
    if (two) { nodes.push('c-t1'); appearMap['c-t1'] = smootherAt(t, 8.8, 9.2); }
    for (const node of [...M2_NODES, ...M3_NODES]) {
      if (t < node.time) continue;
      nodes.push(node.id);
      appearMap[node.id] = smootherAt(t, node.time, node.time + 0.4);
    }
    const drawing: { from: string; to: string; progress: number }[] = [];
    const litEdges: [string, string][] = [];
    const doneEdges: [string, string][] = [];
    let drawn = 0;
    if (t >= 8.6) {
      const p = smootherAt(t, 8.6, 8.85);
      if (p >= 0.999) { litEdges.push(['c-t1', 'blade']); doneEdges.push(['c-t1', 'blade']); drawn++; }
      else drawing.push({ from: 'blade', to: 'c-t1', progress: p });
    }
    for (const e of [...M2_EDGES, ...M3_EDGES]) {
      if (t < e.time || !nodes.includes(e.from) || !nodes.includes(e.to)) continue;
      const p = smootherAt(t, e.time, e.time + ((e as { dur?: number }).dur ?? 0.3));
      if (p >= 0.999) { litEdges.push([e.from, e.to]); doneEdges.push([e.from, e.to]); drawn++; }
      else drawing.push({ from: e.from, to: e.to, progress: p });
    }
    const captions: string[] = [];
    if (two) captions.push('涡轮叶环');
    if (t >= compStart(0)) captions.push('压气机叶环');
    lastGraphNodes = nodes;
    const pulse: Record<string, number> = {};
    for (const f of M2_FLASH) {
      const v = seg(t, f.time, f.time + (f.dur ?? 0.4));
      if (v > 0 && v < 1) pulse[f.id] = v;
    }
    lastPulse = Object.keys(pulse);
    renderGraph(graphEl, {
      focus: false, lit: nodes, litEdges, chip: {}, status: {}, timing: [],
      only: nodes,
      sub: { blade: `×${Math.max(1, shown)}` },
      appear: appearMap,
      counter: `${nodes.length} 个节点 · ${drawn} 条关系`,
      drawing,
      onlyEdges: doneEdges,
      edgeWidth: 1.5,
      pulse,
      captions,
    });
  }

  // ---- milestone two: turbine stages 2-5, shaft, compressor ----------------
  const STAGE_GROUPS: { ids: string[]; start: number; node: string }[] = [
    { ids: ['turbine.stage-2-blades', 'turbine.stage-2-hub', 'turbine.stage-2-outer', 'turbine.stage-2-tip-ring', 'turbine.stage-1-outer', 'turbine.stage-1-tip-ring'], start: 10.10, node: 'c-t2' },
    { ids: ['turbine.stage-3-blades', 'turbine.stage-3-hub', 'turbine.stage-3-outer', 'turbine.stage-3-tip-ring'], start: 10.70, node: 'c-t3' },
    { ids: ['turbine.stage-4-blades', 'turbine.stage-4-outer', 'turbine.stage-4-tip-ring'], start: 11.30, node: 'c-t4' },
    { ids: ['turbine.stage-5-blades', 'turbine.stage-5-hub', 'turbine.stage-5-outer', 'turbine.stage-5-tip-ring'], start: 11.90, node: 'c-t5' },
  ];
  const COMP_ORDER = ['compressor.stage-4', 'compressor.stators', 'compressor.stage-3', 'compressor.struts', 'compressor.stage-2', 'compressor.stage-1', 'compressor.drum', 'compressor.inlet-bell'];
  const compStart = (i: number) => 13.50 + 2.40 * Math.pow(i / 7, 0.7);

  type Piece = {
    ids: string[]; meshes: THREE.Mesh[]; mats: THREE.Material[]; lines: LineSegments2[];
    box: THREE.Box3; plane: THREE.Plane; linePlane: THREE.Plane; shells: THREE.Mesh[]; start: number; dur: number; axis: 'y' | 'xp' | 'xm';
    outlineTo: number; sweepFrom: number; sweepTo: number;
    flash: THREE.Color; idle: number; tints: { mat: HeroMat; base: THREE.Color; metal: number; rough: number; env: number }[];
  };
  const pieces: Piece[] = [];


  function buildEdges(mesh: THREE.Mesh, mat: LineMaterial) {
    const edges = new THREE.EdgesGeometry(mesh.geometry, 25);
    const pos = edges.getAttribute('position') as THREE.BufferAttribute;
    const inst = mesh as THREE.InstancedMesh;
    const count = inst.isInstancedMesh ? inst.count : 1;
    const out: number[] = [];
    const m = new THREE.Matrix4();
    const v = new THREE.Vector3();
    for (let k = 0; k < count; k++) {
      if (inst.isInstancedMesh) {
        const snap = instanceSnapshots.get(inst);
        if (snap) m.fromArray(snap, k * 16); else inst.getMatrixAt(k, m);
      } else m.identity();
      for (let i = 0; i < pos.count; i++) {
        v.fromBufferAttribute(pos, i).applyMatrix4(m);
        out.push(v.x, v.y, v.z);
      }
    }
    edges.dispose();
    const lines = new LineSegments2(new LineSegmentsGeometry().setPositions(out), mat);
    lines.computeLineDistances();
    lines.visible = false;
    return lines;
  }

  function addPiece(ids: string[], start: number, dur: number, axis: 'y' | 'xp' | 'xm', outlineTo: number, sweepFrom: number, sweepTo: number) {
    const mats: THREE.Material[] = [];
    const meshes: THREE.Mesh[] = [];
    const tints: { mat: HeroMat; base: THREE.Color; metal: number; rough: number; env: number }[] = [];
    const lines: LineSegments2[] = [];
    const shells: THREE.Mesh[] = [];
    const lineMat = new LineMaterial({ color: 0x4e5e6b, linewidth: 1.2, transparent: true, opacity: 1, depthWrite: false });
    const shellMat = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: true, side: THREE.DoubleSide });
    shellMat.polygonOffset = true;
    shellMat.polygonOffsetFactor = 1;
    shellMat.polygonOffsetUnits = 1;
    lineMat.resolution.set(1280, 1080);
    let base: THREE.Color | null = null;
    for (const id of ids) {
      const comp = components.find(c => c.meta.id === id);
      if (!comp) continue;
      const found: THREE.Mesh[] = [];
      comp.group.traverse(o => {
        const mesh = o as THREE.Mesh & { isLineSegments2?: boolean };
        if (mesh.isMesh && !mesh.isLineSegments2 && mesh.geometry) found.push(mesh);
      });
      for (const mesh of found) {
        const source = (Array.isArray(mesh.material) ? mesh.material[0] : mesh.material) as HeroMat;
        const cloned = source.clone();
        mesh.material = cloned;
        mats.push(cloned);
        meshes.push(mesh);
        if (cloned.color) tints.push({ mat: cloned, base: cloned.color.clone(), metal: cloned.metalness ?? 1, rough: cloned.roughness ?? 0.5, env: cloned.envMapIntensity ?? 1 });
        if (!base && cloned.color) base = cloned.color.clone();
        if (!mask) {
          const l = buildEdges(mesh, lineMat);
          mesh.add(l);
          lines.push(l);
          // Depth-only twin of the unswept half, so interior lines stay hidden.
          const twin = mesh.clone() as THREE.Mesh & { instanceMatrix?: THREE.InstancedBufferAttribute };
          const source = mesh as THREE.Mesh & { instanceMatrix?: THREE.InstancedBufferAttribute };
          if (source.instanceMatrix) twin.instanceMatrix = source.instanceMatrix;
          twin.material = shellMat;
          twin.matrixAutoUpdate = false;
          twin.matrix.copy(mesh.matrix);
          twin.castShadow = false;
          twin.receiveShadow = false;
          twin.renderOrder = 10;
          mesh.parent!.add(twin);
          shells.push(twin);
        }
      }
    }
    const box = new THREE.Box3();
    for (const id of ids) for (const part of engine.listParts(id)) {
      const pts = engine.partWorldPoints(part);
      if (!pts) continue;
      for (let i = 0; i < pts.length; i += 3) box.expandByPoint(new THREE.Vector3(pts[i], pts[i + 1], pts[i + 2]));
    }
    // One instance-colour multiplier for the whole piece: a per-material ratio
    // tuned for one part reads differently on the rest.
    const flash = new THREE.Color(0.55, 1.00, 2.40);
    void base;
    const piece: Piece = { ids, meshes, mats, lines, shells, box, plane: new THREE.Plane(), linePlane: new THREE.Plane(), start, dur, axis, outlineTo, sweepFrom, sweepTo, flash, idle: 0, tints };
    for (const m of mats) m.clippingPlanes = [piece.plane];
    engine.setVisible(ids, false);
    pieces.push(piece);
    return piece;
  }

  engineGroup.matrix.identity();
  engineGroup.updateMatrixWorld(true);
  const stagePieces = STAGE_GROUPS.map(g => addPiece(g.ids, g.start, 0.6, 'y', 0.10, 0.20, 0.55));
  const shaftPiece = addPiece(['shaft.main'], 12.70, 1.0, 'xp', 0.10, 0.25, 1.00);
  const compPieces = COMP_ORDER.map((id, i) => addPiece([id], compStart(i), 0.4, 'y', 0.08, 0.14, 0.40));
  const M3_PIECES: { ids: string[]; start: number; axis: 'y' | 'xp' | 'xm'; outlineTo: number; sweepTo: number; node: string }[] = [
    { ids: ['combustor.cans', 'combustor.casing', 'combustor.injectors', 'combustor.inner-shell'], start: 17.00, axis: 'y', outlineTo: 0.20, sweepTo: 0.60, node: 'm-comb' },
    { ids: ['core-casing.bolts', 'core-casing.drum', 'core-casing.inner-wall', 'core-casing.tiles', 'turbine.band', 'turbine.inner-cone'], start: 17.80, axis: 'y', outlineTo: 0.20, sweepTo: 0.70, node: 'm-core' },
    { ids: ['fan.hub', 'fan.inner-shroud'], start: 18.70, axis: 'y', outlineTo: 0.15, sweepTo: 0.55, node: 'm-fan' },
    { ids: ['fan-cowl.aft', 'fan-cowl.lip', 'fan-cowl.shell'], start: 20.20, axis: 'xm', outlineTo: 0.20, sweepTo: 0.90, node: 'm-cowl' },
    { ids: ['nacelle.duct'], start: 20.20, axis: 'xp', outlineTo: 0.20, sweepTo: 0.90, node: 'm-nac' },
    { ids: ['exhaust.bolts', 'exhaust.fittings', 'exhaust.nozzle', 'exhaust.tail-cone'], start: 21.30, axis: 'xm', outlineTo: 0.15, sweepTo: 0.60, node: 'm-exh' },
    { ids: ['fan.spinner'], start: 21.30, axis: 'xm', outlineTo: 0.15, sweepTo: 0.60, node: '' },
  ];
  const m3Pieces = M3_PIECES.map(m => ({ ...m, piece: addPiece(m.ids, m.start, m.sweepTo, m.axis, m.outlineTo, m.outlineTo, m.sweepTo) }));

  // Fan blades fill in one at a time, outline first, like the first-stage ring.
  const FAN = 'fan.blades';
  const fanStart = (k: number) => 19.10 + 0.05 * (k - 1);
  const fanOutline = 0.12;
  const fanComp = components.find(c => c.meta.id === FAN);
  const fanMesh = (() => {
    let best: THREE.InstancedMesh | null = null;
    fanComp?.group.traverse(o => {
      const m = o as THREE.InstancedMesh;
      if (m.isInstancedMesh && (!best || m.count > best.count)) best = m;
    });
    return best as THREE.InstancedMesh | null;
  })();
  const fanTotal = engine.listParts(FAN).length;
  const fanOutlines: LineSegments2[] = [];
  const fanMat = new LineMaterial({ color: 0x4e5e6b, linewidth: 1.2, transparent: true, opacity: 1, depthWrite: false });
  fanMat.resolution.set(1280, 1080);
  let fanShell: THREE.Mesh | null = null;
  if (fanMesh && !mask) {
    const edges = new THREE.EdgesGeometry(fanMesh.geometry, 25);
    const base = new LineSegmentsGeometry().fromEdgesGeometry(edges);
    const snap = instanceSnapshots.get(fanMesh)!;
    const matrix = new THREE.Matrix4();
    const src = (base.attributes.instanceStart as THREE.InterleavedBufferAttribute).data.array as Float32Array;
    const segments = base.attributes.instanceStart.count;
    const v = new THREE.Vector3();
    for (let k = 0; k < fanMesh.count; k++) {
      matrix.fromArray(snap, k * 16);
      const arr: number[] = [];
      for (let i = 0; i < segments; i++) {
        for (const off of [i * 3, (i + 1) * 3]) {
          v.set(src[off], src[off + 1], src[off + 2]).applyMatrix4(matrix);
          arr.push(v.x, v.y, v.z);
        }
      }
      const lines = new LineSegments2(new LineSegmentsGeometry().setPositions(arr), fanMat);
      lines.computeLineDistances();
      lines.visible = false;
      scene.add(lines);
      fanOutlines.push(lines);
    }
    edges.dispose();
    const shell = fanMesh.clone() as THREE.Mesh & { instanceMatrix?: THREE.InstancedBufferAttribute };
    const sm = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: true, side: THREE.DoubleSide });
    sm.polygonOffset = true;
    sm.polygonOffsetFactor = 1;
    sm.polygonOffsetUnits = 1;
    shell.material = sm;
    shell.instanceMatrix = fanMesh.instanceMatrix;
    shell.matrixAutoUpdate = false;
    shell.matrix.copy(fanMesh.matrix);
    shell.castShadow = false;
    shell.receiveShadow = false;
    shell.renderOrder = 10;
    fanMesh.parent!.add(shell);
    fanShell = shell;
  }
  let fanSolidNow = -1;
  function fanAt(t: number) {
    if (solo || partMask || !fanMesh) return;
    const total = fanTotal;
    let solid = 0;
    for (let k = 1; k <= total; k++) if (t + 1e-9 >= fanStart(k) + fanOutline) solid = k;
    if (solid !== fanSolidNow) {
      for (let k = 1; k <= total; k++) engine.setVisible(`${FAN}.${String(k).padStart(3, '0')}`, k <= solid);
      fanSolidNow = solid;
    }
    for (let k = 1; k <= total; k++) {
      const line = fanOutlines[k - 1];
      if (line) line.visible = t >= fanStart(k) && t < fanStart(k) + fanOutline && !noLines;
    }
    const tips = components.find(c => c.meta.id === 'fan.blade-tips');
    if (tips) engine.setVisible('fan.blade-tips', t >= fanStart(1) + fanOutline);
    if (fanShell) fanShell.visible = t < 21.0 && !hideShell('fan');
  }
  engineGroup.matrix.copy(Qinv);
  engineGroup.updateMatrixWorld(true);

  function pieceAt(p: Piece, t: number) {
    const on = t >= p.start;
    engine.setVisible(p.ids, on);
    for (const l of p.lines) l.visible = on && !noLines;
    for (const sh of p.shells) sh.visible = on;
    if (!on) return 0;
    const alpha = smootherAt(t, p.start, p.start + p.outlineTo);
    const u = smootherAt(t, p.start + p.sweepFrom, p.start + p.sweepTo);
    const linesOn = u < 0.999;
    for (const l of p.lines) {
      const mat = l.material as LineMaterial;
      mat.opacity = alpha;
      mat.visible = linesOn && alpha > 0.001 && !noLines;
      mat.clippingPlanes = [p.linePlane];
    }
    for (const sh of p.shells) {
      sh.visible = linesOn && !hideShell('piece');
      (sh.material as THREE.Material).clippingPlanes = [p.linePlane];
    }
    if (p.axis === 'y') {
      const h = lerp(p.box.max.y + 0.02, p.box.min.y - 0.02, u);
      p.plane.set(new THREE.Vector3(0, 1, 0), -h);
      p.linePlane.set(new THREE.Vector3(0, -1, 0), h);
    } else if (p.axis === 'xp') {
      const h = lerp(p.box.min.x - 0.02, p.box.max.x + 0.02, u);
      p.plane.set(new THREE.Vector3(-1, 0, 0), h);
      p.linePlane.set(new THREE.Vector3(1, 0, 0), -h);
    } else {
      const h = lerp(p.box.max.x + 0.02, p.box.min.x - 0.02, u);
      p.plane.set(new THREE.Vector3(1, 0, 0), -h);
      p.linePlane.set(new THREE.Vector3(-1, 0, 0), h);
    }
    if (u >= 0.999) {
      for (const m of p.mats) m.clippingPlanes = null;
      for (const l of p.lines) { l.visible = false; (l.material as LineMaterial).clippingPlanes = null; }
      for (const sh of p.shells) sh.visible = false;
      return 1;
    }
    for (const m of p.mats) m.clippingPlanes = [p.plane];
    return u;
  }

  // ---- milestone two: graph and flashes ------------------------------------
  const M2_NODES: { id: string; time: number; pieces: Piece[] }[] = [
    ...STAGE_GROUPS.map((g, i) => ({ id: g.node, time: g.start, pieces: [stagePieces[i]] })),
    { id: 'm-turb', time: 12.60, pieces: stagePieces },
    { id: 'm-shaft', time: 12.70, pieces: [shaftPiece] },
    { id: 'c-comp4', time: compStart(0), pieces: [compPieces[0]] },
    { id: 'c-comp3', time: compStart(2), pieces: [compPieces[2]] },
    { id: 'c-comp2', time: compStart(4), pieces: [compPieces[4]] },
    { id: 'c-comp1', time: compStart(5), pieces: [compPieces[5]] },
    { id: 'm-comp', time: 16.30, pieces: compPieces },
  ];
  const M3_NODES: { id: string; time: number; pieces: Piece[] }[] = [
    { id: 'm-comb', time: 17.00, pieces: [] },
    { id: 'm-core', time: 17.80, pieces: [] },
    { id: 'm-fan', time: 18.70, pieces: [] },
    { id: 'c-fan', time: 19.10, pieces: [] },
    { id: 'm-nac', time: 20.20, pieces: [] },
    { id: 'm-cowl', time: 20.20, pieces: [] },
    { id: 'm-exh', time: 21.30, pieces: [] },
    { id: 'e7', time: 22.00, pieces: [] },
  ];
  const MODULE_ORDER = ['m-fan', 'm-cowl', 'm-comp', 'm-comb', 'm-turb', 'm-exh', 'm-core', 'm-nac', 'm-shaft'];
  const M3_EDGES: { from: string; to: string; time: number; dur?: number }[] = [
    { from: 'c-fan', to: 'm-fan', time: 19.10 },
    ...MODULE_ORDER.map((id, i) => ({ from: id, to: 'e7', time: 22.00 + i * 0.01, dur: 0.18 })),
  ];
  const M2_EDGES: { from: string; to: string; time: number }[] = [
    ...['c-t1', 'c-t2', 'c-t3', 'c-t4', 'c-t5'].map((id, i) => ({ from: id, to: 'm-turb', time: 12.60 + i * 0.05 })),
    ...['c-comp1', 'c-comp2', 'c-comp3', 'c-comp4'].map((id, i) => ({ from: id, to: 'm-comp', time: 16.30 + i * 0.06 })),
  ];
  // Every part's own colour, read once, so a flash can return to it exactly.
  const LIT_SRGB = LIT.clone().convertLinearToSRGB();
  type Tint = { mesh?: THREE.InstancedMesh; index?: number; mat?: HeroMat; base: THREE.Color };
  const pieceTints: Tint[][] = pieces.map(() => []);
  for (let pi = 0; pi < pieces.length; pi++) {
    const p = pieces[pi];
    engine.setColor(p.ids, null);
    for (const mesh of p.meshes) {
      const inst = mesh as THREE.InstancedMesh;
      const arr = inst.instanceColor?.array as Float32Array | undefined;
      if (inst.isInstancedMesh && arr) {
        for (let i = 0; i < inst.count; i++) {
          pieceTints[pi].push({ mesh: inst, index: i, base: new THREE.Color(arr[i * 3], arr[i * 3 + 1], arr[i * 3 + 2]) });
        }
      } else {
        const mat = mesh.material as HeroMat;
        pieceTints[pi].push({ mat, base: mat.color.clone() });
      }
    }
  }
  const flashOf = (piece: Piece) => piece.start + piece.sweepTo;
  // Every piece flashes as it finishes laying metal. The spinner has no node of
  // its own (it belongs to the fan), so its pulse lands on a name no node has.
  const M2_FLASH: { id: string; time: number; pieces: Piece[]; amp?: number; dur?: number }[] = [
    ...m3Pieces.map(m => ({ id: m.node ?? 'fan-spinner', time: m.piece.start + m.piece.sweepTo, pieces: [m.piece] })),
    { id: 'e7', time: 22.00, pieces: [...stagePieces, ...compPieces, ...m3Pieces.map(m => m.piece)], amp: 0.15, dur: 0.5 },
    ...STAGE_GROUPS.map((g, i) => ({ id: g.node, time: flashOf(stagePieces[i]), pieces: [stagePieces[i]] })),
    { id: 'm-turb', time: 12.60, pieces: stagePieces },
    { id: 'm-shaft', time: flashOf(shaftPiece), pieces: [shaftPiece] },
    { id: 'c-comp4', time: flashOf(compPieces[0]), pieces: [compPieces[0]] },
    { id: 'c-comp3', time: flashOf(compPieces[2]), pieces: [compPieces[2]] },
    { id: 'c-comp2', time: flashOf(compPieces[4]), pieces: [compPieces[4]] },
    { id: 'c-comp1', time: flashOf(compPieces[5]), pieces: [compPieces[5]] },
    { id: 'm-comp', time: 16.30, pieces: compPieces },
  ];
  const noFlash = params.get('noflash') === '1';
  const noLines = params.get('nolines') === '1';
  function writeTint(tint: Tint, colour: THREE.Color) {
    if (tint.mesh) {
      tint.mesh.setColorAt(tint.index!, colour);
      tint.mesh.instanceColor!.needsUpdate = true;
    } else if (tint.mat) {
      tint.mat.color.copy(colour);
    }
  }
  // Only the milestone-two pieces, so the aim matches a15ba3a.
  for (const p of [...stagePieces, shaftPiece, ...compPieces]) m2Box.union(p.box);
  m2Target = m2Box.getCenter(new THREE.Vector3());
  for (const x of [m2Box.min.x, m2Box.max.x]) for (const y of [m2Box.min.y, m2Box.max.y]) for (const z of [m2Box.min.z, m2Box.max.z]) m2Corners.push(new THREE.Vector3(x, y, z));
  for (let i = 0; i < 10; i++) {
    m2Cam.position.copy(m2Target).addScaledVector(m2Dir, m2Distance);
    m2Cam.lookAt(m2Target);
    m2Cam.updateMatrixWorld();
    let ex = 0, ey = 0;
    for (const c of m2Corners) {
      const q = c.clone().project(m2Cam);
      ex = Math.max(ex, Math.abs(q.x));
      ey = Math.max(ey, Math.abs(q.y));
    }
    m2Distance *= Math.max(ex / 0.84, ey / 0.80);
  }

  function m2At(t: number) {
    if (t < 9.6) return;
    for (const p of pieces) {
      if (solo && !p.ids.some(id => solo.includes(id))) continue;
      pieceAt(p, t);
    }
    fanAt(t);
    // Flash strength is a pure function of t; a piece shared by two nodes takes
    // the stronger one, and each part's colour is written once per frame.
    const amounts = new Map<Piece, number>();
    for (const node of M2_FLASH) {
      const p = seg(t, node.time, node.time + (node.dur ?? 0.4));
      if (p <= 0 || p >= 1 || noFlash) continue;
      const a = Math.sin(Math.PI * p) * (node.amp ?? 0.25);
      for (const piece of node.pieces) amounts.set(piece, Math.max(amounts.get(piece) ?? 0, a));
    }
    for (let pi = 0; pi < pieces.length; pi++) {
      const a = amounts.get(pieces[pi]) ?? 0;
      const piece = pieces[pi];
      if (a <= 0.0005) {
        if (piece.idle !== 1) {
          for (const tint of pieceTints[pi]) writeTint(tint, tint.base);
          piece.idle = 1;
        }
        continue;
      }
      piece.idle = 0;
      for (const tint of pieceTints[pi]) {
        writeTint(tint, tint.base.clone().convertLinearToSRGB().lerp(LIT_SRGB, a).convertSRGBToLinear());
      }
    }
  }

  // ---- frame --------------------------------------------------------------
  let lastBladeState = '';
  let appliedT = 0;
  let lastGraphNodes: string[] = [];
  let lastPulse: string[] = [];
  function attached(t: number) {
    appliedT = t;
    discAt(t);
    ringAt(t);
  }
  // Spin up 22.0-23.2, cruise to 26.0, ease out by 28.0: the integral is
  // 0.6 + 2.8 + 1.0 = 4.4 turns at omega, so the blades stop on 360 degrees.
  const OMEGA = 360 / 4.4;
  const rotorIntegral = (u: number) => u ** 6 - 3 * u ** 5 + 2.5 * u ** 4;
  function rotorDegrees(t: number) {
    if (t <= 22.0) return 0;
    if (t >= 28.0) return 360;
    const ramp = Math.min(1, (t - 22.0) / 1.2);
    const cruise = Math.max(0, Math.min(t, 26.0) - 23.2);
    const easeOut = t > 26.0 ? (t - 26.0) - 2 * rotorIntegral((t - 26.0) / 2) : 0;
    return OMEGA * (1.2 * rotorIntegral(ramp) + cruise + easeOut);
  }
  const rotorGroups = engine.modules.flatMap(m => m.components).filter(c => c.rotor).map(c => c.group);
  let rotorNow = 0;
  function rotorAt(t: number) {
    const deg = params.get('norotor') === '1' ? 0 : rotorDegrees(t);
    rotorNow = deg;
    for (const g of rotorGroups) g.rotation.x = -THREE.MathUtils.degToRad(deg);
  }

  function apply(t: number, render = true) {
    appliedT = t;
    if (t < 5.0 && !diskMode) {
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
    const fade = params.get('nofade') === '1'
      ? (t >= 7.30 ? 1 : 0)
      : smootherAt(t, 7.30, 7.60);
    hero.root.updateMatrixWorld(true);
    open.hero.root.visible = fade < 0.999;
    if (partMask) {
      hero.root.visible = false;
      open.hero.root.visible = false;
      engine.setVisible(RING, false);
      engine.setVisible(DISC, false);
      cameraAt(t);
      lightsAt(t);
      appliedT = t;
      if (render) view.render();
      return;
    }
    if (diskMode) {
      hero.root.visible = false;
      open.hero.root.visible = false;
      engine.setVisible(RING, false);
      cameraAt(t);
      lightsAt(t);
      discAt(t);
      if (render) view.render();
      return;
    }
    cameraAt(t);
    lightsAt(t);
    discAt(t);
    ringAt(t);
    flashAt(Math.min(t, 9.3));
    // Hand the hero blade over to the ring's own metal before the cross-fade.
    const handoff = smootherAt(t, 5.0, 7.30);
    for (const entry of heroColors) {
      entry.material.color.copy(entry.base).lerp(ringColor, handoff);
      entry.material.metalness = lerp(entry.metalness, ringPbr.metalness, handoff);
      entry.material.roughness = lerp(entry.roughness, ringPbr.roughness, handoff);
      entry.material.envMapIntensity = lerp(entry.env, ringPbr.env, handoff);
      const opacity = 1 - fade;
      if (Math.abs(entry.material.opacity - opacity) > 0.002 || entry.material.transparent !== (opacity < 0.999)) {
        entry.material.opacity = opacity;
        entry.material.transparent = opacity < 0.999;
        entry.material.needsUpdate = true;
      }
    }
    // Touch blade 001 only while it is changing, so the resulting engine state
    // is the same however the playhead got here.
    const bladeState = t < 7.30 ? 'hidden' : fade >= 0.999 ? 'solid' : 'fading';
    if ((solo || partMask) && bladeState !== 'hidden') {
      engine.setVisible(bladeId(1), false);
    } else if (bladeState === 'fading') {
      engine.setVisible(bladeId(1), true);
      engine.setOpacity(bladeId(1), fade);
    } else if (bladeState !== lastBladeState) {
      engine.setVisible(bladeId(1), bladeState === 'solid');
      // Restoring through the whole ring puts the part back in the shared mesh,
      // so it draws with the same depth state as every other blade.
      if (bladeState === 'solid') engine.setOpacity(engine.listParts(RING), 1);
    }
    lastBladeState = bladeState;
    if (t >= 9.6) m2At(t);
    rotorAt(t);
    graphAt(t);
    if (!mask) {
      const first = firstBladeTip();
      const fade = 1 - seg(t, 6.6, 7.1);
      if (first && t >= 1.8 && fade > 0) line(firstPath, firstDot, first, { x: 1573, y: 410 }, 9, clamp01((t - 1.8) / 1.4), 0.85 * fade);
      else { firstPath.style.opacity = '0'; firstDot.style.opacity = '0'; }
      const tip = t >= 8.8 ? bladeTipScreen(100) : null;
      const threadFade = 1 - smootherAt(t, 9.6, 10.1);
      if (tip && threadFade > 0.002) line(secondPath, secondDot, tip, { x: 1573, y: 330 }, 6, seg(t, 8.8, 9.2), 0.85 * threadFade);
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
      fadeBox: (() => {
        let x0 = bx0, y0 = by0, x1 = bx1, y1 = by1;
        const pts = engine.partWorldPoints(bladeId(1));
        if (pts) {
          for (let i = 0; i < pts.length; i += 3) {
            const q = view.project(new THREE.Vector3(pts[i], pts[i + 1], pts[i + 2]));
            x0 = Math.min(x0, q.x); y0 = Math.min(y0, q.y);
            x1 = Math.max(x1, q.x); y1 = Math.max(y1, q.y);
          }
        }
        return [x0 - 8, y0 - 8, x1 + 8, y1 + 8];
      })(),
      blades: { count: shownNow, solid: solidNow, ids: Array.from({ length: shownNow }, (_, i) => bladeId(i + 1)) },
      graph: { nodes: lastGraphNodes.length, ids: lastGraphNodes, pulse: lastPulse, counter: gtexts.find(x => x.includes('个节点')) ?? '', sub: gtexts.find(x => x.startsWith('×')) ?? '', texts: gtexts },
      threads,
      disc: { top: discTop, bottom: discBottom, parts: engine.listParts(DISC).length },
      rotor: rotorNow,
      shellsOn: [...pieces.filter(p => p.shells.some(sh => sh.visible)).map(p => p.ids[0]),
        ...(ringShell && ringShell.visible ? ['ring'] : []),
        ...(fanShell && fanShell.visible ? ['fan'] : [])],
      rotorIds: components.filter(c => c.rotor).map(c => c.meta.id),
      fit: { position: m3FitPos.toArray(), target: m3FitTarget.toArray() },
      boxes: pieces.map(p => ({ ids: p.ids[0], y: [p.box.min.y, p.box.max.y], x: [p.box.min.x, p.box.max.x], start: p.start, dur: p.dur })),
      components: Object.fromEntries(pieces.flatMap(p => p.ids.map(id => [id, appliedT >= p.start]))),
      visibleParts: engine.listParts(RING).length + engine.listParts(DISC).length
        + (fanSolidNow > 0 ? fanSolidNow : 0)
        + (appliedT >= 19.10 + fanOutline ? 16 : 0)
        + pieces.reduce((n, p) => (appliedT >= p.start ? n + p.ids.reduce((k, id) => k + engine.listParts(id).length, 0) : n), 0),
      seat: view.project(seatPos.clone()),
      seatMatrix: seatMatrix.elements.slice(),
    };
  };

  if (solo) {
    const keep = new Set(solo);
    for (const c of components) if (!keep.has(c.meta.id)) engine.setVisible(c.meta.id, false);
    hero.root.visible = false;
    open.hero.root.visible = false;
  }
  if (mask) {
    const black = new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.DoubleSide, toneMapped: false });
    scene.traverse(o => {
      const m = o as THREE.Mesh & { isLineSegments2?: boolean; userData: { openShell?: boolean } };
      if (m.isMesh && !m.isLineSegments2 && !m.userData.openShell) m.material = black;
    });
    if (partMask) {
      for (const p of pieces) engine.setVisible(p.ids, false);
      engine.setVisible(RING, false);
      engine.setVisible(DISC, false);
      engine.setVisible(partMask, true);
      for (const p of pieces) for (const m of p.mats) m.clippingPlanes = null;
      for (const p of pieces) for (const l of p.lines) l.visible = false;
    }
    for (const piece of pieces) {
      for (const mesh of piece.meshes) {
        const bm = new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.DoubleSide, toneMapped: false });
        bm.clippingPlanes = partMask ? null : [piece.plane];
        mesh.material = bm;
        piece.mats.push(bm);
      }
    }
    if (maskMode === 'disk-solid') {
      // Solid part black (below the sweep), unswept part opaque white (above).
      const blackBelow = new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.DoubleSide, toneMapped: false });
      blackBelow.clippingPlanes = [discPlane];
      blackBelow.userData.maskFix = true;
      for (const mesh of discMeshes) {
        const white = new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide, toneMapped: false });
        white.clippingPlanes = [discAbove];
        white.userData.maskFix = true;
        const twin = mesh.clone();
        twin.material = white;
        mesh.parent!.add(twin);
        mesh.material = blackBelow;
      }
      for (const m of discMaterials) m.userData.maskFix = true;
    }
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
