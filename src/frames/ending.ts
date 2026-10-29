// frame=ending: the main timeline's ending, global t 103–120 (主时间轴二 第三节, 9.5).
// It is built on the opening's own engine and rig (clip-open in hosted mode), so the fan,
// the airflow, the outlines and the 0–7.6 s hand-over between the detailed blade and ring
// blade 001 are the opening's own, run backwards. frame=film hands over at 103.0, where both
// pages show the net-end picture (with question three's disposal node in the graph).
//   103–112  A: net framing; spin up and down, ring flash, parts go farthest from 001 first
//   112–115  B: camera back to the ring view; 001 tints, cross-fades to the detailed blade, leaves
//   115–120  C: the opening's own t < 5 picture: thread redrawn, closing line, 8°/s spin
import * as THREE from 'three';
import { mountOpening } from './clip-open';
import { renderGraph } from './graph';
import { endingGraphAt } from './ending-graph';
import { filmEvents } from './film-events';
import { blendPose } from './clip-q12';
import type { Theme, Pose } from './scene';
import { clamp, seg, ease } from './timing';

export const START = 103, DURATION = 120;
const SPIN = [103.0, 105.0, 105.8, 111.0] as const;
const RING_FLASH = [105.0, 105.5] as const, FLASH_AMP = 0.25;
const PARTS = [105.6, 110.6] as const;            // start of the first and the last part to go
const BLADE_LINE = 0.2;                            // a ring blade shows its outline this long
const B = 112.0, TINT = [112.0, 113.0] as const, CROSS = [113.0, 113.3] as const, CAM_B = [112.0, 113.3] as const;
const LEAVE = [113.3, 115.0] as const, C = 115.0;
const CAPTION = [112.0, 112.3] as const, THREAD = [115.0, 116.4] as const, SUBTITLE = [116.4, 117.4] as const;
const SPIN_JOIN = 117.4;                          // from here the opening's own 8°/s, Y3 + 8 × (t − 119)
const OMEGA = 360 / 4.4;
const S = (u: number) => u * u * u * (u * (u * 6 - 15) + 10);
const I = (u: number) => u ** 6 - 3 * u ** 5 + 2.5 * u ** 4;   // ∫S
/** Rotor speed as a share of cruise (9.5). */
export function speedAt(t: number) {
  if (t <= SPIN[0] || t >= SPIN[3]) return 0;
  if (t < SPIN[1]) return S((t - SPIN[0]) / 2);
  if (t < SPIN[2]) return 1;
  return 1 - S((t - SPIN[2]) / 5.2);
}
/** ω × (1.0 + 0.8 + 2.6) = 360° at 111.0, so blade 001 is back in its assembled place. */
export function rotorDegrees(t: number) {
  if (t <= SPIN[0]) return 0;
  if (t >= SPIN[3]) return 360;
  if (t < SPIN[1]) return OMEGA * 2 * I((t - SPIN[0]) / 2);
  if (t < SPIN[2]) return OMEGA * (1 + (t - SPIN[1]));
  const u = (t - SPIN[2]) / 5.2;
  return OMEGA * (1.8 + 5.2 * (u - I(u)));
}

