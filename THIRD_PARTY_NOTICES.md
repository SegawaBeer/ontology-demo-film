# Third-party notices

The root MIT license covers this project's original code. The 3D model, fonts, environment
maps and libraries carry their own licenses, listed below.

## 3D model

- **Turbine | Turbofan Engine | Jet Engine**, by **blenderbirb**.
  Source: https://sketchfab.com/3d-models/turbine-turbofan-engine-jet-engine-74c6aceed86b4a41aaad3b93afc3e262
  License: **Creative Commons Attribution 4.0 International (CC BY 4.0)**, https://creativecommons.org/licenses/by/4.0/
  Changes: the downloaded GLB was split into 3,542 connected components, grouped into 2,027
  parts under 51 components and 9 modules, re-indexed and re-materialized without textures.
  The long inner shell was cut at four axial planes and distributed to the modules it passes
  through. The 100 inner flat plates of the first turbine stage were replaced by blades
  generated in `tools/blade.py`, and a rotor disc was added from `tools/rotor_disk.py`
  (original code, no third-party geometry). See `tools/convert_turbofan.py`.

## Bundled runtime assets

- Poly Haven studio HDR environments: CC0. Sources: https://polyhaven.com/a/poly_haven_studio and https://polyhaven.com/a/studio_kontrast_02 . License: https://polyhaven.com/license . Files and provenance are listed in `public/environment/README.md`.
- Manrope font: SIL Open Font License 1.1. Copyright and complete license: `public/fonts/Manrope-OFL.txt`.
- Space Grotesk font: SIL Open Font License 1.1. Copyright and complete license: `public/fonts/SpaceGrotesk-OFL.txt`.
- IBM Plex Mono font: SIL Open Font License 1.1. Copyright and complete license: `public/fonts/IBMPlexMono-OFL.txt`.
- Sound is synthesized by project code. No third-party sound recordings are bundled.

## Dependencies

- Three.js and its example modules: MIT, https://github.com/mrdoob/three.js/blob/dev/LICENSE . A copy of the installed version's license is included in `licenses/three-LICENSE.txt`.
- Vite: MIT, https://github.com/vitejs/vite/blob/main/LICENSE . Build-time dependency.
- TypeScript: Apache-2.0, https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt . Build-time dependency.

Exact versions are pinned by `package-lock.json`. Preserve applicable notices when redistributing.

## Upstream code

The interface and scene structure are adapted from **Turbine Explorer** by AlexZhangji
(https://github.com/AlexZhangji/turbine-explorer), MIT licensed. Its original copyright
notice is kept in `LICENSE`. Its procedural gas turbine geometry is not part of this project,
with one exception: `src/hero-blade.ts` is ported from Turbine Explorer's `src/blade-study.ts`
(the cooled blade study), modified to split the blade into separately controllable parts and to
drive it with continuous parameters. That file is used under the original license:

> MIT License
>
> Copyright (c) 2026 AlexZhangji
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software
> and associated documentation files (the "Software"), to deal in the Software without
> restriction, including without limitation the rights to use, copy, modify, merge, publish,
> distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
> Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or
> substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
> BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
> NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
> DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
