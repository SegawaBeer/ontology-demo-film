"""Split the turbofan GLB into named engine sections and write a compact GLB.

The source mesh is merged by material, so parts have to be recovered from
geometry: split each primitive into connected components, then sort every
component into a section by its axial and radial position.
"""
import sys, json, struct, math, collections

sys.path.insert(0, 'tools')
from glb_pieces import load, pieces_of

X_MIN, X_MAX = -1.92, 2.19
X_FAN, X_COMP_START, X_COMB_START, X_TURB_START, X_EXHAUST = 1.33, 0.30, -0.12, -1.00, -1.00
R_NACELLE, R_SHAFT, R_HUB = 0.56, 0.12, 0.30


BANDS = [
    ('fan', 1.33, 2.40),
    ('compressor', 0.30, 1.33),
    ('combustor', -0.12, 0.30),
    ('turbine', -1.00, -0.12),
    ('exhaust', -2.20, -1.00),
]


def dominant_band(p):
    best, best_len = 'compressor', 0.0
    for name, a, b in BANDS:
        overlap = min(p['x1'], b) - max(p['x0'], a)
        if overlap > best_len:
            best, best_len = name, overlap
    return best


def classify(p):
    """Return (section, layer) for one connected component."""
    cx = (p['x0'] + p['x1']) / 2
    length = p['x1'] - p['x0']
    r0, r1 = p['r0'], p['r1']
    if r1 <= 0.32 and length > 1.0:
        return 'shaft', 'static'
    if r0 >= R_NACELLE:
        return ('fan-cowl' if cx >= 1.2 else 'nacelle'), 'static'
    if length > 1.6:
        return 'core-casing', 'static'
    band = dominant_band(p)
    if band == 'fan':
        return 'fan', ('rotor' if r0 < R_HUB else 'static')
    if band == 'compressor':
        if r0 >= 0.50:
            return 'compressor', 'shell'
        return 'compressor', ('rotor' if r0 < 0.18 else 'static')
    if band == 'turbine':
        if r0 >= 0.55:
            return 'turbine', 'shell'
        return 'turbine', ('rotor' if r0 < 0.20 else 'static')
    if band == 'combustor':
        if r0 >= 0.55:
            return 'combustor', 'shell'
        return 'combustor', 'static'
    return band, 'static'


SECTION_ORDER = ['fan', 'fan-cowl', 'compressor', 'combustor', 'turbine', 'exhaust',
                 'core-casing', 'nacelle', 'shaft']
LAYER_ORDER = ['rotor', 'static', 'shell']


def build(src, out):
    g, bn = load(src)
    ps = pieces_of(g, bn)
    buckets = collections.defaultdict(list)
    for p in ps:
        sec, layer = classify(p)
        buckets[(sec, layer, p['mat'])].append(p)

    sections = collections.defaultdict(lambda: collections.defaultdict(list))
    for (sec, layer, mat), items in buckets.items():
        sections[sec][layer].append((mat, items))

    binparts, views, accessors, meshes, nodes = [], [], [], [], []
    offset = 0

    def add_view(data, target=None):
        nonlocal offset
        pad = (-len(data)) % 4
        data = data + b'\x00' * pad
        views.append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(data) - pad})
        binparts.append(data)
        offset += len(data)
        return len(views) - 1

    root_children = []
    stats = {}
    for sec in SECTION_ORDER:
        if sec not in sections:
            continue
        layer_ids = []
        for layer in LAYER_ORDER:
            if layer not in sections[sec]:
                continue
            prims = []
            tris = 0
            for mat, items in sections[sec][layer]:
                pos, nrm, idx = [], [], []
                for p in items:
                    base = len(pos) // 3
                    srcpos, srcn = p['pos'], p['n']
                    remap = {v: i for i, v in enumerate(p['vs'])}
                    for v in p['vs']:
                        pos.extend(srcpos[v * 3:v * 3 + 3])
                        if srcn:
                            nrm.extend(srcn[v * 3:v * 3 + 3])
                    for tri in p['trisv']:
                        idx.extend((remap[tri[0]] + base, remap[tri[1]] + base, remap[tri[2]] + base))
                    tris += len(p['trisv'])
                pb = struct.pack('<%df' % len(pos), *pos)
                pv = add_view(pb)
                accessors.append({'bufferView': pv, 'componentType': 5126, 'count': len(pos) // 3,
                                  'type': 'VEC3', 'min': [min(pos[i::3]) for i in range(3)],
                                  'max': [max(pos[i::3]) for i in range(3)]})
                pa = len(accessors) - 1
                attrs = {'POSITION': pa}
                if nrm:
                    nb = struct.pack('<%df' % len(nrm), *nrm)
                    nv = add_view(nb)
                    accessors.append({'bufferView': nv, 'componentType': 5126, 'count': len(nrm) // 3, 'type': 'VEC3'})
                    attrs['NORMAL'] = len(accessors) - 1
                ib = struct.pack('<%dI' % len(idx), *idx)
                iv = add_view(ib)
                accessors.append({'bufferView': iv, 'componentType': 5125, 'count': len(idx), 'type': 'SCALAR'})
                prim = {'attributes': attrs, 'indices': len(accessors) - 1, 'mode': 4}
                if mat is not None and mat < len(g.get('materials', [])):
                    prim['material'] = mat
                prims.append(prim)
            meshes.append({'name': f'{sec}-{layer}', 'primitives': prims})
            nodes.append({'name': f'{sec}-{layer}', 'mesh': len(meshes) - 1})
            layer_ids.append(len(nodes) - 1)
            stats[(sec, layer)] = (len(prims), tris)
        nodes.append({'name': sec, 'children': layer_ids})
        root_children.append(len(nodes) - 1)

    nodes.append({'name': 'turbofan', 'children': root_children})
    mats = []
    for m in g.get('materials', []):
        m = dict(m)
        m.pop('extensions', None)
        mats.append(m)
    gltf = {
        'asset': {'version': '2.0', 'generator': 'turbofan section splitter'},
        'scene': 0,
        'scenes': [{'nodes': [len(nodes) - 1]}],
        'nodes': nodes,
        'meshes': meshes,
        'materials': mats,
        'accessors': accessors,
        'bufferViews': views,
        'buffers': [{'byteLength': offset}],
    }
    js = json.dumps(gltf, separators=(',', ':')).encode()
    js += b' ' * ((-len(js)) % 4)
    binb = b''.join(binparts)
    total = 12 + 8 + len(js) + 8 + len(binb)
    with open(out, 'wb') as f:
        f.write(struct.pack('<4sII', b'glTF', 2, total))
        f.write(struct.pack('<I4s', len(js), b'JSON')); f.write(js)
        f.write(struct.pack('<I4s', len(binb), b'BIN\x00')); f.write(binb)

    for key in sorted(stats):
        print(key, 'primitives', stats[key][0], 'tris', stats[key][1])
    print('wrote', out, round(total / 1e6, 2), 'MB')


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
