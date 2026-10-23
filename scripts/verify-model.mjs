import { readFileSync } from 'node:fs';

const glbPath = new URL('../public/models/turbofan.glb', import.meta.url);
const jsonPath = new URL('../public/models/turbofan-parts.json', import.meta.url);

const data = readFileSync(glbPath);
if (data.subarray(0, 4).toString() !== 'glTF') throw new Error('not a GLB');
const jsonLength = data.readUInt32LE(12);
const gltf = JSON.parse(data.subarray(20, 20 + jsonLength).toString());
const manifest = JSON.parse(readFileSync(jsonPath, 'utf8'));

const fail = message => { throw new Error(message); };
const nodesByName = new Map(gltf.nodes.map(node => [node.name, node]));
const moduleIds = ['fan', 'fan-cowl', 'compressor', 'combustor', 'turbine', 'exhaust', 'core-casing', 'nacelle', 'shaft'];

for (const id of moduleIds) if (!nodesByName.has(id)) fail(`module node missing: ${id}`);
if (manifest.modules.length !== 9) fail(`expected 9 modules, found ${manifest.modules.length}`);

// Component and part nodes must mirror the manifest.
const partNodes = gltf.nodes.filter(node => node.mesh !== undefined);
const componentIds = new Set(manifest.components.map(c => c.id));
for (const node of partNodes) {
  const component = node.name.replace(/\.\d+$/, '');
  if (!componentIds.has(component)) fail(`part ${node.name} has no component in the manifest`);
}

const manifestIds = new Set(manifest.parts.map(p => p.id));
if (manifestIds.size !== manifest.parts.length) fail('duplicate part ids in the manifest');
if (partNodes.length !== manifest.parts.length) {
  fail(`GLB has ${partNodes.length} part nodes, manifest lists ${manifest.parts.length}`);
}
for (const node of partNodes) if (!manifestIds.has(node.name)) fail(`GLB part ${node.name} missing from the manifest`);

// Named components.
const blades = manifest.parts.filter(p => p.component === 'turbine.stage-1-blades');
if (blades.length !== 100) fail(`expected 100 stage-1 turbine blades, found ${blades.length}`);
if (new Set(blades.map(b => b.id)).size !== 100) fail('stage-1 blade ids are not unique');
for (const blade of blades) if (blade.type !== 'blade') fail(`${blade.id} is not typed as a blade`);
const fanBlades = manifest.parts.filter(p => p.component === 'fan.blades');
if (fanBlades.length !== 16) fail(`expected 16 fan blades, found ${fanBlades.length}`);

// Every connected component of the source mesh is accounted for.
const audit = manifest.audit;
if (!audit) fail('manifest has no audit block');
const assigned = manifest.parts.reduce((sum, part) => sum + (part.pieceCount ?? 0), 0);
if (assigned !== audit.assignedPieces) fail(`piece counts sum to ${assigned}, audit says ${audit.assignedPieces}`);
if (audit.assignedPieces + audit.replacedPieces !== audit.sourcePieces) {
  fail(`unassigned pieces: ${audit.sourcePieces} source, ${audit.assignedPieces} assigned, ${audit.replacedPieces} replaced`);
}
const generated = manifest.parts.filter(part => part.generated);
if (generated.length !== 100) fail(`expected 100 generated blades, found ${generated.length}`);
if (manifest.parts.some(part => !part.generated && !part.pieceCount)) fail('a source part has no pieces');

// Assembly order must reference real components and cover the ten steps.
const orders = new Set(manifest.components.map(c => c.order));
for (const step of [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) if (!orders.has(step)) fail(`assembly step ${step} is empty`);
for (const id of manifest.assembly) if (!componentIds.has(id)) fail(`assembly references unknown component ${id}`);

// Module and component counts agree with the parts list.
for (const module of manifest.modules) {
  const parts = manifest.parts.filter(p => p.module === module.id);
  if (parts.length !== module.partCount) fail(`${module.id}: partCount ${module.partCount} but ${parts.length} parts`);
}
for (const component of manifest.components) {
  const parts = manifest.parts.filter(p => p.component === component.id);
  if (parts.length !== component.partCount) fail(`${component.id}: partCount ${component.partCount} but ${parts.length} parts`);
  for (const id of component.parts) if (!manifestIds.has(id)) fail(`${component.id} lists unknown part ${id}`);
}

// Index ranges stay inside their vertex buffers.
const binStart = 12 + 8 + jsonLength + 8;
const bin = data.subarray(binStart);
for (const mesh of gltf.meshes) {
  for (const primitive of mesh.primitives) {
    const ia = gltf.accessors[primitive.indices];
    const pa = gltf.accessors[primitive.attributes.POSITION];
    const view = gltf.bufferViews[ia.bufferView];
    const start = (view.byteOffset ?? 0) + (ia.byteOffset ?? 0);
    const indices = new Uint32Array(bin.buffer, bin.byteOffset + start, ia.count);
    let max = 0;
    for (const index of indices) if (index > max) max = index;
    if (max >= pa.count) fail(`index ${max} outside ${pa.count} vertices in ${mesh.name}`);
  }
}

const moduleSummary = manifest.modules.map(m => `${m.id}:${m.partCount}`).join(' ');
console.log(`modules ${manifest.modules.length}, components ${manifest.components.length}, parts ${manifest.parts.length}`);
console.log(moduleSummary);
console.log(`pieces ${audit.sourcePieces} = assigned ${audit.assignedPieces} + replaced ${audit.replacedPieces}`);
console.log(`PASS: hierarchy, blade counts, manifest/GLB agreement, index bounds, ${(data.length / 1e6).toFixed(1)} MB`);
