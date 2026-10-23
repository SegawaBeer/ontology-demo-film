import { readFileSync } from 'node:fs';

const path = new URL('../public/models/turbofan.glb', import.meta.url);
const data = readFileSync(path);
if (data.subarray(0, 4).toString() !== 'glTF') throw new Error('not a GLB');
const jsonLength = data.readUInt32LE(12);
const gltf = JSON.parse(data.subarray(20, 20 + jsonLength).toString());

const sections = ['fan', 'fan-cowl', 'compressor', 'combustor', 'turbine', 'exhaust', 'nacelle', 'core-casing', 'shaft'];
const nodes = new Map(gltf.nodes.map(node => [node.name, node]));
const accessors = gltf.accessors;

const binStart = 12 + 8 + jsonLength + 8;
const bin = data.subarray(binStart);
let checkedPrimitives = 0;
for (const mesh of gltf.meshes) {
  for (const primitive of mesh.primitives) {
    const ia = accessors[primitive.indices];
    const pa = accessors[primitive.attributes.POSITION];
    const view = gltf.bufferViews[ia.bufferView];
    const start = (view.byteOffset ?? 0) + (ia.byteOffset ?? 0);
    const indices = new Uint32Array(bin.buffer, bin.byteOffset + start, ia.count);
    let max = 0;
    for (const index of indices) if (index > max) max = index;
    if (max >= pa.count) throw new Error(`index ${max} outside ${pa.count} vertices in ${mesh.name}`);
    checkedPrimitives++;
  }
}

let totalTriangles = 0;
const report = [];
for (const name of sections) {
  const node = nodes.get(name);
  if (!node) throw new Error(`missing section ${name}`);
  let triangles = 0;
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  const visit = index => {
    const current = gltf.nodes[index];
    if (current.mesh !== undefined) {
      for (const primitive of gltf.meshes[current.mesh].primitives) {
        const count = primitive.indices !== undefined ? accessors[primitive.indices].count : accessors[primitive.attributes.POSITION].count;
        triangles += count / 3;
        const position = accessors[primitive.attributes.POSITION];
        for (let axis = 0; axis < 3; axis++) {
          min[axis] = Math.min(min[axis], position.min[axis]);
          max[axis] = Math.max(max[axis], position.max[axis]);
        }
      }
    }
    for (const child of current.children ?? []) visit(child);
  };
  visit(gltf.nodes.indexOf(node));
  if (triangles === 0) throw new Error(`section ${name} has no triangles`);
  if (!(max[0] - min[0] > 0)) throw new Error(`section ${name} has no extent`);
  totalTriangles += triangles;
  report.push(`${name}: ${Math.round(triangles)} tris, x ${min[0].toFixed(2)}..${max[0].toFixed(2)}`);
}
if (totalTriangles < 200000) throw new Error(`unexpected triangle total ${totalTriangles}`);

const rotor = nodes.get('fan-rotor');
if (!rotor) throw new Error('fan rotor node missing');

console.log(report.join('\n'));
console.log(`PASS: 9 sections, ${Math.round(totalTriangles)} triangles, fan rotor present, ${(data.length / 1e6).toFixed(1)} MB`);
