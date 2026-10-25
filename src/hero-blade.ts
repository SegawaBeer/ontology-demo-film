import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

/*
 * Close-up cooled turbine blade, generated at runtime (the GLB does not carry it).
 *
 * Ported from src/blade-study.ts of Turbine Explorer by AlexZhangji (MIT, see
 * THIRD_PARTY_NOTICES.md). The aerofoil, perforated walls, fir-tree root, platform,
 * tip rim, edge strips, internal cooling, airflow overlay, coating coupon and the
 * procedural textures follow that file. Changes: the blade is split into parts
 * that can be coloured, dimmed, faded and hidden one by one; every film-hole column
 * gets a thin liner inside its holes so the column can light up; the three views
 * became the continuous parameters cutaway, coatings and airflow; the final tilt
 * was removed so the caller owns the orientation.
 *
 * Generic explanatory geometry, not a specific manufacturer's blade.
 *
 * Units are the reference file's. The aerofoil runs from y = 0.52 (t = 0) to
 * y = 4.17 (t = 1); the platform top is at y = 0.555; u runs from the leading
 * edge (0) to the trailing edge (1). Face 1 is called the pressure side and
 * face -1 the suction side, as in the reference.
 */

export const HERO_COMPONENT = 'turbine.hero-blade';
export const HERO_SPAN = 3.65;
export const HERO_PLATFORM_TOP = 0.555;
export const HERO_TIP = 0.52 + HERO_SPAN;
const HOLE_U = [0.055, 0.12, 0.76, 0.93];
const HOLE_ROWS = 22;
const WINDOW = { u0: 0.145, u1: 0.915, t0: 0.045, t1: 0.965, chamfer: 0.035 };

const PART_NAMES: [string, string][] = [
  ['root', '叶根（枞树形）'], ['platform', '缘板'], ['tip', '叶尖围边'], ['edges', '前后缘加厚条'],
  ['wall-ps', '压力面完整叶壁'], ['wall-ps-cut', '压力面剖开叶壁与窗口边框'], ['wall-ss', '吸力面叶壁'],
  ['dividers', '冷却通道隔板'], ['ribs-1', '前缘通道斜肋'], ['ribs-2', '中间通道斜肋'], ['ribs-3', '后部通道斜肋'],
  ['pin-fins', '尾缘针肋'], ['airflow', '冷却气流示意'],
  ['coat-base', '涂层样片：镍基高温合金基体'], ['coat-bond', '涂层样片：MCrAlY 粘结层'],
  ['coat-tgo', '涂层样片：热生长氧化层'], ['coat-ysz', '涂层样片：YSZ 陶瓷热障层'],
  ...[1, 2, 3, 4].map(n => [`film-ps-${n}`, `压力面气膜孔第 ${n} 列`] as [string, string]),
  ...[1, 2, 3, 4].map(n => [`film-ss-${n}`, `吸力面气膜孔第 ${n} 列`] as [string, string]),
];
export const HERO_PART_IDS = PART_NAMES.map(([id]) => `${HERO_COMPONENT}.${id}`);
export const HERO_PART_NAME = new Map(PART_NAMES.map(([id, name]) => [`${HERO_COMPONENT}.${id}`, name]));

export function bladePoint(u: number, t: number, face = 1, inset = 0) {
  const chord = 1.65 * (1 - 0.18 * t);
  const x = (u - 0.46) * chord;
  const camber = 0.21 * Math.sin(Math.PI * u);
  const thickness = 0.19 * Math.pow(Math.sin(Math.PI * u), 0.62) + 0.025;
  const z = camber + face * Math.max(0.012, thickness - inset);
  const twist = 0.12 - 0.39 * t;
  return new THREE.Vector3(x * Math.cos(twist) + z * Math.sin(twist) + 0.22 * t * t,
    0.52 + t * HERO_SPAN, -x * Math.sin(twist) + z * Math.cos(twist));
}

/** Unit normal of one face, pointing out of the blade. */
export function outwardNormal(u: number, t: number, face: number) {
  const e = 0.002;
  const du = bladePoint(Math.min(1, u + e), t, face).sub(bladePoint(Math.max(0, u - e), t, face));
  const dt = bladePoint(u, Math.min(1, t + e), face).sub(bladePoint(u, Math.max(0, t - e), face));
  const n = du.cross(dt).normalize();
  const out = bladePoint(u, t, face).sub(bladePoint(u, t, -face));
  return n.dot(out) < 0 ? n.negate() : n;
}

type Textures = {
  bump: THREE.DataTexture; ceramicRoughness: THREE.DataTexture;
  brushed: THREE.DataTexture; sprite: THREE.DataTexture;
};
let shared: Textures | null = null;

/** The reference's procedural textures, built once and shared by every engine copy. */
function textures(): Textures {
  if (shared) return shared;
  const finish = (texture: THREE.DataTexture, repeat = true) => {
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    if (repeat) texture.repeat.set(1, 2.5);
    texture.magFilter = THREE.LinearFilter; texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.generateMipmaps = true; texture.needsUpdate = true;
    return texture;
  };
  // Fine ceramic relief, independent of albedo and roughness. No fake crystal facets.
  const grain = new Uint8Array(1024 * 1024 * 4); let seed = 9137;
  for (let i = 0; i < grain.length; i += 4) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const value = 105 + (seed >>> 25);
    grain[i] = grain[i + 1] = grain[i + 2] = value; grain[i + 3] = 255;
  }
  const bump = finish(new THREE.DataTexture(grain, 1024, 1024, THREE.RGBAFormat));
  // Independent roughness field: mesoscale deposition variation plus fine grain.
  const ceramicData = new Uint8Array(1024 * 1024 * 4); let finishSeed = 47219;
  for (let y = 0; y < 1024; y++) for (let x = 0; x < 1024; x++) {
    finishSeed = (Math.imul(finishSeed, 1664525) + 1013904223) >>> 0;
    const value = Math.round(225 + 9 * Math.sin(x * 0.043) * Math.sin(y * 0.057) + (finishSeed >>> 28) - 7);
    const i = (y * 1024 + x) * 4;
    ceramicData[i] = ceramicData[i + 1] = ceramicData[i + 2] = value; ceramicData[i + 3] = 255;
  }
  const ceramicRoughness = finish(new THREE.DataTexture(ceramicData, 1024, 1024));
  // Brushed alloy roughness.
  const brushedData = new Uint8Array(1024 * 1024 * 4);
  for (let y = 0; y < 1024; y++) for (let x = 0; x < 1024; x++) {
    const v = Math.round(180 + 17 * Math.sin(y * 2.7 + Math.sin(x * 0.011)) + 9 * Math.sin(y * 7.3 + x * 0.023));
    const i = (y * 1024 + x) * 4;
    brushedData[i] = brushedData[i + 1] = brushedData[i + 2] = v; brushedData[i + 3] = 255;
  }
  const brushed = finish(new THREE.DataTexture(brushedData, 1024, 1024), false);
  const spriteData = new Uint8Array(32 * 32 * 4);
  for (let y = 0; y < 32; y++) for (let x = 0; x < 32; x++) {
    const i = (y * 32 + x) * 4;
    const a = Math.max(0, 1 - Math.hypot((x - 15.5) / 15.5, (y - 15.5) / 15.5));
    spriteData[i] = spriteData[i + 1] = spriteData[i + 2] = 255; spriteData[i + 3] = Math.round(a * a * 255);
  }
  const sprite = new THREE.DataTexture(spriteData, 32, 32); sprite.needsUpdate = true;
  shared = { bump, ceramicRoughness, brushed, sprite };
  return shared;
}

