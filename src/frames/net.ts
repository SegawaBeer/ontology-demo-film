// The 0:30 hand-off picture (frame=net-end): the net with every link laid and
// nothing highlighted. Opening 3B ends on it and the main timeline starts on it.
import * as THREE from 'three';
import type { GraphState } from './data';

export const NET_GRAPH: GraphState = {
  focus: false,
  relStyle: 'strong',
  lit: [],
  litEdges: [],
  chip: {},
  status: {},
  timing: [],
  counter: '34 个节点 · 35 条关系',
};

/** Same shell, cut and framing as treeToNet(). */
export const NET_VIEW = {
  ghost: ['nacelle', 'fan-cowl', 'core-casing'],
  direction: new THREE.Vector3(0.78, 0.34, 0.92),
  limits: { x: 0.78, y: 0.7 },
  shift: new THREE.Vector2(-0.06, 0.02),
  caption: ['实物', '7 号发动机 · 总装中'] as const,
};
