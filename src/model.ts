import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

export type PartMeta = {
  id: string;
  name: string;
  type: string;
  component: string;
  module: string;
  center: [number, number, number];
  axial: [number, number];
  radius: [number, number];
  rotor: boolean;
};

export type ComponentMeta = {
  id: string;
  name: string;
  module: string;
  partCount: number;
  order: number;
  parts: string[];
};

export type ModuleMeta = {
  id: string;
  name: string;
  components: string[];
  partCount: number;
};

export type Manifest = {
  modules: ModuleMeta[];
  components: ComponentMeta[];
  parts: PartMeta[];
  assembly: string[];
};

type Group = {
  mesh: THREE.InstancedMesh | THREE.Mesh;
  material: THREE.MeshStandardMaterial;
  parts: string[];
  instanced: boolean;
  baseEnv: number;
};

type PartState = {
  meta: PartMeta;
  group: Group;
  index: number;          // instance index, -1 for a single mesh
  matrix: THREE.Matrix4;
  baseColor: THREE.Color;
  color: THREE.Color;
  visible: boolean;
  opacity: number;
  promoted: THREE.Mesh | null;
};

export type ComponentRuntime = {
  meta: ComponentMeta;
  group: THREE.Group;
  parts: string[];
  rotor: boolean;
};

export type ModuleRuntime = {
  meta: ModuleMeta;
  group: THREE.Group;
  components: ComponentRuntime[];
  center: THREE.Vector3;
};

export type EngineAssets = {
  manifest: Manifest;
  parts: Map<string, PartMeta>;
  components: Map<string, ComponentMeta>;
  modules: Map<string, ModuleMeta>;
  nodes: Map<string, THREE.Object3D>;
  geometries: Map<string, THREE.BufferGeometry>;
  materials: Map<string, THREE.Material>;
};

export async function loadEngineAssets(glbUrl: string, jsonUrl: string, onProgress?: (r: number) => void): Promise<EngineAssets> {
  const [gltf, manifest] = await Promise.all([
    new GLTFLoader().loadAsync(glbUrl, event => {
      if (onProgress && event.total) onProgress(Math.min(1, event.loaded / event.total));
    }),
    fetch(jsonUrl).then(r => r.json() as Promise<Manifest>),
  ]);
  const nodes = new Map<string, THREE.Object3D>();
  // GLTFLoader strips dots from node names, so ids are resolved both ways.
  const sanitize = (name: string) => name.replace(/\s/g, '_').replace(/[\[\]\.:\/]/g, '');
  gltf.scene.traverse(object => {
    if (!object.name) return;
    nodes.set(object.name, object);
    nodes.set(sanitize(object.name), object);
  });
  const parts = new Map(manifest.parts.map(p => [p.id, p]));
  for (const id of parts.keys()) {
    const node = nodes.get(id) ?? nodes.get(sanitize(id));
    if (node) nodes.set(id, node);
  }
  const components = new Map(manifest.components.map(c => [c.id, c]));
  const modules = new Map(manifest.modules.map(m => [m.id, m]));
  const geometries = new Map<string, THREE.BufferGeometry>();
  const materials = new Map<string, THREE.Material>();
  for (const [id] of parts) {
    const node = nodes.get(id) as THREE.Mesh | undefined;
    if (!node || !(node as THREE.Mesh).isMesh) continue;
    const mesh = node as THREE.Mesh;
    if (!geometries.has(mesh.geometry.uuid)) geometries.set(mesh.geometry.uuid, mesh.geometry);
    const material = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material;
    if (!materials.has(material.uuid)) materials.set(material.uuid, material);
  }
  return { manifest, parts, components, modules, nodes, geometries, materials };
}

const Y_AXIS = new THREE.Vector3(0, 1, 0);

export class Engine {
  root = new THREE.Group();
  modules: ModuleRuntime[] = [];
  parts = new Map<string, PartState>();
  pickables: THREE.Object3D[] = [];
  extracted = new THREE.Group();
  private assets: EngineAssets;
  private order = 0;

  constructor(assets: EngineAssets) {
    this.assets = assets;
    this.root.name = 'engine';
    this.extracted.name = 'extracted';
    this.root.add(this.extracted);
    this.build();
  }

