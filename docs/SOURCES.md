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
| fan | 122 | 17,536 |
| fan-cowl | 32 | 20,992 |
| compressor | 520 | 62,100 |
| combustor | 130 | 42,064 |
| turbine | 889 | 53,438 |
| exhaust | 67 | 20,528 |
| core-casing | 252 | 45,416 |
| nacelle | 14 | 18,416 |
| shaft | 1 | 1,920 |

Totals: 2,027 parts, 51 components, 282,410 triangles. The source mesh is 235,778 triangles;
100 flat two-triangle plates were removed and replaced by 100 generated blades (44,400
triangles), a rotor disc was added (1,152), and cutting the long shell at four planes added
about 1,280 triangles.

## The first-stage blades

`tools/blade.py` builds a cambered, twisted airfoil from six sections (chord 0.050, stagger 35°,
thickness 26% at the root) on a parallelogram platform and a three-lobe fir-tree root. Local +Y is
the radius and the root centre is the origin, so a blade can be turned or pulled out along its own
radius. The aerofoil spans r = 0.304 to 0.450 at x = −1.355 and its axial projection is 0.041, the
envelope of the original plates; neighbouring aerofoils clear each other by 0.002. A simple rotor
disc (`tools/rotor_disk.py`, rim 0.302, bore 0.170) sits under the roots. Both generators are
deterministic.

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
