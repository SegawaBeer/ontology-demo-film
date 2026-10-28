// Ontology graph and dialog content for the style frames. Values follow
// 脚本/本体结构清单-v1.2 (demo data, no live platform).

export type Anchor = 'below' | 'above' | 'left' | 'right';
export type Tone = 'red' | 'amber' | 'green';
export type GraphNode = {
  id: string;
  x: number;
  y: number;
  label: string;
  kind: 'engine' | 'module' | 'component' | 'part' | 'biz';
  anchor: Anchor;
  group?: 'rd' | 'mfg' | 'qa' | 'scm';
  sub?: string;
};
/** `via` gives a cubic route (two control points, from → to) instead of the quadratic `bend`. */
export type GraphEdge = { from: string; to: string; kind: 'tree' | 'rel'; bend?: number; via?: [number, number, number, number] };

const moduleNames: [string, string][] = [
  ['m-fan', '风扇'], ['m-cowl', '进气罩'], ['m-comp', '压气机'], ['m-comb', '燃烧室'],
  ['m-turb', '涡轮'], ['m-exh', '尾喷管'], ['m-core', '核心机机匣'], ['m-nac', '外涵道机匣'], ['m-shaft', '主轴'],
];

export const nodes: GraphNode[] = [
  { id: 'e7', x: 250, y: 150, label: '7 号发动机', sub: '总装中', kind: 'engine', anchor: 'above' },
  { id: 'e3', x: 520, y: 150, label: '3 号发动机', sub: '澜川航空 · 在役', kind: 'engine', anchor: 'above' },
  ...moduleNames.map(([id, label], i): GraphNode => ({ id, x: 44 + i * 69, y: 248, label, kind: 'module', anchor: 'below' })),
  { id: 'c-fan', x: 44, y: 330, label: '风扇叶片', kind: 'component', anchor: 'below' },
  ...[1, 2, 3, 4].map((n, i): GraphNode => ({ id: `c-comp${n}`, x: 155 + i * 16, y: 330, label: `${n}`, kind: 'component', anchor: 'below' })),
  ...[1, 2, 3, 4, 5].map((n, i): GraphNode => ({ id: `c-t${n}`, x: 293 + i * 16, y: 330, label: `${n}`, kind: 'component', anchor: 'below' })),
  { id: 'blade', x: 293, y: 410, label: '第一级涡轮叶片', sub: '×100', kind: 'part', anchor: 'left' },

  { id: 'design', x: 62, y: 664, label: '设计版本', kind: 'biz', group: 'rd', anchor: 'right' },
  { id: 'drill', x: 62, y: 726, label: '打孔程序', kind: 'biz', group: 'rd', anchor: 'right' },
  { id: 'std', x: 186, y: 695, label: '检验标准', kind: 'biz', group: 'rd', anchor: 'right' },
  { id: 'mwo', x: 578, y: 664, label: '加工工单', kind: 'biz', group: 'mfg', anchor: 'left' },
  { id: 'spray', x: 462, y: 712, label: '喷涂工单', kind: 'biz', group: 'mfg', anchor: 'left' },
  { id: 'awo', x: 578, y: 760, label: '装配工单', kind: 'biz', group: 'mfg', anchor: 'left' },
  { id: 'insp', x: 186, y: 900, label: '检验记录', kind: 'biz', group: 'qa', anchor: 'right' },
  { id: 'coat', x: 62, y: 948, label: '涂层检测', kind: 'biz', group: 'qa', anchor: 'right' },
  { id: 'po', x: 578, y: 900, label: '采购订单', kind: 'biz', group: 'scm', anchor: 'left' },
  { id: 'powder', x: 372, y: 948, label: '粉末批次', kind: 'biz', group: 'scm', anchor: 'right' },
  { id: 'supplier', x: 578, y: 1000, label: '供应商', kind: 'biz', group: 'scm', anchor: 'left' },
  { id: 'stock', x: 262, y: 1010, label: '库存', kind: 'biz', group: 'scm', anchor: 'right' },
];

export const groups = [
  { id: 'rd', label: '研发', x: 32, y: 624, align: 'start' },
  { id: 'mfg', label: '生产', x: 608, y: 624, align: 'end' },
  { id: 'qa', label: '质量', x: 32, y: 858, align: 'start' },
  { id: 'scm', label: '供应链', x: 608, y: 858, align: 'end' },
] as const;

export const captions = [
  { x: 179, y: 356, text: '压气机叶环' },
  { x: 325, y: 356, text: '涡轮叶环' },
];

