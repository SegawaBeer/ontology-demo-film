# Third-party notices

The root MIT license covers this project's original code. The 3D model, fonts, environment
maps and libraries carry their own licenses, listed below.

## 3D model

- **Turbine | Turbofan Engine | Jet Engine**, by **blenderbirb**.
  Source: https://sketchfab.com/3d-models/turbine-turbofan-engine-jet-engine-74c6aceed86b4a41aaad3b93afc3e262
  License: **Creative Commons Attribution 4.0 International (CC BY 4.0)**, https://creativecommons.org/licenses/by/4.0/
  Changes: the downloaded GLB was split into 3,542 connected components, grouped into 2,021
  parts under 40 components and 9 modules, re-indexed and re-materialized without textures.
  The 100 inner flat plates of the first turbine stage were replaced by blades generated in
  `tools/blade.py` (original code, no third-party geometry). See `tools/convert_turbofan.py`.

## Bundled runtime assets

- Poly Haven studio HDR environments: CC0. Sources: https://polyhaven.com/a/poly_haven_studio and https://polyhaven.com/a/studio_kontrast_02 . License: https://polyhaven.com/license . Files and provenance are listed in `public/environment/README.md`.
- Manrope font: SIL Open Font License 1.1. Copyright and complete license: `public/fonts/Manrope-OFL.txt`.
- Space Grotesk font: SIL Open Font License 1.1. Copyright and complete license: `public/fonts/SpaceGrotesk-OFL.txt`.
- Sound is synthesized by project code. No third-party sound recordings are bundled.

## Dependencies

- Three.js and its example modules: MIT, https://github.com/mrdoob/three.js/blob/dev/LICENSE . A copy of the installed version's license is included in `licenses/three-LICENSE.txt`.
- Vite: MIT, https://github.com/vitejs/vite/blob/main/LICENSE . Build-time dependency.
- TypeScript: Apache-2.0, https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt . Build-time dependency.

Exact versions are pinned by `package-lock.json`. Preserve applicable notices when redistributing.

## Upstream code

The interface and scene structure are adapted from **Turbine Explorer** by AlexZhangji
(https://github.com/AlexZhangji/turbine-explorer), MIT licensed. Its original copyright
notice is kept in `LICENSE`. Its procedural gas turbine geometry is not part of this project.