  private build() {
    const { manifest, nodes, components } = this.assets;
    for (const moduleMeta of manifest.modules) {
      const moduleGroup = new THREE.Group();
      moduleGroup.name = moduleMeta.id;
      const runtime: ModuleRuntime = {
        meta: moduleMeta, group: moduleGroup, components: [],
        center: new THREE.Vector3(),
      };
      let count = 0;
      for (const componentId of moduleMeta.components) {
        const componentMeta = components.get(componentId);
        if (!componentMeta) continue;
        const componentGroup = new THREE.Group();
        componentGroup.name = componentId;
        moduleGroup.add(componentGroup);
        runtime.components.push({
          meta: componentMeta, group: componentGroup,
          parts: componentMeta.parts, rotor: false,
        });
        const buckets = new Map<string, string[]>();
        for (const partId of componentMeta.parts) {
          const node = nodes.get(partId) as THREE.Mesh | undefined;
          if (!node) continue;
          const mesh = node as THREE.Mesh;
          const material = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material;
          const key = mesh.geometry.uuid + '|' + material.uuid;
          if (!buckets.has(key)) buckets.set(key, []);
          buckets.get(key)!.push(partId);
        }
        for (const [, ids] of buckets) {
          const first = nodes.get(ids[0]) as THREE.Mesh;
          const source = (Array.isArray(first.material) ? first.material[0] : first.material) as THREE.MeshStandardMaterial;
          const material = source.clone() as THREE.MeshStandardMaterial;
          const sourceColor = source.color.clone();
          material.color.set('#ffffff');
          material.side = THREE.DoubleSide;
          material.shadowSide = THREE.DoubleSide;
          material.envMapIntensity = 1.15;
          const instanced = ids.length > 1;
          const mesh = instanced
            ? new THREE.InstancedMesh(first.geometry, material, ids.length)
            : new THREE.Mesh(first.geometry, material);
          mesh.name = ids.length > 1 ? `${componentId}-instanced` : ids[0];
          mesh.castShadow = true;
          mesh.receiveShadow = true;
          mesh.frustumCulled = false;
          const group: Group = {
            mesh, material, parts: ids, instanced,
            baseEnv: 1.15,
          };
          const baseColor = new THREE.Color('#ffffff');
          ids.forEach((id, index) => {
            const node = nodes.get(id)!;
            const meta = this.assets.parts.get(id)!;
            node.updateMatrix();
            const matrix = node.matrix.clone();
            if (instanced) {
              (mesh as THREE.InstancedMesh).setMatrixAt(index, matrix);
            } else {
              mesh.matrixAutoUpdate = false;
              mesh.matrix.copy(matrix);
              mesh.matrixWorldNeedsUpdate = true;
            }
            const state: PartState = {
              meta, group, index: instanced ? index : -1, matrix,
              baseColor: sourceColor.clone(), color: sourceColor.clone(),
              visible: true, opacity: 1, promoted: null,
            };
            this.parts.set(id, state);
            if (meta.rotor) {
              const comp = runtime.components[runtime.components.length - 1];
              comp.rotor = true;
            }
          });
          if (instanced) {
            const colors = new Float32Array(ids.length * 3);
            for (let i = 0; i < ids.length; i++) {
              colors[i * 3] = sourceColor.r; colors[i * 3 + 1] = sourceColor.g; colors[i * 3 + 2] = sourceColor.b;
            }
            (mesh as THREE.InstancedMesh).instanceColor = new THREE.InstancedBufferAttribute(colors, 3);
          } else {
            material.color.copy(sourceColor);
          }
          componentGroup.add(mesh);
          this.pickables.push(mesh);
          count += ids.length;
        }
      }
      this.modules.push(runtime);
      this.root.add(moduleGroup);
      const box = new THREE.Box3().setFromObject(moduleGroup);
      box.getCenter(runtime.center);
      this.order += count;
    }
  }

  /** Resolve any mix of module, component and part ids into part ids. */
  resolve(ids: string | string[]): string[] {
    const list = Array.isArray(ids) ? ids : [ids];
    const out = new Set<string>();
    for (const id of list) {
      if (this.parts.has(id)) { out.add(id); continue; }
      const component = this.assets.components.get(id);
      if (component) { component.parts.forEach(p => out.add(p)); continue; }
      const module = this.assets.modules.get(id);
      if (module) module.components.forEach(c => this.assets.components.get(c)?.parts.forEach(p => out.add(p)));
    }
    return [...out];
  }