/** True inside the chamfered cutaway window, in (u, t) parameter space. */
export function inWindow(u: number, t: number) {
  const { u0, u1, t0, t1, chamfer } = WINDOW;
  if (u <= u0 || u >= u1 || t <= t0 || t >= t1) return false;
  return (u - u0) + (t - t0) >= chamfer && (u1 - u) + (t - t0) >= chamfer
    && (u1 - u) + (t1 - t) >= chamfer && (u - u0) + (t1 - t) >= chamfer;
}

/** One wall loft with real apertures. Group 0 is the outer skin, group 1 the hole walls and inner skin. */
function perforatedFace(face: number, material: THREE.Material, cutWindow: boolean, innerMaterial: THREE.Material) {
  const outline = new THREE.Shape();
  outline.moveTo(0, 0); outline.lineTo(1, 0); outline.lineTo(1, 1); outline.lineTo(0, 1); outline.closePath();
  if (cutWindow) {
    const window = new THREE.Path();
    window.moveTo(0.145, 0.08); window.lineTo(0.18, 0.045); window.lineTo(0.88, 0.045); window.lineTo(0.915, 0.08);
    window.lineTo(0.915, 0.93); window.lineTo(0.88, 0.965); window.lineTo(0.18, 0.965); window.lineTo(0.145, 0.93);
    window.closePath();
    outline.holes.push(window);
  }
  for (const u of HOLE_U) {
    for (let i = 0; i < HOLE_ROWS; i++) {
      if (cutWindow && u > WINDOW.u0 && u < WINDOW.u1) continue;
      const hole = new THREE.Path();
      hole.absellipse(u, 0.065 + i * 0.041, 0.012, 0.0065, 0, Math.PI * 2, true);
      outline.holes.push(hole);
    }
  }
  // Extrusion creates real aperture walls; then both sheets are lofted into the airfoil.
  const flat = new THREE.ExtrudeGeometry(outline, { depth: 0.018, bevelEnabled: false, curveSegments: 5, steps: 1 });
  // Earcut alone bridges broad curved regions with long flat triangles. Refine in
  // parameter space before lofting, otherwise interior walls puncture the skin.
  const coords: number[] = [], normals: number[] = [];
  const flatPosition = flat.getAttribute('position'), flatNormal = flat.getAttribute('normal');
  function subdivide(vertices: THREE.Vector3[], ns: THREE.Vector3[], depth = 0) {
    const lengths = vertices.map((v, i) => v.distanceToSquared(vertices[(i + 1) % 3]));
    const longest = lengths.indexOf(Math.max(...lengths));
    if (lengths[longest] > 0.075 ** 2 && depth < 10) {
      const a = longest, b = (longest + 1) % 3, c = (longest + 2) % 3;
      const mid = vertices[a].clone().add(vertices[b]).multiplyScalar(0.5);
      const nm = ns[a].clone().add(ns[b]).normalize();
      subdivide([vertices[a], mid, vertices[c]], [ns[a], nm, ns[c]], depth + 1);
      subdivide([mid, vertices[b], vertices[c]], [nm, ns[b], ns[c]], depth + 1);
    } else vertices.forEach((v, i) => { coords.push(v.x, v.y, v.z); normals.push(ns[i].x, ns[i].y, ns[i].z); });
  }
  for (let i = 0; i < flatPosition.count; i += 3) {
    subdivide([0, 1, 2].map(j => new THREE.Vector3().fromBufferAttribute(flatPosition, i + j)),
      [0, 1, 2].map(j => new THREE.Vector3().fromBufferAttribute(flatNormal, i + j)));
  }
  flat.dispose();
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(coords, 3));
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  // uv keeps the (u, t) parameters: textures use it, and so does the cutaway scan.
  const uv: number[] = [];
  for (let i = 0; i < coords.length; i += 3) uv.push(coords[i], coords[i + 1]);
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  const position = geometry.getAttribute('position');
  const normal = geometry.getAttribute('normal');
  const jacobian = new THREE.Matrix3();
  for (let i = 0; i < position.count; i++) {
    const u = position.getX(i), t = position.getY(i), depth = position.getZ(i);
    const p = bladePoint(u, t, face, depth);
    const eps = 0.0001;
    const du = bladePoint(Math.min(1, u + eps), t, face, depth).sub(bladePoint(Math.max(0, u - eps), t, face, depth))
      .multiplyScalar(1 / (Math.min(1, u + eps) - Math.max(0, u - eps)));
    const dt = bladePoint(u, t + eps, face, depth).sub(bladePoint(u, t - eps, face, depth)).multiplyScalar(1 / (eps * 2));
    const dd = bladePoint(u, t, face, depth + eps).sub(bladePoint(u, t, face, depth - eps)).multiplyScalar(1 / (eps * 2));
    jacobian.set(du.x, dt.x, dd.x, du.y, dt.y, dd.y, du.z, dt.z, dd.z).invert().transpose();
    const n = new THREE.Vector3(normal.getX(i), normal.getY(i), normal.getZ(i)).applyMatrix3(jacobian).normalize();
    position.setXYZ(i, p.x, p.y, p.z);
    normal.setXYZ(i, n.x, n.y, n.z);
  }
  // The pressure-side loft reverses depth, so its Jacobian has negative
  // determinant. Reverse winding as well as transforming normals; otherwise
  // DoubleSide lighting flips the correctly transformed normals back inward.
  const outerIndices: number[] = [], innerIndices: number[] = [];
  for (let i = 0; i < position.count; i += 3) {
    const outer = [0, 1, 2].every(j => Math.abs(coords[(i + j) * 3 + 2]) < 0.00001);
    (outer ? outerIndices : innerIndices).push(i, i + (face === 1 ? 2 : 1), i + (face === 1 ? 1 : 2));
  }
  geometry.setIndex([...outerIndices, ...innerIndices]);
  geometry.addGroup(0, outerIndices.length, 0);
  geometry.addGroup(outerIndices.length, innerIndices.length, 1);
  geometry.computeBoundingSphere();
  return new THREE.Mesh(geometry, [material, innerMaterial]);
}