export const edges: GraphEdge[] = [
  ...moduleNames.map(([id]): GraphEdge => ({ from: 'e7', to: id, kind: 'tree' })),
  { from: 'm-fan', to: 'c-fan', kind: 'tree' },
  ...[1, 2, 3, 4].map((n): GraphEdge => ({ from: 'm-comp', to: `c-comp${n}`, kind: 'tree' })),
  ...[1, 2, 3, 4, 5].map((n): GraphEdge => ({ from: 'm-turb', to: `c-t${n}`, kind: 'tree' })),
  { from: 'c-t1', to: 'blade', kind: 'tree' },

  { from: 'design', to: 'blade', kind: 'rel', bend: -0.12 },
  { from: 'drill', to: 'blade', kind: 'rel', bend: -0.16 },
  { from: 'std', to: 'blade', kind: 'rel', bend: -0.08 },
  { from: 'mwo', to: 'blade', kind: 'rel', bend: 0.1 },
  { from: 'spray', to: 'blade', kind: 'rel', bend: 0.06 },
  { from: 'awo', to: 'e7', kind: 'rel', bend: 0.14 },
  { from: 'insp', to: 'blade', kind: 'rel', bend: -0.1 },
  { from: 'coat', to: 'powder', kind: 'rel', bend: -0.12 },
  { from: 'powder', to: 'spray', kind: 'rel', bend: 0.1 },
  { from: 'powder', to: 'supplier', kind: 'rel', bend: -0.1 },
  { from: 'po', to: 'supplier', kind: 'rel', bend: 0.2 },
  { from: 'po', to: 'm-comb', kind: 'rel', bend: -0.3 },
  // No single bend clears every label in the net, q3 and stale frames, so this
  // link takes a cubic route around the right side of the production group.
  { from: 'po', to: 'blade', kind: 'rel', via: [644, 960, 670, 480] },
  { from: 'stock', to: 'blade', kind: 'rel', bend: -0.06 },
  { from: 'blade', to: 'e3', kind: 'rel', bend: -0.3 },
];

export type GraphState = {
  focus: boolean;
  lit: string[];
  litEdges: [string, string][];
  /** `dx`, `dy`, `anchor`: optional move of the chip off its default spot (to keep it clear of lines). */
  chip: Record<string, { text: string; tone?: Tone; dx?: number; dy?: number; anchor?: 'start' | 'middle' | 'end' }>;
  status: Record<string, Tone>;
  timing: { text: string; x: number; y: number }[];
  counter?: string;
  relStyle?: 'soft' | 'strong';
  hidden?: [string, string][];
  fresh?: string[];
  /** `tone`: draw the head and stroke in a status colour instead of the lit blue. */
  drawing?: { from: string; to: string; progress: number; tone?: Tone }[];
  /** Links drawn in a status colour on top of their normal look; `progress` below 1 lays it down partly, with a head. */
  toneEdges?: { from: string; to: string; tone: Tone; amount?: number; progress?: number }[];
  /** Per-link opacity factor, keyed 'from>to' as in data.ts (absent = 1). */
  edgeAlpha?: Record<string, number>;
  /** Per-node strength of its status colour, 0..1 (absent = 1): below 1 the node is drawn plain with the coloured one on top. */
  statusAmount?: Record<string, number>;
  /** Opacity factor of the two ring captions (absent = 1). */
  captionAppear?: number;
  spawned?: { node: GraphNode; edges: [string, string, number][]; appear?: number }[];
  dots?: { hits: number[]; caption: string; scan?: number; appear?: number };
  /** Numeric opacity for unlit items; overrides `focus` when set. */
  dimLevel?: number;
  /** Per-node opacity floor, for neighbours that are checked and dropped. */
  nodeAlpha?: Record<string, number>;
  /** Expanding ring on a node, 0..1 through its life. */
  pulse?: Record<string, number>;
  /** Draw only these nodes, with no groups, captions or edges. */
  only?: string[];
  /** Per-node subtitle override. */
  sub?: Record<string, string>;
  /** Per-node fade-in, 0..1. */
  appear?: Record<string, number>;
  /** With `only`, the captions to keep (matched by their text). */
  captions?: string[];
  /** With `only`, the finished edges to keep drawing. */
  onlyEdges?: [string, string][];
  /** Match the drawing head's thickness so completion does not pop. */
  edgeWidth?: number;
  /** 0 = the net's strong link style, 1 = the soft three-column style; blends in between. */
  relMix?: number;
  /** 0..1: lit nodes, lit links, chips and timings fade back to their unlit look. */
  release?: number;
  /** Per-group label fade-in, 0..1 (absent = shown). */
  groupAppear?: Record<string, number>;
  /** For unlit nodes: a lit copy drawn on top at this opacity, 0..1. */
  litAmount?: Record<string, number>;
  /** Finished edges with a lit stroke fading over their normal look. */
  fading?: { from: string; to: string; amount: number; width?: number }[];
  /** Per-node chip opacity, 0..1 (absent = 1). */
  chipAmount?: Record<string, number>;
  /** Per-node opacity of the `fresh` ring, 0..1 (absent = 1). */
  freshAmount?: Record<string, number>;
  /** Like `pulse`, but any number of rings at once per node. */
  pulses?: Record<string, number[]>;
};

// First-stage blades in fleet order: engines 1–7, stock, engines 8–10.
export const fleetBlocks = [
  { key: '1', count: 100 }, { key: '2', count: 100 }, { key: '3', count: 100 }, { key: '4', count: 100 },
  { key: '5', count: 100 }, { key: '6', count: 100 }, { key: '7', count: 100 }, { key: '库', count: 16 },
  { key: '8', count: 100 }, { key: '9', count: 100 }, { key: '10', count: 100 },
];