  setColor(ids: string | string[], color: THREE.Color | string | null): void {
    const target = new THREE.Color(color ?? '#ffffff');
    for (const id of this.resolve(ids)) {
      const state = this.parts.get(id);
      if (!state) continue;
      state.color.copy(color ? target : state.baseColor);
      this.applyColor(state);
    }
  }

  private applyColor(state: PartState) {
    if (state.promoted) {
      (state.promoted.material as THREE.MeshStandardMaterial).color.copy(state.color);
      return;
    }
    if (state.index >= 0) {
      (state.group.mesh as THREE.InstancedMesh).setColorAt(state.index, state.color);
      (state.group.mesh as THREE.InstancedMesh).instanceColor!.needsUpdate = true;
    } else {
      state.group.material.color.copy(state.color);
    }
  }

  setDim(ids: string | string[], amount = 0.2): void {
    for (const id of this.resolve(ids)) {
      const state = this.parts.get(id);
      if (!state) continue;
      state.color.copy(state.baseColor).multiplyScalar(amount);
      this.applyColor(state);
    }
    this.refreshEnvironment();
  }

  setOpacity(ids: string | string[], opacity: number): void {
    const target = new Set(this.resolve(ids));
    if (!target.size) return;
    // Whole material groups can share one transparent material.
    const groups = new Map<Group, string[]>();
    for (const id of target) {
      const state = this.parts.get(id);
      if (!state) continue;
      if (!groups.has(state.group)) groups.set(state.group, []);
      groups.get(state.group)!.push(id);
    }
    for (const [group, parts] of groups) {
      const whole = parts.length === group.parts.length;
      if (whole) {
        for (const id of parts) this.unpromote(id);
        const material = group.material;
        material.transparent = opacity < 0.999;
        material.opacity = opacity;
        material.depthWrite = opacity >= 0.999;
        material.needsUpdate = true;
      } else {
        for (const id of parts) {
          this.promote(id);
          const state = this.parts.get(id)!;
          if (state.promoted) {
            const material = state.promoted.material as THREE.MeshStandardMaterial;
            material.transparent = opacity < 0.999;
            material.opacity = opacity;
            material.depthWrite = false;
            material.needsUpdate = true;
          }
        }
      }
    }
  }

  setVisible(ids: string | string[], visible: boolean): void {
    for (const id of this.resolve(ids)) {
      const state = this.parts.get(id);
      if (!state) continue;
      state.visible = visible;
      if (state.promoted) state.promoted.visible = visible;
      if (state.index >= 0) {
        const mesh = state.group.mesh as THREE.InstancedMesh;
        const m = state.matrix.clone();
        if (!visible) m.scale(new THREE.Vector3(0, 0, 0));
        mesh.setMatrixAt(state.index, m);
        mesh.instanceMatrix.needsUpdate = true;
      } else {
        state.group.mesh.visible = visible;
      }
    }
  }