export async function mountEnding(theme: Theme) {
  const o = (await mountOpening(theme, true))!;
  const { view, camera, engine, components, pieces, bladeId } = o;
  const RING = 'turbine.stage-1-blades', DISC = 'turbine.stage-1-disk', FAN = 'fan.blades';
  const graphEl = document.querySelector<SVGSVGElement>('#graph')!;
  const frameEl = document.querySelector<HTMLElement>('#frame')!;
  const subtitle = document.createElement('div');
  subtitle.className = 'film-subtitle';
  subtitle.textContent = '同一套对象，整个工厂一起用。';
  frameEl.append(subtitle);

  // Outlines that sit in the scene follow the rotor from here on (the opening only shows them standing still).
  const groupOf = (id: string) => components.find(c => c.meta.id === id)!.group;
  for (const l of o.ringOutlines) groupOf(RING).add(l);
  for (const l of o.fanOutlines) groupOf(FAN).add(l);
  const ghostSet = new Set(o.ghostMats as THREE.Material[]);

  // Fade order: every item by its distance from blade 001, farthest first.
  const c1 = new THREE.Vector3(...engine.getPart(bladeId(1))!.center);
  const centre = (ids: string[]) => { const v = new THREE.Vector3(); for (const id of ids) v.add(new THREE.Vector3(...engine.getPart(id)!.center)); return v.multiplyScalar(1 / ids.length); };
  type Item = { kind: 'piece' | 'fan' | 'disc' | 'blade'; d: number; n?: number; piece?: typeof pieces[number]; start: number; dur: number };
  const items: Item[] = [
    ...pieces.map(p => ({ kind: 'piece' as const, d: p.box.getCenter(new THREE.Vector3()).distanceTo(c1), piece: p, start: 0, dur: Math.min(0.8, p.sweepTo) })),
    { kind: 'fan', d: centre(engine.listParts(FAN)).distanceTo(c1), start: 0, dur: 0.6 },
    { kind: 'disc', d: centre(engine.listParts(DISC)).distanceTo(c1), start: 0, dur: 0.6 },
    ...Array.from({ length: 99 }, (_, i) => ({ kind: 'blade' as const, n: i + 2, d: centre([bladeId(i + 2)]).distanceTo(c1), start: 0, dur: BLADE_LINE })),
  ];
  items.sort((a, b) => b.d - a.d);
  items.forEach((it, i) => { it.start = PARTS[0] + (PARTS[1] - PARTS[0]) * i / (items.length - 1); });
  const fanEnd = o.fanStart(o.fanTotal) + o.fanOutline + 0.01;
  /** Each item's own assembly timeline run backwards: r = 0 fully there, 1 gone. */
  function fadeItems(t: number) {
    let blades = 1;
    for (const it of items) {
      const r = seg(t, it.start, it.start + it.dur);
      if (it.kind === 'piece') {
        const p = it.piece!;
        if (r <= 0) continue;   // untouched: keeps the opening's t = 30 state (cut plane included)
        o.pieceAt(p, r >= 1 ? p.start - 0.01 : p.start + (p.sweepTo + 0.01) * (1 - r));
        // The net shell keeps its half-section cut while it sweeps away.
        if (r > 0 && r < 1 && p.mats.some(m => ghostSet.has(m))) {
          for (const m of p.mats) m.clippingPlanes = [o.cutPlane, p.plane];
          for (const l of p.lines) (l.material as THREE.Material).clippingPlanes = [p.linePlane, o.cutPlane];
        }
      } else if (it.kind === 'fan') {
        if (r > 0) o.fanAt(r >= 1 ? 0 : o.fanStart(1) + (fanEnd - o.fanStart(1)) * (1 - r));
      } else if (it.kind === 'disc') {
        if (r > 0) o.discAt(r >= 1 ? 4.9 : 5.0 + 1.9 * (1 - r));
      } else {
        const gone = t >= it.start;
        if (!gone) blades++;
        if (gone) engine.setVisible(bladeId(it.n!), false);
        const line = o.ringOutlines[it.n! - 1];
        if (line) line.visible = gone && r < 1;
      }
    }
    return blades;
  }

  // The hero blade's own look, read before anything has touched it (frame=open's state).
  const heroOwn = o.heroColors.map(e => ({ e, opacity: e.material.opacity, transparent: e.material.transparent }));
  const nickel = o.heroColors.find(e => e.base.getHex() === new THREE.Color(0x999b9c).getHex()) ?? o.heroColors[0];
  function heroLook(opacity: number) {
    for (const { e, opacity: o0, transparent: t0 } of heroOwn) {
      const m = e.material;
      m.color.copy(e.base); m.metalness = e.metalness; m.roughness = e.roughness; m.envMapIntensity = e.env;
      const transparent = opacity < 0.999 ? true : t0;
      m.opacity = opacity < 0.999 ? o0 * opacity : o0;
      if (m.transparent !== transparent) { m.transparent = transparent; m.needsUpdate = true; }
    }
  }
  // 115–117.4: from the opening's 5.0 yaw (turning back at the reversed rate) into its
  // own 8°/s, Y3 + 8 × (t − 119), by a cubic with matching end speeds.
  const LEAVE_RATE = 2.3 / (LEAVE[1] - LEAVE[0]);
  const yaw5 = o.Y3 + 16;
  const yawAt = (t: number) => {
    if (t >= SPIN_JOIN) return o.Y3 + 8 * (t - 119);
    const d = SPIN_JOIN - C, u = clamp((t - C) / d);
    const p0 = yaw5, p1 = o.Y3 + 8 * (SPIN_JOIN - 119), v0 = -8 * LEAVE_RATE * d, v1 = 8 * d;
    const h00 = 2 * u ** 3 - 3 * u ** 2 + 1, h10 = u ** 3 - 2 * u ** 2 + u, h01 = -2 * u ** 3 + 3 * u ** 2, h11 = u ** 3 - u ** 2;
    return h00 * p0 + h10 * v0 + h01 * p1 + h11 * v1;
  };
  // The opening's two passes, but the see-through shells and the airflow are drawn once.
  const passTwo = () => [...pieces.flatMap(p => [...p.lines, ...p.shells]), ...o.ringOutlines, ...o.discLines, ...o.fanOutlines,
    ...(o.ringShell ? [o.ringShell] : []), ...(o.fanShell ? [o.fanShell] : [])] as THREE.Object3D[];
  const ghostMeshes = pieces.flatMap(p => p.meshes.filter(m => ghostSet.has(m.material as THREE.Material)));
  function draw() {
    const extras = passTwo().filter(x => x.visible);
    for (const x of extras) x.visible = false;
    view.render();
    if (!extras.length) return;
    for (const x of extras) x.visible = true;
    const off = [...ghostMeshes.filter(m => m.visible), ...(o.flow.group.visible ? [o.flow.group] : [])];
    for (const x of off) x.visible = false;
    view.renderSecond();
    for (const x of off) x.visible = true;
  }
  // Camera poses: the net framing (opening t = 30) and the ring view (opening t = 7.3).
  const NET: Pose = { position: o.m3FitPos.clone(), target: o.m3FitTarget.clone() };
  o.apply(7.3, false);
  const RINGV: Pose = { position: camera.position.clone(), target: o.ringView.target.clone() };
  const ringNear = camera.near, ringFar = camera.far;
  let lastT = START, bladesNow = 100, lastPose: Pose = NET;

  function seek(input: number) {
    const t = clamp(input, START, DURATION);
    lastT = t;
    o.resetCaches();
    if (t >= C) {
      fadeItems(DURATION);
      heroLook(1);
      o.apply(4.0, true, { yaw: yawAt(t), thread: clamp((t - THREAD[0]) / (THREAD[1] - THREAD[0])) });
      subtitle.style.opacity = ease(seg(t, SUBTITLE[0], SUBTITLE[1])).toFixed(3);
      bladesNow = 1;
      lastPose = { position: camera.position.clone(), target: o.open.openTarget.clone() };
      return;
    }
    subtitle.style.opacity = '0';
    if (t >= LEAVE[0]) leave(t);
    else {
      o.apply(30.0, false);
      const deg = rotorDegrees(t);
      for (const g of o.rotorGroups) g.rotation.x = -THREE.MathUtils.degToRad(deg % 360);
      o.flow.set(speedAt(t), 360 + deg, false);
      lastPose = NET;
    }
    bladesNow = fadeItems(t);
    const f = seg(t, RING_FLASH[0], RING_FLASH[1]);
    if (f > 0 && f < 1) {
      const a = Math.sin(Math.PI * f) * FLASH_AMP, c = new THREE.Color();
      for (let n = 1; n <= 100; n++) engine.setColor(bladeId(n), c.copy(engine.parts.get(bladeId(n))!.baseColor).convertLinearToSRGB().lerp(o.LIT_SRGB, a).convertSRGBToLinear());
    }
    if (t >= B && t < LEAVE[0]) swap(t);
    if (t >= B) caption(t);
    renderGraph(graphEl, endingGraphAt(t, bladesNow));
    // After a jump some material state only lands on the next draw (as in film-a), so draw twice.
    draw();
    draw();
  }

  /** 112–113.3: camera to the ring view; blade 001 takes the detailed blade's metal, then they cross-fade. */
  function swap(t: number) {
    const k = ease(seg(t, CAM_B[0], CAM_B[1]));
    lastPose = blendPose(NET, RINGV, k);
    view.applyPose(lastPose);
    camera.near = THREE.MathUtils.lerp(0.05, ringNear, k);
    camera.far = THREE.MathUtils.lerp(80, ringFar, k);
    camera.updateProjectionMatrix();
    o.lightsAt(t, [1, 1 - k]);
    const cross = ease(seg(t, CROSS[0], CROSS[1]));
    o.open.hero.root.visible = cross > 0;
    heroLook(cross);
    const one = bladeId(1);
    if (cross >= 1) { engine.setVisible(one, false); return; }
    engine.setOpacity([one], 1 - cross);
    const m = engine.parts.get(one)!.promoted!.material as THREE.MeshStandardMaterial;
    const tint = ease(seg(t, TINT[0], TINT[1]));
    m.color.lerp(nickel.base, tint);
    m.metalness = THREE.MathUtils.lerp(o.ringPbr.metalness, nickel.metalness, tint);
    m.roughness = THREE.MathUtils.lerp(o.ringPbr.roughness, nickel.roughness, tint);
    m.envMapIntensity = THREE.MathUtils.lerp(o.ringPbr.env, nickel.env, tint);
  }
  /** 113.3–115: the opening's 7.3 → 5.0 backwards: the blade leaves the ring and the camera goes back. */
  function leave(t: number) {
    o.apply(7.3 - 2.3 * seg(t, LEAVE[0], LEAVE[1]), false);
    heroLook(1);
    o.firstPath.style.opacity = '0';
    o.firstDot.style.opacity = '0';
    lastPose = { position: camera.position.clone(), target: new THREE.Vector3() };
  }
  function caption(t: number) {
    const cap = ease(seg(t, CAPTION[0], CAPTION[1]));
    if (o.captionRight) o.captionRight.innerHTML = cap >= 1 ? '第一级涡轮叶片'
      : `<span style="display:inline-grid;justify-items:end"><span style="grid-area:1/1;opacity:${1 - cap}">7 号发动机 · 总装中</span><span style="grid-area:1/1;opacity:${cap}">第一级涡轮叶片</span></span>`;
  }

  const probe = () => ({ t: lastT, camera: { position: lastPose.position.toArray(), target: lastPose.target.toArray() },
    rotor: rotorDegrees(lastT), speed: speedAt(lastT), blades: bladesNow, yaw: lastT >= C ? yawAt(lastT) : null,
    partsVisible: [...engine.parts.values()].filter(s => s.visible).length });
  return { seek, probe, events: filmEvents(), debug: { o, view, engine, items, yawAt, THREE } };
}
