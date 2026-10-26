import * as THREE from 'three';
import { LineSegments2 } from 'three/examples/jsm/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/examples/jsm/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import { createHeroBlade, bladePoint, outwardNormal } from '../hero-blade';
import { renderGraph } from './graph';
import { createModelView, type Theme } from './scene';

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const smoothstep = (a: number, b: number, x: number) => {
  const u = clamp01((x - a) / (b - a));
  return u * u * (3 - 2 * u);
};

const NODE = { x: 1573, y: 410 };
const TARGET = { x: 520, y: 545 };
const FRAME_HEIGHT = 610;
const YAW_RATE = 8;
const UP = new THREE.Vector3(0, 1, 0);

// The blade silhouette, sampled once in tilt-local space so every yaw is one
// matrix multiply per point.
function samplePoints(root: THREE.Object3D, stride = 1) {
  const out: number[] = [];
  const v = new THREE.Vector3();
  root.traverse(object => {
    const mesh = object as THREE.Mesh;
    if (!mesh.isMesh || !mesh.geometry) return;
    for (let o: THREE.Object3D | null = mesh; o; o = o.parent) if (!o.visible) return;
    const pos = mesh.geometry.getAttribute('position') as THREE.BufferAttribute;
    mesh.updateWorldMatrix(true, false);
    for (let i = 0; i < pos.count; i += stride) {
      v.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld);
      out.push(v.x, v.y, v.z);
    }
  });
  return new Float32Array(out);
}