function stripGeometry(u0: number, u1: number, t0: number, t1: number) {
  const points: number[] = [], indices: number[] = [];
  for (let i = 0; i <= 32; i++) {
    const t = THREE.MathUtils.lerp(t0, t1, i / 32);
    for (const u of [u0, u1]) for (const side of [-1, 1]) {
      const p = bladePoint(u, t, side, 0.032); points.push(p.x, p.y, p.z);
    }
    if (i < 32) {
      const k = i * 4;
      for (const [a, b] of [[0, 1], [1, 3], [3, 2], [2, 0]]) indices.push(k + a, k + b, k + b + 4, k + a, k + b + 4, k + a + 4);
    }
  }
  indices.push(0, 2, 3, 0, 3, 1, 128, 129, 131, 128, 131, 130);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
  g.setIndex(indices);
  g.computeVertexNormals();
  return g;
}

function beamGeometry(a: THREE.Vector3, b: THREE.Vector3, radius: number) {
  const g = new THREE.CylinderGeometry(radius, radius, a.distanceTo(b), 8);
  const m = new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5),
    new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize()),
    new THREE.Vector3(1, 1, 1));
  return g.applyMatrix4(m);
}

/** Merge geometries into one non-indexed buffer with position and normal only. */
function merged(geometries: THREE.BufferGeometry[]) {
  const flat = geometries.map(g => {
    const out = g.index ? g.toNonIndexed() : g.clone();
    for (const name of Object.keys(out.attributes)) if (name !== 'position' && name !== 'normal') out.deleteAttribute(name);
    return out;
  });
  const result = mergeGeometries(flat)!;
  geometries.forEach(g => g.dispose()); flat.forEach(g => g.dispose());
  return result;
}

/**
 * Thin liners for one film-hole column, built in the wall's own (u, t, depth)
 * space so they sit exactly inside the apertures. Each liner is a sleeve that
 * starts just below the outer skin (never above it) close to the hole wall and
 * tapers towards the inner skin, so a coloured liner reads as a ring from the front.
 */
