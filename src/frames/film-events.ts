// Sound events of the whole main timeline, 30–120 (主时间轴二 9.7), the same list on
// frame=film and frame=ending.
import { buildEvents, settleAt, type FilmEvent } from './clip-q12';
import { clipEvents } from './clip-q3';
import { q4Events } from './q4';
import { PATHS } from './ending-graph';

export function filmEvents(): FilmEvent[] {
  const out: FilmEvent[] = [
    ...buildEvents(),
    ...clipEvents().map(e => ({ ...e, t: e.t + 64 })),
    ...q4Events(settleAt),
    { t: 101.0, kind: 'slide', gain: 0.6, src: 'dialog', dur: 2.0 },           // panel out, back to the split view
    ...PATHS.map((): FilmEvent => ({ t: 103.0, kind: 'path', gain: 0.5, src: 'graph' })),  // the four paths light again
    { t: 105.0, kind: 'tone', gain: 0.5, src: '3d' },                          // ring and blade node flash
    { t: 113.0, kind: 'swap', gain: 0.5, src: '3d' },                          // ring blade 001 -> detailed blade (cross-fade start)
    { t: 116.4, kind: 'tone', gain: 0.8, src: '3d' },                          // the closing line
  ];
  return out.sort((a, b) => a.t - b.t);
}
