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

const meshTriangles = meshIndex => {
  const mesh = gltf.meshes[meshIndex];
  return mesh.primitives.reduce((sum, primitive) => {
    const accessor = primitive.indices !== undefined
      ? gltf.accessors[primitive.indices]
      : gltf.accessors[primitive.attributes.POSITION];
    return sum + accessor.count / 3;
  }, 0);
};

// Every part node has a manifest entry and the same triangle count.
const partNodes = gltf.nodes.filter(node => node.mesh !== undefined);
const manifestIds = new Set(manifest.parts.map(p => p.id));
if (manifestIds.size !== manifest.parts.length) fail('duplicate part ids in the manifest');
if (partNodes.length !== manifest.parts.length) {
  fail(`GLB has ${partNodes.length} part nodes, manifest lists ${manifest.parts.length}`);
}
const byId = new Map(manifest.parts.map(p => [p.id, p]));
for (const node of partNodes) {
  const part = byId.get(node.name);
  if (!part) fail(`GLB part ${node.name} missing from the manifest`);
  if (Math.round(meshTriangles(node.mesh)) !== part.triangles) {
    fail(`${node.name}: GLB has ${Math.round(meshTriangles(node.mesh))} triangles, manifest ${part.triangles}`);
  }
}
const componentIds = new Set(manifest.components.map(c => c.id));
for (const node of partNodes) {
  const meta = byId.get(node.name);
  if (!meta || !componentIds.has(meta.component)) fail(`part ${node.name} has no component in the manifest`);
}

// Generated and source parts.
const blades = manifest.parts.filter(p => p.component === 'turbine.stage-1-blades');
if (blades.length !== 100) fail(`expected 100 stage-1 turbine blades, found ${blades.length}`);
if (new Set(blades.map(b => b.id)).size !== 100) fail('stage-1 blade ids are not unique');
for (const blade of blades) if (blade.type !== 'blade') fail(`${blade.id} is not typed as a blade`);
const fanBlades = manifest.parts.filter(p => p.component === 'fan.blades');
if (fanBlades.length !== 16) fail(`expected 16 fan blades, found ${fanBlades.length}`);

// Surface audit: every source triangle is covered exactly once.
const audit = manifest.audit;
if (!audit) fail('manifest has no audit block');
const assignedArea = manifest.parts.filter(p => !p.generated).reduce((sum, p) => sum + p.area, 0);
if (Math.abs(assignedArea - audit.assignedArea) > 0.01) {
  fail(`part areas sum to ${assignedArea.toFixed(4)}, audit says ${audit.assignedArea}`);
}
if (Math.abs(audit.assignedArea + audit.replacedArea - audit.sourceArea) > 0.01) {
  fail(`surface not conserved: ${audit.sourceArea} source, ${audit.assignedArea} assigned, ${audit.replacedArea} replaced`);
}
const generated = manifest.parts.filter(p => p.generated);
const generatedBlades = generated.filter(p => p.component === 'turbine.stage-1-blades');
const generatedDisc = generated.filter(p => p.component === 'turbine.stage-1-disk');
if (generatedBlades.length !== 100) fail(`expected 100 generated blades, found ${generatedBlades.length}`);
if (generatedDisc.length !== 1) fail(`expected one generated disc, found ${generatedDisc.length}`);
for (const part of generated) {
  if (part.component !== 'turbine.stage-1-blades' && part.component !== 'turbine.stage-1-disk'
    && part.component !== 'turbine.hero-blade') fail(`unexpected generated part ${part.id}`);
}

// Detailed close-up blade: present, complete and outside the assembly order.
const hero = manifest.components.find(c => c.id === 'turbine.hero-blade');
if (!hero) fail('hero blade component missing');
if (manifest.assembly.includes('turbine.hero-blade')) fail('hero blade is part of the assembly order');
const heroParts = new Set(manifest.parts.filter(p => p.component === 'turbine.hero-blade').map(p => p.id));
const requiredHero = ['skin-suction', 'skin-pressure', 'tip', 'platform', 'neck', 'root',
  'film-le-1', 'film-le-2', 'film-le-3', 'film-le-4', 'film-ps-1', 'film-ps-2', 'film-ss-1',
  'slot-te', 'passage-1', 'passage-2', 'passage-3', 'pin-fin',
  'coat-base', 'coat-bond', 'coat-tgo', 'coat-ysz'];
for (const suffix of requiredHero) {
  if (!heroParts.has(`turbine.hero-blade.${suffix}`)) fail(`hero blade part missing: ${suffix}`);
}

// The combustor must stay in its axial band after the shell split.
for (const part of manifest.parts.filter(p => p.module === 'combustor')) {
  if (part.axial[0] < -0.6 || part.axial[1] > 0.6) fail(`combustor part ${part.id} spans ${part.axial}`);
}

// Assembly order: steps 1 to 11, step 1 is the blade ring alone.
const orders = new Set(manifest.components.map(c => c.order));
for (let step = 1; step <= 10; step++) if (!orders.has(step)) fail(`assembly step ${step} is empty`);
const first = manifest.components.filter(c => c.order === 1);
if (first.length !== 1 || first[0].id !== 'turbine.stage-1-blades') fail('assembly step 1 is not the blade ring alone');
const sixth = manifest.components.filter(c => c.order === 6);
if (sixth.some(c => c.module !== 'combustor')) fail('assembly step 6 contains a non-combustor component');
const third = manifest.components.filter(c => c.order === 3).map(c => c.id);
if (third.includes('turbine.band') || third.includes('turbine.inner-cone')) {
  fail('assembly step 3 still contains the turbine band or inner cone');
}
const seventh = manifest.components.filter(c => c.order === 7).map(c => c.id);
for (const id of ['turbine.band', 'turbine.inner-cone']) {
  if (!seventh.includes(id)) fail(`${id} is not in assembly step 7`);
}
const splitParts = ['exhaust.tail-cone', 'turbine.inner-cone', 'core-casing.inner-wall',
  'combustor.inner-shell', 'compressor.inlet-bell', 'fan.inner-shroud'];
for (const id of splitParts) {
  if (!manifest.parts.some(p => p.component === id)) fail(`split shell part missing: ${id}`);
}
for (const id of manifest.assembly) if (!componentIds.has(id)) fail(`assembly references unknown component ${id}`);

// The exhaust bolt ring holds 64 bolts.
const bolts = manifest.components.find(c => c.id === 'exhaust.bolts');
if (!bolts || bolts.partCount !== 64) fail(`exhaust bolt ring has ${bolts ? bolts.partCount : 0} parts`);

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
console.log(`surface ${audit.sourceArea} = assigned ${audit.assignedArea} + replaced ${audit.replacedArea}`);
console.log(`PASS: hierarchy, blades, surface audit, combustor band, assembly steps, bolt ring, index bounds, ${(data.length / 1e6).toFixed(1)} MB`);
