# Sources and limits

This project visualizes a turbofan engine with a downloaded 3D model. It is a study aid, not a
dimensionally validated engineering model.

- Model: Turbine | Turbofan Engine | Jet Engine by blenderbirb, Sketchfab, CC BY 4.0.
  https://sketchfab.com/3d-models/turbine-turbofan-engine-jet-engine-74c6aceed86b4a41aaad3b93afc3e262
- Background reading on turbofan operation: NASA Glenn Beginner's Guide to Aeronautics,
  https://www.grc.nasa.gov/www/k-12/airplane/aturbf.html and
  https://www.grc.nasa.gov/www/k-12/airplane/turbparts.html

## What the model is

The source mesh was modelled for visualization. Its 235,778 triangles were split into 3,542
connected components and regrouped into nine sections by axial and radial position:

| Section | Triangles | Axial range (model units) |
| --- | --- | --- |
| fan | 17,024 | 1.33 to 2.19 |
| fan cowl | 21,760 | 1.11 to 2.06 |
| compressor | 64,084 | 0.13 to 1.33 |
| combustor | 38,624 | -0.48 to 0.48 |
| turbine | 26,024 | -1.04 to 0.18 |
| exhaust | 5,846 | -1.78 to -1.04 |
| bypass duct | 59,248 | -1.92 to 1.34 |
| core casing | 896 | -1.90 to 2.05 |
| shaft | 2,272 | -1.79 to 2.00 |

## Limits

- Section boundaries are approximations derived from geometry, not from engineering drawings.
- The model has no detailed internal blade passages. The cutaway clips the near half of the whole
  assembly, so the cut faces show casing shells and ring surfaces rather than a sectioned
  compressor or turbine.
- Rotor and stator are separated by a radius rule, so only the fan blades and the compressor hub
  rotate. Combustor and turbine pieces are shown static.
- Rotation speed, airflow particles, combustion glow and the exhaust plume are illustrative.
  They are not a fluid, thermal or acoustic simulation.
- The model is not identified with any manufacturer or engine type. No manufacturer imagery,
  CAD or documents are distributed with this project.
- Sound is synthesized in the browser; it does not reproduce a recorded engine.
- The views, section names and explanations are written for general readers, not for maintenance
  or operating decisions.
