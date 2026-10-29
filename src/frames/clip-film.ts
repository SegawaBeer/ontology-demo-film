// Main timeline, global t 30–120 (主时间轴二). One view, one 7 号发动机:
//   30–64   part one (clip-q12)
//   64–86   the question-three clip (clip-q3), local time t − 64, drawn into the same view
//   86–101  question four (q4.ts)
//   101–109 back to the split view; the ending page (frame=ending) takes over at 109.
// Every frame is a pure function of t; the few checks of engine state below only
// mirror what the engine already shows.
import * as THREE from 'three';
import { mountFilmA, type FilmEvent } from './clip-q12';
import { mountClip, dialogHTML, graphAt as clipGraphAt } from './clip-q3';
import { q4DialogHTML, q4GraphAt, GAP_TAGS_OUT } from './q4';
import { createQ4Model, TAGS_OUT, GAP_TAGS } from './q4-model';
import { seg, ease } from './timing';
import { renderGraph } from './graph';
import { filmEvents } from './film-events';
import { graphBack } from './ending-graph';
import { blendPose, shiftPose, LIFT } from './clip-q12';
import type { Theme, Pose } from './scene';
import { clamp } from './timing';

export const START = 30;
export const DURATION = 103;   // see END_AT
export const CLIP_AT = 64;
export const Q4_AT = 86;
/** frame=film ends here; frame=ending (built on the opening's engine) carries on from the same picture. */
export const END_AT = 103;
const BACK = [101.0, 103.0] as const, UNGHOST = [101.4, 103.0] as const, UNCUT = [101.0, 102.2] as const, CAPTION_BACK = [101.0, 101.3] as const;
const RING = 'turbine.stage-1-blades';