  /** Translate and rotate a part away from its assembled position. */
  setTransform(ids: string | string[], transform: { position?: [number, number, number]; rotation?: [number, number, number] }): void {
    for (const id of this.resolve(ids)) {
      const state = this.parts.get(id);
      if (!state) continue;
      this.promote(id);
      const mesh = state.promoted!;
      const matrix = state.matrix.clone();
      if (transform.position) {
        matrix.premultiply(new THREE.Matrix4().makeTranslation(...transform.position));
      }
      if (transform.rotation) {
        const [rx, ry, rz] = transform.rotation;
        const rotation = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(rx, ry, rz));
        const center = new THREE.Vector3().setFromMatrixPosition(matrix);
        matrix.premultiply(new THREE.Matrix4().makeTranslation(...center.toArray()))
          .multiply(rotation)
          .multiply(new THREE.Matrix4().makeTranslation(...center.clone().negate().toArray()));
      }
      mesh.matrixAutoUpdate = false;
      mesh.matrix.copy(matrix);
      mesh.matrixWorldNeedsUpdate = true;
    }
  }

  private promote(id: string) {
    const state = this.parts.get(id);
    if (!state || state.promoted) return;
    const source = state.group.mesh as THREE.Mesh;
    const material = (source.material as THREE.MeshStandardMaterial).clone();
    material.color.copy(state.color);
    const mesh = new THREE.Mesh(source.geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.matrixAutoUpdate = false;
    mesh.matrix.copy(state.matrix);
    mesh.name = id;
    mesh.userData.partId = id;
    this.extracted.add(mesh);
    state.promoted = mesh;
    this.pickables.push(mesh);
    if (state.index >= 0) {
      const instanced = state.group.mesh as THREE.InstancedMesh;
      instanced.setMatrixAt(state.index, new THREE.Matrix4().makeScale(0, 0, 0));
      instanced.instanceMatrix.needsUpdate = true;
    } else {
      source.visible = false;
    }
  }

  private unpromote(id: string, restore = true) {
    const state = this.parts.get(id);
    if (!state || !state.promoted) return;
    this.extracted.remove(state.promoted);
    this.pickables = this.pickables.filter(p => p !== state.promoted);
    (state.promoted.material as THREE.Material).dispose();
    state.promoted = null;
    if (!restore) return;
    if (state.index >= 0) {
      const instanced = state.group.mesh as THREE.InstancedMesh;
      instanced.setMatrixAt(state.index, state.matrix);
      instanced.instanceMatrix.needsUpdate = true;
    } else {
      state.group.mesh.visible = state.visible;
    }
  }

  reset(): void {
    for (const id of [...this.parts.keys()]) this.unpromote(id);
    for (const [, state] of this.parts) {
      state.color.copy(state.baseColor);
      state.visible = true;
      state.opacity = 1;
      if (state.index >= 0) {
        (state.group.mesh as THREE.InstancedMesh).setColorAt(state.index, state.color);
      }
    }
    for (const [, state] of this.parts) {
      if (state.index >= 0) {
        (state.group.mesh as THREE.InstancedMesh).instanceColor!.needsUpdate = true;
      }
    }
    for (const moduleRuntime of this.modules) {
      for (const component of moduleRuntime.components) {
        const material = (component.group.children[0] as THREE.Mesh)?.material as THREE.MeshStandardMaterial;
        if (material) {
          material.transparent = false;
          material.opacity = 1;
          material.depthWrite = true;
          material.envMapIntensity = 1.15;
          material.needsUpdate = true;
        }
      }
    }
    this.refreshEnvironment();
  }

  private refreshEnvironment() {
    for (const moduleRuntime of this.modules) {
      for (const component of moduleRuntime.components) {
        for (const child of component.group.children) {
          const material = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
          if (material) material.envMapIntensity = 1.15;
        }
      }
    }
  }

  setModuleVisible(ids: string[], visible: boolean) {
    for (const id of ids) this.setVisible(id, visible);
  }

  update(delta: number, running: boolean, speed = 9.5) {
    if (!running) return;
    for (const moduleRuntime of this.modules) {
      for (const component of moduleRuntime.components) {
        if (component.rotor) component.group.rotation.x -= delta * speed;
      }
    }
  }

  pick(raycaster: THREE.Raycaster): string | null {
    const hits = raycaster.intersectObjects(this.pickables, false);
    for (const hit of hits) {
      const object = hit.object as THREE.Mesh;
      if (!object.visible) continue;
      if (object.userData.partId) return object.userData.partId as string;
      if ((object as THREE.InstancedMesh).isInstancedMesh && hit.instanceId !== undefined) {
        const name = object.name.replace('-instanced', '');
        const component = this.assets.components.get(name);
        if (!component) continue;
        for (const [id, state] of this.parts) {
          if (state.group.mesh === object && state.index === hit.instanceId) return id;
        }
        return null;
      }
      return object.name;
    }
    return null;
  }

  listParts(componentId: string): string[] {
    return this.assets.components.get(componentId)?.parts ?? [];
  }

  getPart(id: string): PartMeta | undefined {
    return this.assets.parts.get(id);
  }

  cloneEngine(): Engine {
    return new Engine(this.assets);
  }
}
