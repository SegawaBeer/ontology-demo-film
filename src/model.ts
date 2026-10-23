import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

export type SectionId =
  | 'fan' | 'fan-cowl' | 'compressor' | 'combustor' | 'turbine'
  | 'exhaust' | 'core-casing' | 'nacelle' | 'shaft';

export type Section = {
  id: SectionId;
  name: string;
  english: string;
  object: THREE.Group;
  rotor?: THREE.Object3D;
  shell?: THREE.Object3D;
  hot?: boolean;
};

export type TurbofanModel = {
  root: THREE.Group;
  sections: Section[];
  byId: Map<SectionId, Section>;
  rotors: THREE.Object3D[];
  size: THREE.Vector3;
  center: THREE.Vector3;
};

const META: Record<SectionId, { name: string; english: string; hot?: boolean }> = {
  fan: { name: '风扇', english: 'Fan' },
  'fan-cowl': { name: '进气罩', english: 'Fan cowl' },
  compressor: { name: '压气机', english: 'Compressor' },
  combustor: { name: '燃烧室', english: 'Combustor', hot: true },
  turbine: { name: '涡轮', english: 'Turbine', hot: true },
  exhaust: { name: '尾喷管', english: 'Exhaust nozzle', hot: true },
  'core-casing': { name: '核心机机匣', english: 'Core casing' },
  nacelle: { name: '外涵道机匣', english: 'Bypass duct' },
  shaft: { name: '主轴', english: 'Shaft' },
};

export async function loadTurbofan(url: string, onProgress?: (ratio: number) => void): Promise<TurbofanModel> {
  const gltf = await new GLTFLoader().loadAsync(url, event => {
    if (onProgress && event.total) onProgress(Math.min(1, event.loaded / event.total));
  });
  const root = gltf.scene;
  root.name = 'turbofan-scene';
  const container = (root.children.find(child => child.name === 'turbofan') as THREE.Group | undefined) ?? root;

  const sections: Section[] = [];
  const byId = new Map<SectionId, Section>();
  const rotors: THREE.Object3D[] = [];

  for (const child of [...container.children]) {
    const id = child.name as SectionId;
    if (!META[id]) continue;
    const section: Section = { id, ...META[id], object: child as THREE.Group };
    const rotor = child.getObjectByName(`${id}-rotor`);
    if (rotor) {
      section.rotor = rotor;
      rotors.push(rotor);
    }
    const shell = child.getObjectByName(`${id}-shell`);
    if (shell) section.shell = shell;
    sections.push(section);
    byId.set(id, section);
  }

  const order: SectionId[] = ['fan', 'fan-cowl', 'compressor', 'combustor', 'turbine', 'exhaust', 'nacelle', 'core-casing', 'shaft'];
  sections.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));

  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());

  root.traverse(object => {
    const mesh = object as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const material of materials as THREE.MeshStandardMaterial[]) {
      if (!material) continue;
      material.envMapIntensity = 1.15;
      material.side = THREE.FrontSide;
    }
  });

  return { root, sections, byId, rotors, size, center };
}

export function sectionOf(object: THREE.Object3D | null): SectionId | null {
  let node: THREE.Object3D | null = object;
  while (node) {
    if (META[node.name as SectionId]) return node.name as SectionId;
    node = node.parent;
  }
  return null;
}
