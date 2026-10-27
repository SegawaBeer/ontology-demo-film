import * as THREE from 'three';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { loadEngineAssets, Engine } from '../model';

export type Theme = 'dark' | 'light';
/**
 * `layered`: every component outside `solid` can also be ghosted on its own
 * with setGhostOf (one amount and one fade per component). The cut plane still
 * applies only to the `ghost` list.
 */
export type Shell = { solid?: string[]; ghost?: string[]; ghostAmount?: number; layered?: boolean };
type Layer = { materials: THREE.MeshStandardMaterial[]; meshes: THREE.Mesh[]; parts: string[]; amount: number; fade: number };
export type Pose = { position: THREE.Vector3; target: THREE.Vector3 };

const palette = {
  dark: { bg: '#0b1016', ghost: '#8fa6b6', ghostOpacity: 0.11, red: '#ff4a3a', exposure: 1.08, hemi: 0.45 },
  light: { bg: '#eef0ee', ghost: '#5b6b78', ghostOpacity: 0.1, red: '#e0362a', exposure: 1.0, hemi: 0.75 },
};

const lerp = THREE.MathUtils.lerp;

export async function createModelView(canvas: HTMLCanvasElement, theme: Theme, width = 720) {
  const height = 1080;
  const look = palette[theme];
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(2);
  renderer.setSize(width, height, false);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = look.exposure;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.localClippingEnabled = true;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(look.bg);
  const camera = new THREE.PerspectiveCamera(24, width / height, 0.05, 80);

  scene.add(new THREE.HemisphereLight('#dfeaf2', '#0a1418', look.hemi));
  const key = new THREE.DirectionalLight('#fff4e2', 2.4);
  key.position.set(-3.5, 6.5, 5.5);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -5, right: 5, top: 6, bottom: -6, near: 0.5, far: 24 });
  key.shadow.bias = -0.0006;
  scene.add(key);
  const fill = new THREE.DirectionalLight('#bcd7ea', 0.7);
  fill.position.set(5, 2.5, -4);
  scene.add(fill);
  const rim = new THREE.DirectionalLight('#8fc6de', 0.5);
  rim.position.set(0, -4.5, 3);
  scene.add(rim);

  const hdr = await new RGBELoader().loadAsync('/environment/poly_haven_studio_1k.hdr');
  const pmrem = new THREE.PMREMGenerator(renderer);
  hdr.mapping = THREE.EquirectangularReflectionMapping;
  scene.environment = pmrem.fromEquirectangular(hdr).texture;
  hdr.dispose();
  pmrem.dispose();

  const assets = await loadEngineAssets('/models/turbofan.glb', '/models/turbofan-parts.json');
  const ghosts = new Map<Engine, { materials: THREE.MeshStandardMaterial[]; meshes: THREE.Mesh[]; parts: string[]; amount: number }>();
  const cuts = new Map<Engine, THREE.Plane>();
  const sweeps = new Map<Engine, THREE.Plane>();
  const ghostColor = new THREE.Color(look.ghost);

  /**
   * With `solid`, only those components keep their metal and the rest can turn
   * into a faint matte ghost. With `ghost`, only the listed modules or components do.
   */
  function addEngine(shell: Shell, position: THREE.Vector3, scale: number) {
    const engine = new Engine(assets);
    engine.root.position.copy(position);
    engine.root.scale.setScalar(scale);
    scene.add(engine.root);
    engine.setVisible('turbine.hero-blade', false);
    const solid = new Set(shell.solid ?? []);
    const ghost = new Set(shell.ghost ?? []);
    const entry = { materials: [] as THREE.MeshStandardMaterial[], meshes: [] as THREE.Mesh[], parts: [] as string[], amount: -1 };
    for (const module of engine.modules) {
      for (const component of module.components) {
        const isGhost = shell.ghost ? ghost.has(component.meta.id) || ghost.has(module.meta.id) : !solid.has(component.meta.id);
        if (!isGhost) continue;
        entry.parts.push(...engine.listParts(component.meta.id));
        component.group.traverse(object => {
          const mesh = object as THREE.Mesh;
          if (!mesh.isMesh) return;
          const material = mesh.material as THREE.MeshStandardMaterial;
          material.userData.base = { metalness: material.metalness, roughness: material.roughness, env: material.envMapIntensity };
          entry.materials.push(material);
          entry.meshes.push(mesh);
        });
      }
    }
    ghosts.set(engine, entry);
    setGhost(engine, shell.ghostAmount ?? 1);
    if (shell.layered) {
      const map = new Map<string, Layer>();
      for (const module of engine.modules) {
        for (const component of module.components) {
          if (solid.has(component.meta.id) || component.meta.id === 'turbine.hero-blade') continue;
          const layer: Layer = { materials: [], meshes: [], parts: engine.listParts(component.meta.id), amount: -1, fade: -1 };
          component.group.traverse(object => {
            const mesh = object as THREE.Mesh;
            if (!mesh.isMesh) return;
            const material = mesh.material as THREE.MeshStandardMaterial;
            material.userData.base ??= { metalness: material.metalness, roughness: material.roughness, env: material.envMapIntensity };
            layer.materials.push(material);
            layer.meshes.push(mesh);
          });
          map.set(component.meta.id, layer);
        }
      }
      layers.set(engine, map);
    }
    return engine;
  }

  const layers = new Map<Engine, Map<string, Layer>>();
  /** Component ids that setGhostOf can drive on a `layered` engine. */
  const layerIds = (engine: Engine) => [...(layers.get(engine)?.keys() ?? [])];

  /**
   * Per-component ghost, same look as setGhost. `fade` 1 takes the component
   * down to opacity 0 on top of the ghost (used to clear a path for a moving part).
   */
  function setGhostOf(engine: Engine, ids: string[], amount: number, fade = 0) {
    const map = layers.get(engine);
    if (!map) return;
    const color = new THREE.Color();
    for (const id of ids) {
      const layer = map.get(id);
      if (!layer || (Math.abs(layer.amount - amount) < 1e-4 && Math.abs(layer.fade - fade) < 1e-4)) continue;
      layer.amount = amount;
      layer.fade = fade;
      for (const pid of layer.parts) {
        const state = engine.parts.get(pid);
        if (state) engine.setColor(pid, color.copy(state.baseColor).lerp(ghostColor, amount));
      }
      const transparent = amount > 0.001 || fade > 0.001;
      const depthWrite = amount < 0.6 && fade < 0.001;
      for (const material of layer.materials) {
        const base = material.userData.base;
        material.metalness = lerp(base.metalness, 0.15, amount);
        material.roughness = lerp(base.roughness, 0.75, amount);
        material.envMapIntensity = lerp(base.env, 0.4, amount);
        material.opacity = lerp(1, look.ghostOpacity, 1 - (1 - amount) ** 2) * (1 - fade);
        if (material.transparent !== transparent || material.depthWrite !== depthWrite) {
          material.transparent = transparent;
          material.depthWrite = depthWrite;
          material.needsUpdate = true;
        }
      }
      for (const mesh of layer.meshes) { mesh.castShadow = amount < 0.5 && fade < 0.5; mesh.receiveShadow = amount < 0.5 && fade < 0.5; }
    }
  }

  /** Opacity a part is drawn with right now (0 when hidden). */
  function partOpacity(engine: Engine, id: string) {
    const state = engine.parts.get(id);
    if (!state || !state.visible) return 0;
    const material = (state.promoted?.material ?? state.group.material) as THREE.MeshStandardMaterial;
    return material.transparent ? material.opacity : 1;
  }

  /** 0 = original metal, 1 = faint matte ghost. Cheap to call every frame. */
  function setGhost(engine: Engine, amount: number) {
    const entry = ghosts.get(engine);
    if (!entry || Math.abs(entry.amount - amount) < 1e-4) return;
    entry.amount = amount;
    const color = new THREE.Color();
    for (const id of entry.parts) {
      const state = engine.parts.get(id);
      if (!state) continue;
      engine.setColor(id, color.copy(state.baseColor).lerp(ghostColor, amount));
    }
    const transparent = amount > 0.001;
    const depthWrite = amount < 0.6;
    for (const material of entry.materials) {
      const base = material.userData.base;
      material.metalness = lerp(base.metalness, 0.15, amount);
      material.roughness = lerp(base.roughness, 0.75, amount);
      material.envMapIntensity = lerp(base.env, 0.4, amount);
      material.opacity = lerp(1, look.ghostOpacity, 1 - (1 - amount) ** 2);
      if (material.transparent !== transparent || material.depthWrite !== depthWrite) {
        material.transparent = transparent;
        material.depthWrite = depthWrite;
        material.needsUpdate = true;
      }
    }
    for (const mesh of entry.meshes) { mesh.castShadow = amount < 0.5; mesh.receiveShadow = amount < 0.5; }
  }

  // Ghost materials take the half-section plane; every material takes the
  // reveal sweep. Planes are shared objects so per-frame updates are cheap.
  function attachPlanes(engine: Engine) {
    const ghostSet = new Set<THREE.Material>(ghosts.get(engine)?.materials ?? []);
    const cut = cuts.get(engine), sweep = sweeps.get(engine);
    engine.root.traverse(object => {
      const mesh = object as THREE.Mesh;
      if (!mesh.isMesh) return;
      for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        const planes: THREE.Plane[] = [];
        if (cut && ghostSet.has(material)) planes.push(cut);
        if (sweep) planes.push(sweep);
        material.clippingPlanes = planes.length ? planes : null;
        material.clipShadows = true;
      }
    });
  }

  /**
   * Clip the near half of an engine's ghost shell, facing the camera. `amount`
   * slides the plane in from outside the engine (0) to the axis (1).
   */
  function cutaway(engine: Engine, amount = 1) {
    engine.root.updateMatrixWorld(true);
    const axis = new THREE.Vector3(1, 0, 0).transformDirection(engine.root.matrixWorld);
    const origin = new THREE.Vector3().setFromMatrixPosition(engine.root.matrixWorld);
    const toCamera = camera.position.clone().sub(origin);
    const normal = toCamera.sub(axis.clone().multiplyScalar(toCamera.dot(axis))).normalize().negate();
    let plane = cuts.get(engine);
    const fresh = !plane;
    if (!plane) { plane = new THREE.Plane(); cuts.set(engine, plane); }
    plane.setFromNormalAndCoplanarPoint(normal, origin);
    plane.constant += (1 - amount) * 1.4 * engine.root.scale.x;
    if (fresh) attachPlanes(engine);
  }

  /** Reveal an engine from its rear up to world x; null shows all of it. */
  function setSweep(engine: Engine, x: number | null) {
    let plane = sweeps.get(engine);
    const fresh = !plane;
    if (!plane) { plane = new THREE.Plane(); sweeps.set(engine, plane); }
    plane.set(new THREE.Vector3(-1, 0, 0), x ?? 1e6);
    if (fresh) attachPlanes(engine);
  }

  function worldOf(engine: Engine, partId: string) {
    const meta = engine.getPart(partId);
    if (!meta) return null;
    engine.root.updateMatrixWorld(true);
    return new THREE.Vector3(...meta.center).applyMatrix4(engine.root.matrixWorld);
  }

  function project(world: THREE.Vector3) {
    const p = world.clone().project(camera);
    return { x: (p.x * 0.5 + 0.5) * width, y: (-p.y * 0.5 + 0.5) * height };
  }

  function applyPose(pose: Pose) {
    camera.position.copy(pose.position);
    camera.lookAt(pose.target);
    camera.updateMatrixWorld();
  }

  /** Camera pose that aims along `direction` and fits every engine in the column. */
  function fit(engines: Engine[], direction: THREE.Vector3, limits = { x: 0.84, y: 0.8 }, shift = new THREE.Vector2()): Pose {
    const box = new THREE.Box3();
    for (const engine of engines) {
      engine.root.updateMatrixWorld(true);
      box.union(new THREE.Box3().setFromObject(engine.root));
    }
    const corners: THREE.Vector3[] = [];
    for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) corners.push(new THREE.Vector3(x, y, z));
    const target = box.getCenter(new THREE.Vector3());
    const dir = direction.clone().normalize();
    let distance = box.getSize(new THREE.Vector3()).length() * 2;
    for (let i = 0; i < 6; i++) {
      applyPose({ position: target.clone().addScaledVector(dir, distance), target });
      let ex = 0, ey = 0;
      for (const c of corners) {
        const p = c.clone().project(camera);
        ex = Math.max(ex, Math.abs(p.x - shift.x));
        ey = Math.max(ey, Math.abs(p.y - shift.y));
      }
      distance *= Math.max(ex / limits.x, ey / limits.y);
    }
    return { position: target.clone().addScaledVector(dir, distance), target };
  }

  function frame(engines: Engine[], direction: THREE.Vector3, limits = { x: 0.84, y: 0.8 }, shift = new THREE.Vector2()) {
    applyPose(fit(engines, direction, limits, shift));
  }

  return {
    scene, camera, renderer, width, height,
    addEngine, setGhost, setGhostOf, layerIds, partOpacity, cutaway, setSweep, worldOf, project, fit, applyPose, frame,
    render: () => renderer.render(scene, camera),
  };
}

export type ModelView = Awaited<ReturnType<typeof createModelView>>;
