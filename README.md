# Turbofan Explorer

An interactive turbofan engine study in the browser. Open the cowl, separate the sections,
select a part and watch the engine run. Built with Three.js, TypeScript and Vite; static output,
no backend, no API key, no database.

The engine model is [Turbine | Turbofan Engine | Jet Engine](https://sketchfab.com/3d-models/turbine-turbofan-engine-jet-engine-74c6aceed86b4a41aaad3b93afc3e262)
by [blenderbirb](https://sketchfab.com/blenderbirb), CC BY 4.0, split into sections by
`tools/convert_turbofan.py`. This is an independent study, not manufacturer CAD and not a
specific engine type.

## Features

- Three views: assembled, cutaway (clipped half-section) and exploded separation.
- A separation slider from 0 to 100 percent.
- Section list and click-to-select on the model, with camera focus and a short explanation.
- "Show only this" isolates the selected section; "Back to engine" restores the whole model.
- Running mode: fan rotation, airflow particles, combustion glow, exhaust plume.
- Opt-in synthesized sound (fan and bypass airflow), no audio files.
- English and Chinese, four backgrounds, three render quality levels.
- Deep links: `?view=cutaway|explode`, `?section=fan`, `?lang=en`, `?background=paper`, `?quality=high`.

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

`npm test` validates the sectioned model: nine sections, triangle counts, index ranges and the
fan rotor node.

## Structure

| File | Purpose |
| --- | --- |
| `src/main.ts` | Scene, camera, views, separation, picking, UI wiring |
| `src/model.ts` | Loads the GLB, exposes sections and rotor nodes |
| `src/effects.ts` | Airflow particles, combustion glow, exhaust plume |
| `src/audio.ts` | Synthesized fan and airflow sound |
| `src/backdrop.ts` | Blueprint, paper and studio backgrounds |
| `src/i18n.ts` | Chinese source text with an English catalog |
| `tools/glb_pieces.py` | GLB parsing and connected-component splitting |
| `tools/convert_turbofan.py` | Section classification and sectioned GLB writer |

## Regenerating the model

```sh
python3 tools/convert_turbofan.py ~/Downloads/turbine__turbofan_engine__jet_engine.glb public/models/turbofan.glb
npm test
```

Section boundaries and layer rules (rotor, static, shell) live at the top of
`tools/convert_turbofan.py`.

## Credits and limits

Model: blenderbirb, CC BY 4.0. Interface and scene adapted from Turbine Explorer (MIT).
See `THIRD_PARTY_NOTICES.md` and `docs/SOURCES.md`. Geometry is illustrative; the model has no
detailed internal blade passages, so the cutaway shows casing and core surfaces rather than a
sectioned engine.