function linerGeometry(face: number, u: number, rows: number[]) {
  // The hole outline is a 10-gon, whose edges come no closer than 0.951 of the
  // radius, so a 0.93 ring never touches the wall.
  const ring = 12, levels = [0.0015, 0.009, 0.018], radii = [0.93, 0.8, 0.62];
  const positions: number[] = [], uvs: number[] = [], indices: number[] = [];
  for (const row of rows) {
    const tc = 0.065 + row * 0.041, base = positions.length / 3;
    levels.forEach((depth, level) => {
      for (let k = 0; k < ring; k++) {
        const angle = (k / ring) * Math.PI * 2;
        const pu = u + Math.cos(angle) * 0.012 * radii[level], pt = tc + Math.sin(angle) * 0.0065 * radii[level];
        const p = bladePoint(pu, pt, face, depth);
        positions.push(p.x, p.y, p.z); uvs.push(pu, pt);
      }
    });
    for (let level = 0; level < levels.length - 1; level++) {
      for (let k = 0; k < ring; k++) {
        const a = base + level * ring + k, b = base + level * ring + (k + 1) % ring;
        indices.push(a, b, b + ring, a, b + ring, a + ring);
      }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  g.setIndex(indices);
  g.computeVertexNormals();
  return g;
}

type Tinted = THREE.Material & { color: THREE.Color; emissive?: THREE.Color };

type Part = {
  id: string;
  objects: THREE.Object3D[];
  materials: Tinted[];
  base: { color: THREE.Color; opacity: number; transparent: boolean; depthWrite: boolean }[];
  glow: number;                       // emissive share of a highlight colour
  color: THREE.Color | null;          // caller state
  dim: number | null;
  opacity: number;
  visible: boolean;
  paramOpacity: number;               // continuous-parameter state
  paramVisible: boolean;
  host?: () => boolean;               // film liners follow the wall they sit in
};

export type HeroBladeRuntime = {
  root: THREE.Group;
  ids: string[];
  has: (id: string) => boolean;
  setColor: (id: string, color: THREE.Color | null) => void;
  setDim: (id: string, amount: number) => void;
  setOpacity: (id: string, opacity: number) => void;
  setVisible: (id: string, visible: boolean) => void;
  setCutaway: (value: number) => void;
  setCoatings: (value: number) => void;
  setAirflow: (value: number) => void;
  update: (delta: number, elapsed: number) => void;
  reset: () => void;
  snapshot: () => string;
  triangles: () => number;
  materialState: (id: string) => string;
  linerRise: () => number;
  dispose: () => void;
  readonly cutaway: number;
  readonly coatings: number;
  readonly airflow: number;
};

// Cutaway timing: the scan line climbs from root to tip over [0, SCAN_END]; at the
// end the window wall takes over from the fully scanned wall (same surface, no fade).
// Interior structure fades in over [0.3, 1].
const SCAN_END = 1;
// Coating coupon, reference sizes and rest positions.
const COAT_IDS = ['coat-base', 'coat-bond', 'coat-tgo', 'coat-ysz'];
const COAT_THICK = [0.07, 0.024, 0.012, 0.024];
const COAT_CENTER = { u: 0.45, t: 0.55 };
const COAT_BONDED_SCALE = 0.25;       // bonded stack is thinner: 0.0325 in total
const COAT_BONDED_FLOOR = -0.012;     // its bottom sits inside the 0.018 wall, top 0.02 above it
const COAT_FOOTPRINT = 0.5;           // bonded footprint is half the magnified coupon
const COAT_LIFT = [0.12, 0.22, 0.32, 0.42];
const COAT_DELAY = [0.3, 0.2, 0.1, 0];  // the ceramic top coat leaves first
const layerRest = (i: number) => new THREE.Vector3(1.12 + i * 0.46, 2.08 + i * 0.12, 0.22 + i * 0.23);

const SCAN_GLSL = `
uniform float heroScan;
varying vec2 vHeroUT;
bool heroInWindow(vec2 p) {
  if (p.x <= ${WINDOW.u0} || p.x >= ${WINDOW.u1} || p.y <= ${WINDOW.t0} || p.y >= ${WINDOW.t1}) return false;
  float c = ${WINDOW.chamfer};
  return (p.x - ${WINDOW.u0}) + (p.y - ${WINDOW.t0}) >= c && (${WINDOW.u1} - p.x) + (p.y - ${WINDOW.t0}) >= c
    && (${WINDOW.u1} - p.x) + (${WINDOW.t1} - p.y) >= c && (p.x - ${WINDOW.u0}) + (${WINDOW.t1} - p.y) >= c;
}
`;

type ScanMode = 'hole' | 'rim' | 'coupon';
type Uniform = { value: number };

/**
 * Scan-line cut. 'hole' discards the window area below the scan line (full
 * pressure wall and the liners in it); 'rim' shows the window frame only below
 * the scan line; 'coupon' cuts the bonded coating stack with the wall while it is
 * still part of it. vHeroUT is the (u, t) parameter of the fragment.
 */
function scanned<T extends THREE.Material>(material: T, mode: ScanMode, scan: Uniform, couponCut?: Uniform): T {
  material.onBeforeCompile = shader => {
    shader.uniforms.heroScan = scan;
    if (couponCut) shader.uniforms.heroCouponCut = couponCut;
    const ut = mode === 'rim' ? `vec2(0.5, (position.y - 0.52) / ${HERO_SPAN.toFixed(2)})` : mode === 'coupon' ? 'heroUT' : 'uv';
    shader.vertexShader = (mode === 'coupon' ? 'attribute vec2 heroUT;\n' : '') + 'varying vec2 vHeroUT;\n'
      + shader.vertexShader.replace('#include <begin_vertex>', `#include <begin_vertex>\n  vHeroUT = ${ut};`);
    const test = mode === 'rim' ? 'if (vHeroUT.y > heroScan) discard;'
      : mode === 'coupon' ? 'if (heroScan > 0.0 && vHeroUT.y < heroScan * heroCouponCut && heroInWindow(vHeroUT)) discard;'
      : 'if (heroScan > 0.0 && vHeroUT.y < heroScan && heroInWindow(vHeroUT)) discard;';
    shader.fragmentShader = SCAN_GLSL + (mode === 'coupon' ? 'uniform float heroCouponCut;\n' : '')
      + shader.fragmentShader.replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>\n  ${test}`);
  };
  material.customProgramCacheKey = () => `hero-scan-${mode}`;
  return material;
}

/** Shadow caster that is cut exactly like the visible surface. */
function scannedShadow(mesh: THREE.Mesh, mode: ScanMode, scan: Uniform, couponCut?: Uniform) {
  mesh.customDepthMaterial = scanned(new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking }), mode, scan, couponCut);
}


export function createHeroBlade(): HeroBladeRuntime {
  const tex = textures();
  const root = new THREE.Group();
  root.name = HERO_COMPONENT;
  const parts = new Map<string, Part>();
  const scan = { value: 0 };
  const paramVisible = new Map<THREE.Object3D, boolean>();

  // Deliberately separated exhibition finishes, not measured PBR values.
  const nickel = new THREE.MeshStandardMaterial({ color: 0x999b9c, metalness: 0.96, roughness: 0.38, side: THREE.DoubleSide, roughnessMap: tex.brushed });
  const interior = new THREE.MeshStandardMaterial({ color: 0x555a5b, metalness: 0.88, roughness: 0.44, side: THREE.DoubleSide });
  const ceramic = new THREE.MeshStandardMaterial({ color: 0xaeb0aa, metalness: 0, roughness: 0.64, side: THREE.DoubleSide,
    bumpMap: tex.bump, bumpScale: 0.006, roughnessMap: tex.ceramicRoughness });
  const bond = new THREE.MeshStandardMaterial({ color: 0x91938e, metalness: 0.88, roughness: 0.36, side: THREE.DoubleSide });
  const oxide = new THREE.MeshStandardMaterial({ color: 0x595e5c, metalness: 0, roughness: 0.82, side: THREE.DoubleSide });
  const rootMetal = nickel.clone(); rootMetal.color.setHex(0xa4a6a6); rootMetal.roughness = 0.32;
  // Every part gets its own material instances, so colouring one never tints another.
  const own = <T extends THREE.Material>(m: T) => m.clone() as T;

  function register(id: string, objects: THREE.Object3D[], materials: Tinted[], glow = 0.18) {
    const full = `${HERO_COMPONENT}.${id}`;
    objects.forEach(object => {
      if (!object.parent) root.add(object);
      object.traverse(o => { o.userData.heroPart = full; });
    });
    const part: Part = {
      id: full, objects, materials, glow,
      base: materials.map(m => ({ color: m.color.clone(), opacity: m.opacity, transparent: m.transparent, depthWrite: m.depthWrite })),
      color: null, dim: null, opacity: 1, visible: true, paramOpacity: 1, paramVisible: true,
    };
    parts.set(full, part);
    return part;
  }

  // Fir-tree root.
  const baseShape = new THREE.Shape();
  baseShape.moveTo(-0.37, -0.58);
  for (let i = 0; i < 4; i++) {
    const y = -0.58 + i * 0.18;
    baseShape.lineTo(-0.40 - i * 0.08, y + 0.035); baseShape.lineTo(-0.46 - i * 0.08, y + 0.12);
    baseShape.lineTo(-0.33 - i * 0.08, y + 0.17);
  }
  baseShape.lineTo(-0.45, 0.35); baseShape.lineTo(0.45, 0.35);
  for (let i = 3; i >= 0; i--) {
    const y = -0.58 + i * 0.18;
    baseShape.lineTo(0.33 + i * 0.08, y + 0.17); baseShape.lineTo(0.46 + i * 0.08, y + 0.12); baseShape.lineTo(0.40 + i * 0.08, y + 0.035);
  }
  baseShape.lineTo(0.37, -0.58); baseShape.closePath();
  const rootMat = own(rootMetal);
  const attachment = new THREE.Mesh(new THREE.ExtrudeGeometry(baseShape, {
    depth: 0.82, bevelEnabled: true, bevelSize: 0.032, bevelThickness: 0.032, bevelSegments: 4,
  }), rootMat);
  attachment.position.z = -0.41;
  register('root', [attachment], [rootMat]);

  // Platform.
  const platformShape = new THREE.Shape();
  platformShape.moveTo(-1, -0.43); platformShape.lineTo(0.82, -0.43); platformShape.lineTo(1.05, 0.12);
  platformShape.lineTo(0.9, 0.58); platformShape.lineTo(-0.86, 0.58); platformShape.lineTo(-1.05, 0.08); platformShape.closePath();
  const platformMat = own(nickel);
  const platform = new THREE.Mesh(new THREE.ExtrudeGeometry(platformShape, {
    depth: 0.13, bevelSize: 0.045, bevelThickness: 0.025, bevelSegments: 3,
  }), platformMat);
  platform.rotation.x = Math.PI / 2; platform.position.y = 0.53;
  register('platform', [platform], [platformMat]);

  // Pressure side: the full wall and the wall with the teaching window. The full
  // wall's window area is cut away below the scan line; the window frame shows
  // below the same line.
  const wallPsMats = [own(ceramic), own(interior)];
  wallPsMats.forEach(m => scanned(m, 'hole', scan));
  const wallPs = perforatedFace(1, wallPsMats[0], false, wallPsMats[1]);
  scannedShadow(wallPs, 'hole', scan);
  const wallPsPart = register('wall-ps', [wallPs], wallPsMats);

  const wallCutMats = [own(ceramic), own(interior)];
  const wallCut = perforatedFace(1, wallCutMats[0], true, wallCutMats[1]);
  const rimPath = [[0.145, 0.08], [0.18, 0.045], [0.88, 0.045], [0.915, 0.08], [0.915, 0.93], [0.88, 0.965], [0.18, 0.965], [0.145, 0.93], [0.145, 0.08]];
  const rimPoints: THREE.Vector3[] = [];
  for (let k = 0; k < rimPath.length - 1; k++) for (let j = 0; j < 24; j++) {
    const u = THREE.MathUtils.lerp(rimPath[k][0], rimPath[k + 1][0], j / 24), t = THREE.MathUtils.lerp(rimPath[k][1], rimPath[k + 1][1], j / 24);
    rimPoints.push(bladePoint(u, t, 1, 0.009));
  }
  const rimMat = own(nickel);
  scanned(rimMat, 'rim', scan);
  const rimMesh = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(rimPoints, true), 224, 0.014, 6, true), rimMat);
  scannedShadow(rimMesh, 'rim', scan);
  const wallCutPart = register('wall-ps-cut', [wallCut, rimMesh], [...wallCutMats, rimMat]);

  const wallSsMats = [own(ceramic), own(interior)];
  const wallSs = perforatedFace(-1, wallSsMats[0], false, wallSsMats[1]);
  const wallSsPart = register('wall-ss', [wallSs], wallSsMats);

  // Leading and trailing edges have full wall thickness, not open paper surfaces.
  const edgeMat = own(nickel);
  register('edges', [new THREE.Mesh(merged([stripGeometry(0, 0.018, 0, 1), stripGeometry(0.982, 1, 0, 1)]), edgeMat)], [edgeMat]);

  const tipMat = own(nickel);
  register('tip', [new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([
    ...Array.from({ length: 25 }, (_, i) => bladePoint(i / 24, 1, 1)),
    ...Array.from({ length: 25 }, (_, i) => bladePoint(1 - i / 24, 1, -1)),
  ], true), 100, 0.024, 6, true), tipMat)], [tipMat]);

  // Internal cooling: two dividers, oblique ribs on the inside of the suction wall
  // (turn clearances alternate), and a pin-fin bank. One merged mesh per part.
  const interiorParts: Part[] = [];
  const dividerMat = own(interior);
  interiorParts.push(register('dividers', [new THREE.Mesh(merged([stripGeometry(0.27, 0.30, 0, 0.91), stripGeometry(0.57, 0.60, 0.105, 1)]), dividerMat)], [dividerMat]));
  [[0.035, 0.25], [0.32, 0.55], [0.62, 0.78]].forEach(([start, end], index) => {
    const geometries: THREE.BufferGeometry[] = [];
    for (let i = 0; i < 20; i++) {
      const t = 0.09 + i * 0.042;
      geometries.push(beamGeometry(bladePoint(start, t, -1, 0.055), bladePoint(end, t + 0.022, -1, 0.055), 0.017));
    }
    const mat = own(interior);
    interiorParts.push(register(`ribs-${index + 1}`, [new THREE.Mesh(merged(geometries), mat)], [mat]));
  });
  const pinGeometries: THREE.BufferGeometry[] = [];
  for (let i = 0; i < 24; i++) for (const u of [0.83, 0.90]) {
    pinGeometries.push(beamGeometry(bladePoint(u, 0.065 + i * 0.037, -1, 0.035), bladePoint(u, 0.065 + i * 0.037, 1, 0.035), 0.021));
  }
  const pinMat = own(interior);
  interiorParts.push(register('pin-fins', [new THREE.Mesh(merged(pinGeometries), pinMat)], [pinMat]));

  // Film-hole liners, one part per column, numbered by u. Pressure-side liners sit
  // in the full wall's holes; the window wall shares the holes outside the window,
  // so columns 1, 2 and 4 stay in place when the wall is swapped. Column 3 lies in
  // the window and is cut with the full wall.
  const allRows = Array.from({ length: HOLE_ROWS }, (_, i) => i);
  HOLE_U.forEach((u, index) => {
    for (const face of [1, -1]) {
      const mat = own(interior);
      if (face === 1) scanned(mat, 'hole', scan);
      const liner = new THREE.Mesh(linerGeometry(face, u, allRows), mat);
      if (face === 1) scannedShadow(liner, 'hole', scan);
      // A lit column must read from across the frame, so liners glow at full strength.
      const part = register(`film-${face === 1 ? 'ps' : 'ss'}-${index + 1}`, [liner], [mat], 1.6);
      const insideWindow = u > WINDOW.u0 && u < WINDOW.u1;
      part.host = face === -1 ? () => effective(wallSsPart)
        : insideWindow ? () => effective(wallPsPart)
        : () => effective(wallPsPart) || effective(wallCutPart);
    }
  });

  // Cooling-air overlay: one serpentine path through the three passages, nine
  // film streams leaving the first pressure-side column, and moving particles.
  // Not tone-mapped: the overlay keeps the reference's cyan under the studio's low exposure.
  const airMaterial = new THREE.MeshBasicMaterial({ color: 0x7bbfca, transparent: true, opacity: 0.26, depthWrite: false, toneMapped: false });
  const curve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-0.20, -0.59, 0), bladePoint(0.16, 0, 0), bladePoint(0.16, 0.78, 0),
    bladePoint(0.23, 0.95, 0), bladePoint(0.43, 0.95, 0), bladePoint(0.43, 0.65, 0),
    bladePoint(0.43, 0.14, 0), bladePoint(0.53, 0.055, 0), bladePoint(0.69, 0.11, 0), bladePoint(0.69, 0.91, 0),
  ], false, 'centripetal');
  const filmCurves: THREE.CatmullRomCurve3[] = [];
  const tubes = [new THREE.TubeGeometry(curve, 160, 0.019, 8, false)];
  for (let i = 0; i < 9; i++) {
    const t = 0.065 + (2 + i * 2) * 0.041;
    const start = bladePoint(0.055, t, 1);
    const film = new THREE.CatmullRomCurve3([start, start.clone().add(new THREE.Vector3(0.08, 0.01, 0.12)),
      start.clone().add(new THREE.Vector3(0.35, 0.045, 0.17)), start.clone().add(new THREE.Vector3(0.66, 0.08, 0.20))]);
    filmCurves.push(film);
    tubes.push(new THREE.TubeGeometry(film, 24, 0.006, 5, false));
  }
  const airTubes = new THREE.Mesh(merged(tubes), airMaterial);
  const particlePositions = new Float32Array((18 * 8 + filmCurves.length * 8) * 3);
  const particleColors = new Float32Array(particlePositions.length);
  for (let i = 0; i < particlePositions.length / 3; i++) {
    const brightness = 0.25 + 0.75 * (1 - (i % 8) / 8);
    particleColors.set([brightness * 0.40, brightness, brightness], i * 3);
  }
  const particleGeometry = new THREE.BufferGeometry();
  particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
  particleGeometry.setAttribute('color', new THREE.BufferAttribute(particleColors, 3));
  const particleMaterial = new THREE.PointsMaterial({ size: 0.092, map: tex.sprite, transparent: true, opacity: 0.9,
    vertexColors: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false });
  const particles = new THREE.Points(particleGeometry, particleMaterial);
  particles.frustumCulled = false;
  const airflowPart = register('airflow', [airTubes, particles], [airMaterial, particleMaterial], 0);
  airflowPart.paramOpacity = 0;
  function moveParticles(elapsed: number) {
    const point = new THREE.Vector3();
    for (let i = 0; i < 18 * 8; i++) {
      curve.getPointAt((elapsed * 0.10 + Math.floor(i / 8) / 18 - (i % 8) * 0.0018 + 1) % 1, point);
      particlePositions.set([point.x, point.y, point.z], i * 3);
    }
    filmCurves.forEach((film, j) => {
      for (let k = 0; k < 8; k++) {
        film.getPointAt((elapsed * 0.48 + j * 0.113 - k * 0.012 + 1) % 1, point);
        particlePositions.set([point.x, point.y, point.z], (18 * 8 + j * 8 + k) * 3);
      }
    });
    particleGeometry.getAttribute('position').needsUpdate = true;
  }
  moveParticles(0);

  // Coating coupon. Each layer is the reference's curved plate; a morph target
  // wraps it onto the blade surface around (u 0.45, t 0.55) so the bonded stack
  // reads as a piece of the wall. Representative superalloy / MCrAlY / alumina /
  // YSZ system; layer thickness and separation are exaggerated.
  const coatMats = [own(nickel), own(bond), own(oxide), own(ceramic)];
  const coatCenter = bladePoint(COAT_CENTER.u, COAT_CENTER.t, 1);
  const coatNormal = outwardNormal(COAT_CENTER.u, COAT_CENTER.t, 1);
  // Local frame of the bonded stack: x along the chord, z out of the wall.
  const chordDir = bladePoint(COAT_CENTER.u + 0.01, COAT_CENTER.t, 1).sub(bladePoint(COAT_CENTER.u - 0.01, COAT_CENTER.t, 1));
  const coatX = chordDir.addScaledVector(coatNormal, -chordDir.dot(coatNormal)).normalize();
  const coatY = new THREE.Vector3().crossVectors(coatNormal, coatX);
  const spanDir = bladePoint(COAT_CENTER.u, COAT_CENTER.t + 0.01, 1).sub(bladePoint(COAT_CENTER.u, COAT_CENTER.t - 0.01, 1));
  const spanSign = Math.sign(coatY.dot(spanDir)) || 1;
  const coatQuat = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(coatX, coatY, coatNormal));
  const coatInverse = coatQuat.clone().invert();
  const chordAt = 1.65 * (1 - 0.18 * COAT_CENTER.t);
  const coatLayers: { mesh: THREE.Mesh; bonded: THREE.Vector3; rest: THREE.Vector3 }[] = [];
  const couponCut = COAT_IDS.map(() => ({ value: 1 }));
  let floor = COAT_BONDED_FLOOR;
  COAT_IDS.forEach((id, i) => {
    const g = new THREE.BoxGeometry(0.70, 0.96, COAT_THICK[i], 20, 16, 1);
    const p = g.getAttribute('position');
    const flatZ = Array.from({ length: p.count }, (_, k) => p.getZ(k));
    for (let k = 0; k < p.count; k++) p.setZ(k, p.getZ(k) + 0.22 * (1 - (p.getX(k) / 0.45) ** 2) + p.getY(k) * 0.10);
    g.computeVertexNormals();
    // Bonded shape: the same box wrapped onto the wall, as a morph target in the
    // layer's local frame at its bonded pose. heroUT records the wall parameter
    // under each vertex so the bonded stack is cut together with the wall.
    const thick = COAT_THICK[i] * COAT_BONDED_SCALE;
    const mid = floor + thick / 2;
    const bonded = coatCenter.clone().addScaledVector(coatNormal, mid);
    const target = new Float32Array(p.count * 3), ut = new Float32Array(p.count * 2);
    const local = new THREE.Vector3();
    for (let k = 0; k < p.count; k++) {
      const u = COAT_CENTER.u + COAT_FOOTPRINT * p.getX(k) / chordAt;
      const t = COAT_CENTER.t + spanSign * COAT_FOOTPRINT * p.getY(k) / HERO_SPAN;
      const depth = flatZ[k] / COAT_THICK[i] * thick;
      local.copy(bladePoint(u, t, 1)).addScaledVector(outwardNormal(u, t, 1), mid + depth).sub(bonded).applyQuaternion(coatInverse);
      target.set([local.x, local.y, local.z], k * 3);
      ut.set([u, t], k * 2);
    }
    const morph = new THREE.BufferGeometry();
    morph.setAttribute('position', new THREE.BufferAttribute(target, 3));
    morph.setIndex(g.getIndex());
    morph.computeVertexNormals();
    g.morphAttributes.position = [morph.getAttribute('position')];
    g.morphAttributes.normal = [morph.getAttribute('normal')];
    g.setAttribute('heroUT', new THREE.BufferAttribute(ut, 2));
    scanned(coatMats[i], 'coupon', scan, couponCut[i]);
    const mesh = new THREE.Mesh(g, coatMats[i]);
    mesh.morphTargetInfluences = [1];
    mesh.frustumCulled = false;
    scannedShadow(mesh, 'coupon', scan, couponCut[i]);
    register(id, [mesh], [coatMats[i]], 0.2);
    coatLayers.push({ mesh, bonded, rest: layerRest(i) });
    floor += thick;
  });

  // ---- State. Caller state (colour, dim, opacity, visibility) and parameter state
  // (cutaway, coatings, airflow) are kept apart and combined in apply().
  function effective(part: Part) { return part.objects[0].visible; }
  const linerParts = [...parts.values()].filter(part => part.host);
  const otherParts = [...parts.values()].filter(part => !part.host);
  const black = new THREE.Color(0);

  function apply(part: Part) {
    const shown = part.visible && part.paramVisible && (!part.host || part.host());
    for (const object of part.objects) object.visible = shown && (paramVisible.get(object) ?? true);
    const fade = part.opacity * part.paramOpacity;
    part.materials.forEach((material, i) => {
      const base = part.base[i];
      const transparent = base.transparent || fade < 0.999;
      if (material.transparent !== transparent) { material.transparent = transparent; material.needsUpdate = true; }
      material.opacity = base.opacity * fade;
      material.depthWrite = base.depthWrite && fade >= 0.999;
      if (part.color) material.color.copy(part.color);
      else if (part.dim !== null) material.color.copy(base.color).multiplyScalar(part.dim);
      else material.color.copy(base.color);
      if (material.emissive) {
        if (part.color) material.emissive.copy(part.color).multiplyScalar(part.glow);
        else material.emissive.copy(black);
      }
    });
  }
  function applyAll() {
    otherParts.forEach(apply);
    linerParts.forEach(apply);
  }

  // ---- Continuous parameters.
  let cutValue = 0, coatValue = 0, flowValue = 0;
  const interiorIds = new Set(interiorParts.map(part => part.id));
  function setCutaway(value: number) {
    const t = THREE.MathUtils.clamp(Number.isFinite(value) ? value : 0, 0, 1);
    cutValue = t;
    scan.value = THREE.MathUtils.clamp(t / SCAN_END, 0, 1) * 1.02;
    paramVisible.set(wallPs, t < SCAN_END - 1e-6);
    paramVisible.set(wallCut, t >= SCAN_END - 1e-6);
    paramVisible.set(rimMesh, t > 0);
    const reveal = THREE.MathUtils.clamp((t - 0.3) / 0.7, 0, 1);
    for (const part of parts.values()) {
      if (!interiorIds.has(part.id)) continue;
      part.paramOpacity = reveal;
      part.paramVisible = reveal > 0;
    }
    applyAll();
  }

  const identity = new THREE.Quaternion();
  function setCoatings(value: number) {
    const t = THREE.MathUtils.clamp(Number.isFinite(value) ? value : 0, 0, 1);
    coatValue = t;
    coatLayers.forEach((layer, i) => {
      const s = THREE.MathUtils.smoothstep(THREE.MathUtils.clamp((t - COAT_DELAY[i]) / 0.7, 0, 1), 0, 1);
      // While bonded the layer is part of the wall and is cut with it; as it
      // lifts off, the cut line drops back so the layer is whole again.
      couponCut[i].value = 1 - THREE.MathUtils.smoothstep(s, 0, 0.12);
      progress[i] = s;
      placeLayer(i);
    });
  }

  // Layer poses follow setCoatings directly, so a timeline can step them frame by
  // frame. (The reference's damped slide-out of a selected layer is not kept:
  // colouring a layer must not move it.)
  const progress = COAT_IDS.map(() => 0);
  function placeLayer(i: number) {
    const layer = coatLayers[i], s = progress[i];
    const lift = layer.bonded.clone().addScaledVector(coatNormal, COAT_LIFT[i]);
    // Quadratic path: leaves the surface along its normal, ends at the reference rest position.
    layer.mesh.position.copy(layer.bonded).multiplyScalar((1 - s) * (1 - s))
      .addScaledVector(lift, 2 * (1 - s) * s).addScaledVector(layer.rest, s * s);
    layer.mesh.quaternion.slerpQuaternions(coatQuat, identity, s);
    layer.mesh.morphTargetInfluences![0] = 1 - s;
  }

  function setAirflow(value: number) {
    const t = THREE.MathUtils.clamp(Number.isFinite(value) ? value : 0, 0, 1);
    flowValue = t;
    airflowPart.paramOpacity = t;
    airflowPart.paramVisible = t > 0;
    apply(airflowPart);
  }

  function update(_delta: number, elapsed: number) {
    if (!particles.visible) return;
    moveParticles(elapsed);
  }

  // ---- Caller API, per part id.
  const get = (id: string) => parts.get(id);
  function setColor(id: string, color: THREE.Color | null) {
    const part = get(id); if (!part) return;
    part.color = color ? color.clone() : null; part.dim = null; apply(part);
  }
  function setDim(id: string, amount: number) {
    const part = get(id); if (!part) return;
    part.color = null; part.dim = amount; apply(part);
  }
  function setOpacity(id: string, opacity: number) {
    const part = get(id); if (!part) return;
    part.opacity = THREE.MathUtils.clamp(opacity, 0, 1); apply(part);
  }
  function setVisible(id: string, visible: boolean) {
    const part = get(id); if (!part) return;
    part.visible = visible; applyAll();
  }
  function reset() {
    for (const part of parts.values()) { part.color = null; part.dim = null; part.opacity = 1; part.visible = true; }
    setCoatings(0); setAirflow(0); setCutaway(0);
  }

  /** Every state the parameters and the caller API can touch, for the self-check. */
  function snapshot() {
    const out: unknown[] = [scan.value.toFixed(5)];
    for (const part of parts.values()) {
      out.push(part.id, part.objects.map(o => o.visible),
        part.materials.map(m => [m.color.getHexString(), m.emissive?.getHexString() ?? '', m.opacity.toFixed(4), m.transparent, m.depthWrite]));
    }
    for (const layer of coatLayers) {
      out.push(layer.mesh.position.toArray().map(v => v.toFixed(5)), layer.mesh.quaternion.toArray().map(v => v.toFixed(5)),
        layer.mesh.morphTargetInfluences![0].toFixed(5));
    }
    out.push(couponCut.map(c => c.value.toFixed(5)));
    return JSON.stringify(out);
  }

  /** Colour state of one part's materials, for the isolation check. */
  function materialState(id: string) {
    const part = get(id);
    return part ? part.materials.map(m => m.color.getHexString() + (m.emissive?.getHexString() ?? '')).join() : '';
  }

  /** Largest distance a liner vertex rises above the outer skin (<= 0 means flush or below). */
  function linerRise() {
    let worst = -Infinity;
    for (const part of linerParts) {
      const face = part.id.includes('film-ps') ? 1 : -1;
      const g = (part.objects[0] as THREE.Mesh).geometry;
      const p = g.getAttribute('position'), uv = g.getAttribute('uv');
      const v = new THREE.Vector3();
      for (let i = 0; i < p.count; i++) {
        const u = uv.getX(i), t = uv.getY(i);
        v.fromBufferAttribute(p, i).sub(bladePoint(u, t, face));
        worst = Math.max(worst, v.dot(outwardNormal(u, t, face)));
      }
    }
    return worst;
  }

  function triangles() {
    let total = 0;
    root.traverse(object => {
      const mesh = object as THREE.Mesh;
      if (!mesh.isMesh) return;
      const g = mesh.geometry;
      total += (g.index ? g.index.count : g.getAttribute('position').count) / 3;
    });
    return total;
  }

  // Points are sized in world units, so follow the scale the caller gives the blade.
  particles.onBeforeRender = () => { particleMaterial.size = 0.092 * particles.matrixWorld.getMaxScaleOnAxis(); };
  root.traverse(object => {
    if ((object as THREE.Mesh).isMesh) { object.castShadow = true; object.receiveShadow = true; }
  });
  airTubes.castShadow = false; airTubes.receiveShadow = false;
  reset();

  return {
    root, ids: [...parts.keys()], has: id => parts.has(id),
    setColor, setDim, setOpacity, setVisible, setCutaway, setCoatings, setAirflow, update, reset, snapshot, triangles,
    materialState, linerRise,
    get cutaway() { return cutValue; }, get coatings() { return coatValue; }, get airflow() { return flowValue; },
    dispose() {
      root.traverse(object => {
        const mesh = object as THREE.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
      });
      for (const part of parts.values()) part.materials.forEach(m => m.dispose());
    },
  } as HeroBladeRuntime;
}

/**
 * Hero-to-ring transform: maps the hero blade's own units into the local frame
 * of a generated first-stage ring blade (tools/blade.py: +Y radial, +X axial,
 * +Z tangential, aerofoil 0.020..0.146, stagger 35° at the root to 21° at the
 * tip). The aerofoil above the platform is scaled to the ring's 0.126 height, the
 * platform top lands on the ring's platform top (0.4 mm higher, so the two
 * platforms do not flicker where they overlap), the mid-span chord is centred on
 * the ring's stacking axis and turned to the ring's mid-span stagger of 28°.
 */
export function heroToRing() {
  const RING_PLATFORM = 0.020, RING_TIP = 0.146, RING_MID_STAGGER = THREE.MathUtils.degToRad(28);
  const scale = (RING_TIP - RING_PLATFORM) / (HERO_TIP - HERO_PLATFORM_TOP);
  const le = bladePoint(0, 0.5, 0), te = bladePoint(1, 0.5, 0);
  const mid = le.clone().add(te).multiplyScalar(0.5);
  const angle = Math.atan2(te.z - le.z, te.x - le.x);
  // A turn of theta about +Y moves the angle atan2(z, x) to angle - theta.
  const rotation = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), angle - RING_MID_STAGGER);
  const offset = new THREE.Vector3(mid.x, HERO_PLATFORM_TOP, mid.z).multiplyScalar(scale).applyQuaternion(rotation);
  const position = new THREE.Vector3(-offset.x, RING_PLATFORM + 0.0004 - offset.y, -offset.z);
  return { matrix: new THREE.Matrix4().compose(position, rotation, new THREE.Vector3(scale, scale, scale)), scale };
}