export async function mountOpen(theme: Theme) {
  const params = new URLSearchParams(location.search);
  const mask = params.get('mask') === '1';
  const frame = document.querySelector<HTMLElement>('#frame')!;
  frame.classList.add('layout-split');

  const view = await createModelView(document.querySelector<HTMLCanvasElement>('#model')!, theme, 1280);
  const { scene, camera } = view;
  scene.background = new THREE.Color(mask ? '#ffffff' : '#eef0ee');

  const hero = createHeroBlade();
  hero.setCutaway(0);
  hero.setCoatings(0);
  hero.setAirflow(0);

  // Spin about the vertical axis through the mid-section, then tilt a little so
  // the tip section shows.
  const center = bladePoint(0.46, 0.5, 1).clone().add(bladePoint(0.46, 0.5, -1)).multiplyScalar(0.5);
  hero.root.position.copy(center.clone().negate());
  const spin = new THREE.Group();
  spin.position.copy(center);
  spin.add(hero.root);
  const tilt = new THREE.Group();
  tilt.rotation.set(THREE.MathUtils.degToRad(5), 0, THREE.MathUtils.degToRad(-4));
  tilt.add(spin);
  scene.add(tilt);
  tilt.updateMatrixWorld(true);

  const tiltMatrix = new THREE.Matrix4().makeRotationFromEuler(tilt.rotation);
  const matrixFor = (yawDeg: number) => new THREE.Matrix4()
    .makeTranslation(center.x, center.y, center.z)
    .multiply(new THREE.Matrix4().makeRotationY(THREE.MathUtils.degToRad(yawDeg)))
    .multiply(new THREE.Matrix4().makeTranslation(-center.x, -center.y, -center.z))
    .premultiply(tiltMatrix);

  // Silhouette samples, taken with both groups at rest.
  const spinYaw = spin.rotation.y;
  spin.rotation.y = 0;
  tilt.rotation.set(0, 0, 0);
  tilt.updateMatrixWorld(true);
  const points = samplePoints(hero.root, 3);
  tilt.rotation.set(THREE.MathUtils.degToRad(5), 0, THREE.MathUtils.degToRad(-4));
  tilt.updateMatrixWorld(true);
  spin.rotation.y = spinYaw;

  const probe = new THREE.Vector3();
  function bboxAt(yawDeg: number) {
    const m = matrixFor(yawDeg);
    const cam = camera;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (let i = 0; i < points.length; i += 3) {
      probe.set(points[i], points[i + 1], points[i + 2]).applyMatrix4(m).project(cam);
      const x = (probe.x * 0.5 + 0.5) * 1280, y = (-probe.y * 0.5 + 0.5) * 1080;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
    return { minX, maxX, minY, maxY, w: maxX - minX, h: maxY - minY };
  }

  function bladeCenter(yawDeg: number) {
    const m = matrixFor(yawDeg);
    const box = new THREE.Box3();
    for (let i = 0; i < points.length; i += 3) box.expandByPoint(new THREE.Vector3(points[i], points[i + 1], points[i + 2]).applyMatrix4(m));
    return box.getCenter(new THREE.Vector3());
  }

  const direction = new THREE.Vector3(0, Math.sin(THREE.MathUtils.degToRad(10)), Math.cos(THREE.MathUtils.degToRad(10))).normalize();

  /** Aim at the blade, then settle distance and pan so it fills the left column. */
  function fit(yawDeg: number) {
    const target = bladeCenter(yawDeg);
    let distance = 10;
    const ax = new THREE.Vector3();
    const ay = new THREE.Vector3();
    for (let i = 0; i < 8; i++) {
      camera.position.copy(target).addScaledVector(direction, distance);
      camera.lookAt(target);
      camera.updateMatrixWorld();
      const b = bboxAt(yawDeg);
      distance = THREE.MathUtils.clamp(distance * (b.h / FRAME_HEIGHT), 3, 60);
      camera.position.copy(target).addScaledVector(direction, distance);
      camera.lookAt(target);
      camera.updateMatrixWorld();
      // Moving the camera towards +right pushes the subject left; the vertical
      // axis is flipped against screen space.
      const wpp = (2 * distance * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) / 1080;
      ax.setFromMatrixColumn(camera.matrixWorld, 0);
      ay.setFromMatrixColumn(camera.matrixWorld, 1);
      const cx = (b.minX + b.maxX) / 2;
      const cy = (b.minY + b.maxY) / 2;
      target.addScaledVector(ax, (cx - TARGET.x) * wpp);
      target.addScaledVector(ay, (TARGET.y - cy) * wpp);
    }
    camera.position.copy(target).addScaledVector(direction, distance);
    camera.lookAt(target);
    camera.updateMatrixWorld();
  }

  function measure(yawDeg: number) {
    const m = matrixFor(yawDeg);
    const front = bladePoint(0.5, 0.5, 1).clone().applyMatrix4(m);
    const lead = bladePoint(0.08, 0.5, 1).clone().applyMatrix4(m);
    const dot = (n: THREE.Vector3, p: THREE.Vector3) => n.transformDirection(m).normalize().dot(camera.position.clone().sub(p).normalize());
    const b = bboxAt(yawDeg);
    return { yaw: yawDeg, A: dot(outwardNormal(0.5, 0.5, 1), front), B: dot(outwardNormal(0.08, 0.5, 1), lead), R: b.w / b.h };
  }

  // Section five: pick the yaw that keeps the curved face and the hole rows in
  // view and never turns the blade into a stick or a slab. 25° won that scan;
  // `&scan=1` recomputes all 72 candidates for the record.
  const Y3 = Number(params.get('yaw') ?? 25);
  if (params.get('scan') === '1') {
    fit(0);
    type Candidate = { yaw: number; A: number; B: number; R: number; R0: number; R5: number };
    const candidates: Candidate[] = [];
    for (let yaw = 0; yaw < 360; yaw += 5) {
      const b0 = bboxAt(yaw - 24);
      const b5 = bboxAt(yaw + 16);
      candidates.push({ ...measure(yaw), R0: b0.w / b0.h, R5: b5.w / b5.h });
    }
    const ok = candidates.filter(c => c.A >= 0.35 && c.B >= 0.25 && c.R >= 0.30 && c.R <= 0.48
      && c.R0 >= 0.22 && c.R5 >= 0.22);
    (window as unknown as { __openScan: () => unknown }).__openScan = () => ({
      chosen: Y3,
      okCount: ok.length,
      candidates: candidates.map(c => ({
        yaw: c.yaw, A: +c.A.toFixed(4), B: +c.B.toFixed(4), R: +c.R.toFixed(4),
        R0: +c.R0.toFixed(4), R5: +c.R5.toFixed(4),
      })),
    });
  }

  fit(Y3);

  // ---- contour lines --------------------------------------------------------
  const lineMat = new LineMaterial({ color: 0x4e5e6b, linewidth: 1.2, transparent: true, opacity: 1, depthWrite: false });
  lineMat.resolution.set(1280, 1080);
  const bladeMaterials = new Set<THREE.Material>();
  const meshes: THREE.Mesh[] = [];
  hero.root.traverse(object => {
    const mesh = object as THREE.Mesh & { isLineSegments2?: boolean };
    if (mesh.isMesh && !mesh.isLineSegments2 && mesh.geometry) meshes.push(mesh);
  });
  // Above the sweep the metal is gone, so interior cooling passages would show
  // through as a jumble of lines. A colour-less shell writes depth only and
  // hides them, leaving just the outline of the part that is not built yet.
  const shellMat = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: true, side: THREE.DoubleSide });
  shellMat.polygonOffset = true;
  shellMat.polygonOffsetFactor = 1;
  shellMat.polygonOffsetUnits = 1;
  if (!mask) {
    for (const mesh of meshes) {
      const shell = new THREE.Mesh(mesh.geometry, shellMat);
      shell.userData.openShell = true;
      shell.renderOrder = -1;
      shell.castShadow = false;
      shell.receiveShadow = false;
      mesh.add(shell);
      const edges = new THREE.EdgesGeometry(mesh.geometry, 25);
      const lines = new LineSegments2(new LineSegmentsGeometry().fromEdgesGeometry(edges), lineMat);
      lines.computeLineDistances();
      lines.renderOrder = 1;
      mesh.add(lines);
      edges.dispose();
      for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) bladeMaterials.add(material);
    }
  } else {
    const black = new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.DoubleSide, toneMapped: false });
    for (const mesh of meshes) mesh.material = black;
  }

  // ---- reveal sweep ---------------------------------------------------------
  // Material below the plane stays; contour lines above it stay.
  tilt.updateMatrixWorld(true);
  const upAxis = new THREE.Vector3(0, 1, 0).transformDirection(hero.root.matrixWorld).normalize();
  let low = Infinity, high = -Infinity;
  const world = new THREE.Vector3();
  for (let i = 0; i < points.length; i += 3) {
    world.set(points[i], points[i + 1], points[i + 2]).applyMatrix4(matrixFor(Y3));
    const h = world.dot(upAxis);
    low = Math.min(low, h);
    high = Math.max(high, h);
  }
  const keepBelow = new THREE.Plane();
  const keepAbove = new THREE.Plane();
  for (const material of bladeMaterials) {
    const own = (material as THREE.Material & { clippingPlanes?: THREE.Plane[] | null }).clippingPlanes ?? [];
    material.clippingPlanes = [...own, keepBelow];
    material.clipShadows = true;
  }
  lineMat.clippingPlanes = [keepAbove];
  shellMat.clippingPlanes = [keepAbove];

  function setSweep(amount: number) {
    const h = THREE.MathUtils.lerp(low - 0.02, high, amount);
    const at = upAxis.clone().multiplyScalar(h);
    keepBelow.setFromNormalAndCoplanarPoint(upAxis.clone().negate(), at);
    keepAbove.setFromNormalAndCoplanarPoint(upAxis, at);
  }

  // ---- right column and the thread -----------------------------------------
  const graph = document.querySelector<SVGSVGElement>('#graph')!;
  const thread = document.querySelector<SVGSVGElement>('#thread')!;
  const nodePath = thread.querySelector<SVGPathElement>('path')!;
  const nodeDot = thread.querySelector<SVGCircleElement>('circle')!;

  function drawGraph(t: number) {
    const appear = smoothstep(1.0, 1.4, t);
    if (mask) return;
    if (appear <= 0) {
      graph.innerHTML = '';
      renderGraph(graph, {
        focus: false, lit: [], litEdges: [], chip: {}, status: {}, timing: [],
        only: [], counter: '0 个节点 · 0 条关系',
      });
      return;
    }
    renderGraph(graph, {
      focus: false, lit: ['blade'], litEdges: [], chip: {}, status: {}, timing: [],
      only: ['blade'], sub: { blade: '×1' }, appear: { blade: appear },
      counter: '1 个节点 · 0 条关系',
    });
  }

  function drawThread(t: number) {
    if (mask) return;
    const m = matrixFor(Number(params.get('yaw') ?? Y3 + YAW_RATE * (t - 3)));
    const a = view.project(bladePoint(0, 0.55, 1).clone().applyMatrix4(m));
    const b = view.project(bladePoint(1, 0.55, 1).clone().applyMatrix4(m));
    const start = a.x >= b.x ? a : b;
    const dx0 = NODE.x - start.x, dy0 = NODE.y - start.y;
    const len = Math.hypot(dx0, dy0) || 1;
    const end = { x: NODE.x - (dx0 / len) * 9, y: NODE.y - (dy0 / len) * 9 };
    const dx = end.x - start.x;
    nodePath.setAttribute('d', `M${start.x} ${start.y} C${start.x + 0.45 * dx} ${start.y} ${end.x - 0.45 * dx} ${end.y} ${end.x} ${end.y}`);
    nodeDot.setAttribute('cx', String(start.x));
    nodeDot.setAttribute('cy', String(start.y));
    const total = nodePath.getTotalLength();
    const p = params.has('thread') ? Number(params.get('thread')) : clamp01((t - 1.8) / 1.4);
    nodePath.style.strokeDasharray = `${total}`;
    nodePath.style.strokeDashoffset = `${total * (1 - p)}`;
    nodePath.style.opacity = p > 0 ? '1' : '0';
    nodeDot.style.opacity = p > 0 ? '1' : '0';
  }

  function apply(t: number) {
    const yaw = params.has('yaw') ? Number(params.get('yaw')) : Y3 + YAW_RATE * (t - 3);
    spin.rotation.y = THREE.MathUtils.degToRad(yaw);
    tilt.updateMatrixWorld(true);
    const sweep = params.has('sweep') ? Number(params.get('sweep')) : smoothstep(0.6, 2.2, t);
    setSweep(sweep);
    const alpha = smoothstep(0, 1.2, t);
    lineMat.opacity = alpha;
    lineMat.visible = alpha > 0.001;
    drawGraph(t);
    drawThread(t);
    view.render();
  }

  if (mask) {
    document.querySelector<HTMLElement>('.col-graph')!.style.visibility = 'hidden';
    thread.style.display = 'none';
  } else {
    const column = document.querySelector<HTMLElement>('.col-model')!;
    column.insertAdjacentHTML('beforeend', '<div class="model-caption"><span>实物</span><span>第一级涡轮叶片</span></div>');
    thread.setAttribute('viewBox', '0 0 1920 1080');
    nodePath.setAttribute('fill', 'none');
    nodePath.setAttribute('stroke', 'var(--lit)');
    nodePath.setAttribute('stroke-width', '1.25');
    nodePath.setAttribute('opacity', '0.85');
    nodeDot.setAttribute('r', '2.5');
    nodeDot.setAttribute('fill', 'var(--lit)');
    nodeDot.setAttribute('opacity', '0.85');
  }

  const seek = (t: number) => apply(t);
  (window as unknown as { __seek: (t: number) => void }).__seek = seek;
  seek(Number(params.get('t') ?? 3));
}
