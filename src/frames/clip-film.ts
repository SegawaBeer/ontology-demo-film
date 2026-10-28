// Main timeline, global t 30–120 (主时间轴二). One view, one 7 号发动机:
//   30–64   part one (clip-q12)
//   64–86   the question-three clip (clip-q3), local time t − 64, drawn into the same view
//   86–101  question four (q4.ts)
//   101–109 back to the split view; the ending page (frame=ending) takes over at 109.
// Every frame is a pure function of t; the few checks of engine state below only
// mirror what the engine already shows.
import * as THREE from 'three';
import { mountFilmA, type FilmEvent } from './clip-q12';
import { mountClip, dialogHTML } from './clip-q3';
import { q4DialogHTML } from './q4';
import type { Theme, Pose } from './scene';
import { clamp } from './timing';

export const START = 30;
export const DURATION = 120;
export const CLIP_AT = 64;
export const Q4_AT = 86;
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

  let lastT = START;
  let lastPose: Pose = f.lastPose();
  /** What clip-q3 and question four change on the shared engine, put back for part one. */
  function partOne(t: number) {
    clip.e3.root.visible = false;
    clip.e3.root.scale.setScalar(E3_SCALE);
    // clip-q3 places its 16 blades as separate meshes; part one has them in the ring.
    if (e7.parts.get(clip.hit7[0])!.promoted) e7.setOpacity(ringParts, 1);
    e7.setVisible(clip.hit7, true);
    view.cutLayers(e7, 0);
    a.seek(t);
    lastPose = f.lastPose();
  }

  function seek(input: number) {
    const t = clamp(input, START, DURATION);
    lastT = t;
    if (t < CLIP_AT) { partOne(t); return; }
    // Part one's last state (columns settled, P0, solid engine), then the clip on top.
    a.seek(CLIP_AT, false);
    const local = Math.min(t, Q4_AT) - CLIP_AT;
    clip.seek(local, 2);
    lastPose = clip.cameraAt(local);
    colCam.position.copy(view.camera.position);
    colCam.quaternion.copy(view.camera.quaternion);
    colCam.updateMatrixWorld();
    if (t <= Q4_AT) return;
    // Question four builds on the clip's 22.0 state.
    f.dialogRoot.innerHTML = q4DialogHTML(t, clipEnd);
  }

  const probe = () => ({
    ...a.probe(),
    t: lastT,
    camera: { position: lastPose.position.toArray(), target: lastPose.target.toArray() },
  });
  const events: FilmEvent[] = [
    ...a.events,
    ...clip.events.map(e => ({ ...e, t: e.t + CLIP_AT })),
  ].sort((x, y) => x.t - y.t);
  const debug = { ...a.debug, clip, film: f };
  return { seek, probe, events, debug };
}