export async function mountFilm(theme: Theme) {
  const a = await mountFilmA(theme);
  const { view, e7, colCam } = a.debug;
  const f = a.film;
  // The model column's own 720-wide camera (no view offset once the columns have settled).
  const project = (w: THREE.Vector3) => {
    const q = w.clone().project(view.camera);
    return { x: (q.x * 0.5 + 0.5) * 720, y: (-q.y * 0.5 + 0.5) * 1080 };
  };
  const clip = await mountClip(theme, {
    view, e7, caption: f.caption, project,
    ghost7: k => view.setGhostOf(e7, f.layerIds, k),
    // clip-q3 cuts everything but the ring and disk; here that is the net shell
    // (cutaway's own list) plus every other layer (its own plane).
    cut7: k => { view.cutaway(e7, k); view.cutLayers(e7, k, f.netShell); },
  });
  // cutaway()'s first call replaces every material's plane list, so it goes first;
  // then the layer plane is added (outside the engine, it cuts nothing). Both stay
  // attached from the start, so the materials are the same before and after 64.
  view.cutaway(e7, 0);
  view.cutLayers(e7, 0, f.netShell);
  const ringParts = e7.listParts(RING);
  const E3_SCALE = clip.e3.root.scale.x;
  const clipEnd = dialogHTML(22);
  const graphEnd = clipGraphAt(22);
  // Question four: 3 号 fades, the camera pushes in to 7 号's first-stage ring.
  e7.root.updateMatrixWorld(true);
  const from = clip.cameraAt(22);
  const ringCentre = new THREE.Vector3(-1.355, 0, 0).applyMatrix4(e7.root.matrixWorld);
  const RING_POSE: Pose = { target: ringCentre.clone().add(new THREE.Vector3(0, 0.05, 0)), position: new THREE.Vector3() };
  RING_POSE.position.copy(RING_POSE.target).addScaledVector(from.position.clone().sub(from.target).normalize(), 0.5 * from.position.distanceTo(from.target));
  const q4 = createQ4Model({
    view, e7, e3: clip.e3, hit7: clip.hit7, ring: f.ringGrey, red: clip.ink.red, green: theme === 'dark' ? '#4cc48f' : '#3fb27f',
    from, to: RING_POSE, project,
  });

  let lastT = START;
  let lastPose: Pose = f.lastPose();
  /** What clip-q3 and question four change on the shared engine, put back for part one. */
  function partOne(t: number) {
    clip.e3.root.visible = false;
    clip.e3.root.scale.setScalar(E3_SCALE);
    // clip-q3 places its 16 blades as separate meshes; part one has them in the ring.
    q4.putBack(clip.hit7);
    e7.setVisible(clip.hit7, true);
    view.cutLayers(e7, 0);
    q4.apply(CLIP_AT);
    a.seek(t);
    lastPose = f.lastPose();
  }

  function seek(input: number) {
    const t = clamp(input, START, DURATION);
    lastT = t;
    if (t < CLIP_AT) { partOne(t); return; }
    // Part one's last state (columns settled, P0, solid engine), then the clip on top.
    a.seek(CLIP_AT, false);
    if (t > BACK[0]) { backToSplit(t); return; }
    if (t > Q4_AT) { questionFour(t); return; }
    q4.apply(CLIP_AT);
    const local = t - CLIP_AT;
    clip.seek(local, 2);
    lastPose = clip.cameraAt(local);
    colCam.position.copy(view.camera.position);
    colCam.quaternion.copy(view.camera.quaternion);
    colCam.updateMatrixWorld();
  }

  /** Question four on top of the clip's 22.0 state (clip.seek(22) has set every engine state). */
  function questionFour(t: number) {
    clip.seek(22, false);
    const oldSvg = f.overlay.innerHTML, oldHtml = f.labels.innerHTML;
    q4.apply(t);
    lastPose = q4.cameraAt(t);
    view.applyPose(lastPose);
    view.cutaway(e7, 1);
    view.cutLayers(e7, 1, f.netShell);
    view.cutaway(clip.e3, 1);
    view.render(); view.render();
    colCam.position.copy(view.camera.position);
    colCam.quaternion.copy(view.camera.quaternion);
    colCam.updateMatrixWorld();
    // clip-q3's two engine tags fade out; the gap tags come in above the empty slots.
    const k = 1 - ease(seg(t, TAGS_OUT[0], TAGS_OUT[1]));
    let svg = k > 0 ? `<g opacity="${k.toFixed(3)}">${oldSvg}</g>` : '';
    let html = k > 0 ? `<div style="opacity:${k.toFixed(3)}">${oldHtml}</div>` : '';
    const g = ease(seg(t, GAP_TAGS, GAP_TAGS + 0.3)) * (1 - ease(seg(t, GAP_TAGS_OUT[0], GAP_TAGS_OUT[1])));
    if (g > 0) {
      // Stacked above the right end of the empty slots, each with a leader to its own group.
      // Right-aligned in the clear space above-left of the ring, leaders down to the gaps.
      const all = q4.groupScreen([...q4.home, ...q4.plant]);
      const x0 = all.x - 40, y0 = all.y0 - 210;
      ([[q4.home, '6', '本厂 · 20 分钟'], [q4.plant, '10', '二号厂区 · 2.5 小时']] as const).forEach(([ids, big, rest], i) => {
        const p = q4.groupScreen([...ids]), y = y0 + 34 * i;
        svg += `<g opacity="${g.toFixed(3)}"><circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="2.5" fill="var(--green)"/><path d="M${p.x.toFixed(2)} ${p.y.toFixed(2)} L${(x0 + 8).toFixed(2)} ${y.toFixed(2)}" stroke="var(--green)" stroke-width="1" fill="none" opacity="0.8"/></g>`;
        html += `<div class="gap-tag" style="left:${x0.toFixed(2)}px;top:${y.toFixed(2)}px;opacity:${g.toFixed(3)}"><b>${big}</b> · ${rest}</div>`;
      });
    }
    f.overlay.innerHTML = svg;
    f.labels.innerHTML = html;
    f.dialogRoot.innerHTML = q4DialogHTML(t, clipEnd);
    renderGraph(f.graphRoot, q4GraphAt(t, graphEnd));
  }

  /** 101–103: part one's 30.3–32.4 run backwards, starting from where question four left the camera. */
  const q4Dialog = q4DialogHTML(BACK[0], clipEnd);
  const q4Graph = q4GraphAt(BACK[0], graphEnd);
  const lift = new THREE.Vector3(0, LIFT, 0);
  function backToSplit(input: number) {
    const t = Math.min(input, END_AT);
    clip.seek(22, false);
    q4.apply(BACK[0]);
    const s = 32.4 - 2.1 * seg(t, BACK[0], BACK[1]);
    a.seek(s, false);
    const p = ease(seg(s, 30.3, 32.4));
    const pose = shiftPose(blendPose(f.NET, shiftPose(RING_POSE, lift.clone().negate()), p), lift.clone().multiplyScalar(p));
    f.applyCamera(s, pose);
    lastPose = pose;
    // The net shell stays ghosted (it is in both pictures); everything else turns solid again.
    const unghost = ease(seg(t, UNGHOST[0], UNGHOST[1]));
    for (const id of f.layerIds) view.setGhostOf(e7, [id], f.netShell.has(id) ? 1 : 1 - unghost);
    view.cutaway(e7, 1);
    view.cutLayers(e7, 1 - ease(seg(t, UNCUT[0], UNCUT[1])), f.netShell);
    view.render(); view.render();
    colCam.position.copy(pose.position); colCam.lookAt(pose.target); colCam.updateMatrixWorld();
    f.captionHTML(s, p);   // for its column position
    const k = ease(seg(t, CAPTION_BACK[0], CAPTION_BACK[1]));
    const A = '第一级涡轮叶环 · 其余部件半透明', B = '7 号发动机 · 总装中';
    f.caption.innerHTML = `<span>实物</span>${k >= 1 ? `<span>${B}</span>` : `<span class="xf"><span style="opacity:${(1 - k).toFixed(3)}">${A}</span><span style="opacity:${k.toFixed(3)}">${B}</span></span>`}`;
    f.overlay.innerHTML = '';
    f.labels.innerHTML = '';
    f.dialogRoot.innerHTML = q4Dialog;
    renderGraph(f.graphRoot, graphBack(t, q4Graph));
  }

  // From 64 on the graph column is drawn here, so the probe reads it back from the DOM.
  const graphDOM = () => ({
    lit: [], litEdges: [], counter: [...f.graphRoot.querySelectorAll('text')].find(x => x.textContent?.includes('个节点'))?.textContent ?? '',
    drawing: [...f.graphRoot.querySelectorAll('[data-draw]')].map(x => [...x.getAttribute('data-draw')!.split('>'), 0]),
  });
  const probe = () => {
    const p = a.probe();
    return { ...p, t: lastT, camera: { position: lastPose.position.toArray(), target: lastPose.target.toArray() },
      ...(lastT >= CLIP_AT ? { graph: graphDOM(), engineY: e7.root.position.y } : {}) };
  };
  const events: FilmEvent[] = filmEvents();
  // Ghost amounts as the engine has them (clip-q3 and question four ghost through setGhostOf too).
  const ghostOf = (partId: string) => view.layerAmount(e7, e7.getPart(partId)?.component ?? '');
  const debug = { ...a.debug, ghostOf, clip, film: f, q4 };
  return { seek, probe, events, debug };
}
