# Sources and limits

This project visualizes a turbofan engine with a downloaded 3D model, split into modules,
components and individual parts. It is a study aid, not a dimensionally validated engineering
model.

- Model: Turbine | Turbofan Engine | Jet Engine by blenderbirb, Sketchfab, CC BY 4.0.
  https://sketchfab.com/3d-models/turbine-turbofan-engine-jet-engine-74c6aceed86b4a41aaad3b93afc3e262
- Background reading on turbofan operation: NASA Glenn Beginner's Guide to Aeronautics,
  https://www.grc.nasa.gov/www/k-12/airplane/aturbf.html and
  https://www.grc.nasa.gov/www/k-12/airplane/turbparts.html

## What the model is

The source mesh has 235,778 triangles in 3,542 connected components. The converter groups a
component or several overlapping components into one part, sorts every part into a component
and module, and writes both the GLB and `turbofan-parts.json`.

| Module | Parts | Triangles |
| --- | --- | --- |
| fan | 121 | 17,024 |
| fan-cowl | 32 | 20,992 |
| compressor | 519 | 61,780 |
| combustor | 194 | 61,168 |
| turbine | 887 | 32,702 |
| exhaust | 66 | 19,984 |
| core-casing | 187 | 26,792 |
| nacelle | 14 | 18,416 |
| shaft | 1 | 1,920 |

Totals: 2,021 parts, 40 components, 260,778 triangles. The difference from the source count is
the first turbine stage: 100 flat two-triangle plates (200 triangles) were replaced by 100
generated blades (25,200 triangles).

## The first-stage blades

`tools/blade.py` builds a cambered, twisted airfoil from five sections with a root platform, local
+Y along the radius, so one blade can be rotated or pulled out along its own radius. The blade
spans r = 0.304 to 0.450 at x = −1.355, the volume the original plates occupied. The generator is
deterministic; the same code produces the same 100 blades in every build.

## Limits

- Module, component and part boundaries are approximations derived from geometry, not from
  engineering drawings. The component between the combustor and the turbine is treated as part of
  the core casing because it is a smooth cylindrical shell without blades.
- The model has no detailed internal blade passages. The cutaway clips the near half of the whole
  assembly, so cut faces show casing shells and ring surfaces rather than a sectioned engine.
- Rotor parts are marked per component. Fan, compressor and turbine discs and blades rotate;
  casings, combustor and exhaust do not.
- Rotation speed, airflow particles, combustion glow and the exhaust plume are illustrative.
  They are not a fluid, thermal or acoustic simulation.
- The model is not identified with any manufacturer or engine type. No manufacturer imagery,
  CAD or documents are distributed with this project.
- Sound is synthesized in the browser; it does not reproduce a recorded engine.
- Names and explanations are written for general readers, not for maintenance decisions.
