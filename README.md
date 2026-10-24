# Turbofan Explorer

An interactive turbofan engine study in the browser. Open the cowl, separate the modules,
pick a single part and watch the engine run. Built with Three.js, TypeScript and Vite; static
output, no backend, no API key, no database.

The engine model is [Turbine | Turbofan Engine | Jet Engine](https://sketchfab.com/3d-models/turbine-turbofan-engine-jet-engine-74c6aceed86b4a41aaad3b93afc3e262)
by [blenderbirb](https://sketchfab.com/blenderbirb), CC BY 4.0, split into modules, components
and parts by `tools/convert_turbofan.py`. The first-stage turbine blades, its rotor disc and the inner cone are generated in code.
This is an independent study, not manufacturer CAD and not a specific engine type.

## Hierarchy

`engine > module > component > part`, with 9 modules, 51 components and 2,027 parts:

| Module | Parts | Components |
| --- | --- | --- |
| fan 风扇 | 122 | 风扇叶片, 风扇叶尖封严块, 风扇轮毂, 整流锥, 风扇内整流罩 |
| fan-cowl 进气罩 | 32 | 进气唇口, 进气罩壳体, 进气罩后段 |
| compressor 压气机 | 520 | 四级叶环, 静子环, 支板, 鼓筒, 前喇叭口 |
| combustor 燃烧室 | 130 | 火焰筒, 喷嘴, 机匣, 内壳 |
| turbine 涡轮 | 889 | 五级叶片、轮毂、叶尖环、外环叶栅, 第一级轮盘, 内锥壳, 外环带 |
| exhaust 尾喷管 | 67 | 尾喷口, 尾喷口螺栓, 附件, 尾锥 |
| core-casing 核心机机匣 | 252 | 过渡段机匣, 机匣瓦块, 机匣螺栓, 内壁 |
| nacelle 外涵道机匣 | 14 | 外涵道机匣 |
| shaft 主轴 | 1 | 主轴 |

Assembly order runs blades → first-stage disc → first-stage tip ring and outer cascade
(second to fifth stages follow) → shaft → compressor → combustor → core casing → fan →
nacelle and cowl → exhaust and spinner. The first-stage blade, its rotor disc and the
inner cone are generated in code; the long black shell that used to run the length of the
engine is cut at four axial planes and distributed to the modules it passes through.

Ids are `module.component.part`, for example `turbine.stage-1-blades.001`. Ring-shaped
components are numbered from the smallest `atan2(z, y)` angle upward. The full list, including
centres, axial and radial ranges, assembly order and rotor flags, is written to
`public/models/turbofan-parts.json`.

## Runtime API

`src/model.ts` exports `loadEngineAssets(glbUrl, jsonUrl)` and `Engine`. Every method accepts a
part id, a component id, a module id, or an array of any of them.

| Method | Purpose |
| --- | --- |
| `new Engine(assets)` | Build one engine from loaded assets; geometries are shared between engines |
| `engine.cloneEngine()` | Second engine with independent colours, opacity, transforms and visibility |
| `setColor(ids, color \| null)` | Set a part colour; `null` restores the original material colour |
| `setDim(ids, amount = 0.2)` | Darken to a fraction of the original colour |
| `setOpacity(ids, alpha)` | Alpha 0–1; whole material groups share one transparent material |
| `setVisible(ids, visible)` | Show or hide |
| `setTransform(ids, { position?, rotation? })` | Offset and rotate relative to the assembled position |
| `reset()` | Restore colours, opacity, visibility and transforms |
| `getPart(id)` | Part metadata (name, centre, ranges, rotor flag) |
| `listParts(componentId)` | Part ids of one component |
| `pick(raycaster)` | Part id under the pointer, or `null` |
| `engine.update(delta, running)` | Rotor rotation for the given frame time |
| `engine.root` | `THREE.Group` to add to the scene |

Example: colour sixteen blades red and pull them out.

```ts
const blades = engine.listParts('turbine.stage-1-blades').slice(0, 16);
engine.setColor(blades, '#e03b2f');
engine.setTransform(blades, { position: [0.9, 0.75, 0.55] });

const second = engine.cloneEngine();
second.root.scale.setScalar(0.5);
second.root.position.set(2, -1, 1.2);
scene.add(second.root);
second.setColor(second.listParts('turbine.stage-1-blades').slice(0, 30), '#e03b2f');
```

Parts are packed into `InstancedMesh` objects per component and shared geometry, so the whole
engine draws in about 170 calls. A part made individually transparent is promoted to its own
mesh but stays under its component, so it keeps turning with the rotor; a part that is moved
goes to the extracted group and no longer turns with the rotor.

## Features

- Three views: assembled, cutaway (clipped half-section, plane follows the camera), exploded.
- Module list, click-to-select on the model, camera focus, section text.
- "Show only this" isolates a module; "Back to engine" restores the model.
- Running mode: rotor rotation, airflow particles, combustion glow, exhaust plume.
- Opt-in synthesized sound, no audio files. English and Chinese, four backgrounds, three
  quality levels.
- Deep links: `?view=cutaway|explode`, `?lang=en`, `?background=paper`, `?quality=high`,
  and the review states `?debug=single-blade|red-16|extract-16|dim|transparent|twin`,
  `?debug=assemble&step=1|3|6|full`.

## Run

Requires Node.js 22.18 or newer and a WebGL-capable browser.

```sh
npm ci
npm run dev
```

```sh
npm test
npm run build
npm run preview
```

`npm test` checks the module/component/part hierarchy, the 100 generated stage-1 blades, the 16
fan blades, manifest/GLB agreement, that every source connected component is assigned, the
assembly order and the index ranges.

## Structure

| File | Purpose |
| --- | --- |
| `src/main.ts` | Scene, camera, views, separation, picking, review states, UI |
| `src/model.ts` | Asset loading, `Engine` and the per-part API above |
| `src/effects.ts` | Airflow particles, combustion glow, exhaust plume |
| `src/audio.ts` | Synthesized fan and airflow sound |
| `src/backdrop.ts` | Blueprint, paper and studio backgrounds |
| `src/i18n.ts` | Chinese source text with an English catalog |
| `tools/glb_pieces.py` | GLB parsing and connected-component splitting |
| `tools/parts.py` | Groups connected components into parts |
| `tools/blade.py` | Generates the first-stage turbine blade |
| `tools/convert_turbofan.py` | Classification, hierarchy, GLB and manifest writer |
| `tools/analyze_parts.py` | Read-only geometry report used while classifying |

## Regenerating the model

```sh
python3 tools/convert_turbofan.py ~/Downloads/turbine__turbofan_engine__jet_engine.glb public/models/turbofan.glb public/models/turbofan-parts.json
npm test
```

The command is deterministic: the same input produces the same GLB and manifest. Classification
rules, stage positions and the assembly order live at the top of
`tools/convert_turbofan.py`; blade proportions live in `tools/blade.py`.

## Credits and limits

Model: blenderbirb, CC BY 4.0. Interface and scene adapted from Turbine Explorer (MIT).
See `THIRD_PARTY_NOTICES.md` and `docs/SOURCES.md`. Geometry is illustrative: the source model
has no detailed internal blade passages, so the cutaway shows casing and ring surfaces rather
than a sectioned engine. Component boundaries come from geometry, not drawings.
