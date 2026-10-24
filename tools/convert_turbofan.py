"""Convert the source turbofan into a four-level, per-part hierarchy.

Input : the downloaded Sketchfab GLB (read only)
Output: public/models/turbofan.glb          module > component > part nodes
        public/models/turbofan-parts.json   the same hierarchy as data

Run from the project root:
    python3 tools/convert_turbofan.py ~/Downloads/turbine__turbofan_engine__jet_engine.glb
"""
import sys, os, json, math, struct, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from glb_pieces import load, pieces_of
from parts import make_parts
import blade as blade_mod
import rotor_disk
import hero_blade

MODULES = [
    ('fan', '风扇'), ('fan-cowl', '进气罩'), ('compressor', '压气机'),
    ('combustor', '燃烧室'), ('turbine', '涡轮'), ('exhaust', '尾喷管'),
    ('core-casing', '核心机机匣'), ('nacelle', '外涵道机匣'), ('shaft', '主轴'),
]
MODULE_NAME = dict(MODULES)

# Component definitions: id -> (name, assembly order)
COMPONENTS = {
    'fan.blades': ('风扇叶片', 8),
    'fan.blade-tips': ('风扇叶尖封严块', 8),
    'fan.hub': ('风扇轮毂', 8),
    'fan.spinner': ('整流锥', 10),
    'fan.inner-shroud': ('风扇内整流罩', 8),
    'fan-cowl.lip': ('进气唇口', 9),
    'fan-cowl.shell': ('进气罩壳体', 9),
    'fan-cowl.aft': ('进气罩后段', 9),
    'compressor.stage-1': ('压气机第 1 级叶环', 5),
    'compressor.stage-2': ('压气机第 2 级叶环', 5),
    'compressor.stage-3': ('压气机第 3 级叶环', 5),
    'compressor.stage-4': ('压气机第 4 级叶环', 5),
    'compressor.stators': ('压气机静子环', 5),
    'compressor.struts': ('压气机支板', 5),
    'compressor.drum': ('压气机鼓筒', 5),
    'compressor.casing': ('压气机机匣', 5),
    'compressor.inlet-bell': ('压气机前喇叭口', 5),
    'combustor.cans': ('燃烧室火焰筒', 6),
    'combustor.injectors': ('燃烧室喷嘴', 6),
    'combustor.casing': ('燃烧室机匣', 6),
    'combustor.inner-shell': ('燃烧室内壳', 6),
    'turbine.stage-1-blades': ('第一级涡轮叶片', 1),
    'turbine.stage-1-disk': ('第一级涡轮盘', 2),
    'turbine.stage-1-tip-ring': ('第一级叶尖环', 3),
    'turbine.stage-1-outer': ('第一级涡轮外环叶栅', 3),
    'turbine.band': ('涡轮外环带', 7),
    'turbine.stage-2-blades': ('第二级涡轮叶片', 3),
    'turbine.stage-3-blades': ('第三级涡轮叶片', 3),
    'turbine.stage-4-blades': ('第四级涡轮叶片', 3),
    'turbine.stage-5-blades': ('第五级涡轮叶片', 3),
    'turbine.stage-2-hub': ('第二级轮毂', 3),
    'turbine.stage-3-hub': ('第三级轮毂', 3),
    'turbine.stage-4-hub': ('第四级轮毂', 3),
    'turbine.stage-5-hub': ('第五级轮毂', 3),
    'turbine.stage-2-tip-ring': ('第二级叶尖环', 3),
    'turbine.stage-3-tip-ring': ('第三级叶尖环', 3),
    'turbine.stage-4-tip-ring': ('第四级叶尖环', 3),
    'turbine.stage-5-tip-ring': ('第五级叶尖环', 3),
    'turbine.stage-2-outer': ('第二级涡轮外环叶栅', 3),
    'turbine.stage-3-outer': ('第三级涡轮外环叶栅', 3),
    'turbine.stage-4-outer': ('第四级涡轮外环叶栅', 3),
    'turbine.stage-5-outer': ('第五级涡轮外环叶栅', 3),
    'turbine.inner-cone': ('涡轮内锥壳', 7),
    'turbine.hero-blade': ('精细叶片', 99),
    'exhaust.nozzle': ('尾喷口', 10),
    'exhaust.bolts': ('尾喷口螺栓', 10),
    'exhaust.fittings': ('尾喷口附件', 10),
    'exhaust.tail-cone': ('尾锥', 10),
    'core-casing.drum': ('核心机过渡段机匣', 7),
    'core-casing.tiles': ('核心机机匣瓦块', 7),
    'core-casing.struts': ('核心机支板', 7),
    'core-casing.flanges': ('核心机法兰', 7),
    'core-casing.bolts': ('核心机机匣螺栓', 7),
    'core-casing.inner-wall': ('核心机内壁', 7),
    'nacelle.duct': ('外涵道机匣', 9),
    'shaft.main': ('主轴', 4),
}

STAGE_X = [-1.355, -1.445, -1.545, -1.645, -1.755]
STAGE_TOL = 0.07


def stage_of(x):
    best, best_d = None, 1e9
    for i, sx in enumerate(STAGE_X):
        d = abs(x - sx)
        if d < best_d:
            best, best_d = i, d
    return best if best_d <= STAGE_TOL else None


DISPLAY = 'display'


def classify(p):
    """Return (module, component) for one part, or None when unknown."""
    x, r, tris = p['cx'], p['r'], p['tris']
    length = p['x1'] - p['x0']

    if r < 0.31 and length > 1.5:
        return 'shaft', 'shaft.main'

    # Turbine blade stages, tip rings and hubs.
    if -1.82 <= x <= -1.30:
        stage = stage_of(x)
        if stage is None:
            return 'turbine', 'turbine.band'
        n = stage + 1
        if tris <= 8:
            return ('turbine', 'turbine.stage-%d-blades' % n) if r < 0.455 else ('turbine', 'turbine.stage-%d-outer' % n)
        if 0.43 <= r <= 0.49:
            return 'turbine', 'turbine.stage-%d-tip-ring' % n
        if r < 0.40:
            # A drum spanning two stages belongs to the stage its body sits in.
            return 'turbine', 'turbine.stage-%d-hub' % n
        return 'turbine', 'turbine.band'

    # Exhaust: fittings, bolts, nozzle.
    if x < -1.80:
        if r > 0.60 and tris <= 60 and x < -1.91:
            return 'exhaust', 'exhaust.fittings'
        if r > 0.60 and tris <= 400:
            return 'exhaust', 'exhaust.bolts'
        if tris > 600:
            return 'exhaust', 'exhaust.nozzle'
        return 'exhaust', 'exhaust.tail-cone'

    # Fan.
    if x >= 1.35:
        if r >= 0.60:
            if x >= 1.86:
                return 'fan-cowl', 'fan-cowl.lip'
            if x >= 1.44:
                return 'fan-cowl', 'fan-cowl.shell'
            return 'fan-cowl', 'fan-cowl.aft'
        if r < 0.30:
            return 'fan', 'fan.spinner'
        if tris in (432,):
            return 'fan', 'fan.blades'
        if tris == 96:
            return 'fan', 'fan.blade-tips'
        return 'fan', 'fan.hub'

    # Outer casing between fan and compressor.
    if 0.29 <= x < 1.35 and r >= 0.62:
        return 'nacelle', 'nacelle.duct'

    # Compressor: one component per blade ring, plus stator rings and struts.
    if 0.29 <= x < 1.35:
        if p.get('bolts'):
            return 'core-casing', 'core-casing.bolts'
        if r >= 0.60:
            return 'compressor', 'compressor.casing'
        if 0.66 <= x <= 0.76 and 0.45 <= r < 0.60:
            return 'compressor', 'compressor.struts'
        if 0.99 <= x <= 1.13 and r >= 0.44:
            return 'compressor', 'compressor.stage-1'
        if 0.79 <= x <= 0.93 and r >= 0.34:
            return 'compressor', 'compressor.stage-2'
        if 0.52 <= x <= 0.64 and r >= 0.34:
            return 'compressor', 'compressor.stage-3'
        if 0.41 <= x <= 0.51 and r >= 0.34:
            return 'compressor', 'compressor.stage-4'
        if 0.22 <= r <= 0.34:
            return 'compressor', 'compressor.stators'
        return 'compressor', 'compressor.drum'

    # Combustor.
    if -0.12 <= x < 0.29:
        if p.get('bolts'):
            return 'core-casing', 'core-casing.bolts'
        if tris >= 1000 and 0.36 <= r <= 0.63:
            return 'combustor', 'combustor.cans'
        if tris <= 600 and r > 0.50:
            return 'combustor', 'combustor.injectors'
        return 'combustor', 'combustor.casing'

    # Core casing between combustor and turbine.
    if -1.30 <= x < -0.12:
        if r > 0.60:
            return 'core-casing', 'core-casing.struts'
        if tris >= 400:
            return 'core-casing', 'core-casing.drum'
        return 'core-casing', 'core-casing.tiles'
    return None


def compressor_stage(x):
    if x >= 0.98:
        return 1
    if x >= 0.78:
        return 2
    if x >= 0.63:
        return 3
    return 4


def parts_from_pieces(pieces):
    parts = make_parts(pieces)
    # Bolts: the two bolt rings are made of several blocks each. Group them by
    # angle so one bolt is one part.
    for p in parts:
        if 0.10 <= p['cx'] <= 0.25 and 0.48 <= p['r'] <= 0.60 and p['tris'] <= 400:
            p['bolts'] = True
    return parts


def geometry_of(part):
    verts, normals, indices = [], [], []
    has_normals = all(piece.get('n') for piece in part['pieces'])
    for piece in part['pieces']:
        base = len(verts) // 3
        pos, nrm = piece['pos'], piece.get('n')
        remap = {v: i for i, v in enumerate(piece['vs'])}
        for v in piece['vs']:
            verts.extend(pos[v * 3:v * 3 + 3])
            if has_normals:
                normals.extend(nrm[v * 3:v * 3 + 3])
        for tri in piece['trisv']:
            indices.extend((remap[tri[0]] + base, remap[tri[1]] + base, remap[tri[2]] + base))
    if not has_normals:
        normals = []
    return {'verts': verts, 'normals': normals, 'indices': indices,
            'mat': part['mat'], 'tris': len(indices) // 3}


def bbox_of(geom):
    v = geom['verts']
    return (min(v[0::3]), min(v[1::3]), min(v[2::3]), max(v[0::3]), max(v[1::3]), max(v[2::3]))


def signature(geom):
    """Rotation-invariant key: triangle count, material and cylindrical size."""
    v = geom['verts']
    xs, ys, zs = v[0::3], v[1::3], v[2::3]
    radii = [math.hypot(y, z) for y, z in zip(ys, zs)]
    angles = [math.atan2(z, y) for y, z in zip(ys, zs)]
    sa = sum(math.sin(a) for a in angles)
    ca = sum(math.cos(a) for a in angles)
    a0 = math.atan2(sa, ca)
    rel = [((a - a0 + math.pi) % (2 * math.pi)) - math.pi for a in angles]
    return (geom['tris'], geom['mat'],
            round(max(xs) - min(xs), 3), round(min(radii), 3), round(max(radii), 3),
            round(max(rel) - min(rel), 3))



SHELL_CUTS = [-1.45, -1.05, -0.28, 0.28, 1.15]
SHELL_SEGMENTS = [
    ('exhaust', 'exhaust.tail-cone', 11),
    ('turbine', 'turbine.inner-cone', 4),
    ('core-casing', 'core-casing.inner-wall', 8),
    ('combustor', 'combustor.inner-shell', 7),
    ('compressor', 'compressor.inlet-bell', 6),
    ('fan', 'fan.inner-shroud', 9),
]


def flatten(part):
    """One vertex list plus triangle index triples in world coordinates."""
    verts, normals, tris = [], [], []
    has_normals = all(piece.get('n') for piece in part['pieces'])
    for piece in part['pieces']:
        base = len(verts) // 3
        pos, nrm = piece['pos'], piece.get('n')
        remap = {v: i for i, v in enumerate(piece['vs'])}
        for v in piece['vs']:
            verts.extend(pos[v * 3:v * 3 + 3])
            if has_normals:
                normals.extend(nrm[v * 3:v * 3 + 3])
        for tri in piece['trisv']:
            tris.append((remap[tri[0]] + base, remap[tri[1]] + base, remap[tri[2]] + base))
    return verts, normals if has_normals else [], tris


def clip_x(poly, plane, keep_greater):
    """Clip a polygon of (x, y, z, nx, ny, nz) tuples against x = plane."""
    out = []
    n = len(poly)
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        inside_a = a[0] >= plane if keep_greater else a[0] <= plane
        inside_b = b[0] >= plane if keep_greater else b[0] <= plane
        if inside_a:
            out.append(a)
        if inside_a != inside_b:
            t = (plane - a[0]) / (b[0] - a[0])
            out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(6)))
    return out


def segment_geometry(verts, normals, tris, lo, hi, mat):
    """Cut every triangle at the segment planes and keep the part in [lo, hi]."""
    out_v, out_n, out_i = [], [], []
    for tri in tris:
        poly = []
        for v in tri:
            x, y, z = verts[v * 3:v * 3 + 3]
            nx, ny, nz = normals[v * 3:v * 3 + 3] if normals else (0.0, 0.0, 0.0)
            poly.append((x, y, z, nx, ny, nz))
        if lo > -1e8:
            poly = clip_x(poly, lo, True)
        if hi < 1e8:
            poly = clip_x(poly, hi, False)
        if len(poly) < 3:
            continue
        base = len(out_v) // 3
        for (x, y, z, nx, ny, nz) in poly:
            out_v.extend((x, y, z))
            if normals:
                out_n.extend((nx, ny, nz))
        for k in range(1, len(poly) - 1):
            out_i.extend((base, base + k, base + k + 1))
    return {'verts': out_v, 'normals': out_n, 'indices': out_i,
            'mat': mat, 'tris': len(out_i) // 3}


def triangle_area(geom):
    v = geom['verts']
    total = 0.0
    idx = geom['indices']
    for i in range(0, len(idx), 3):
        a, b, c = idx[i] * 3, idx[i + 1] * 3, idx[i + 2] * 3
        ux, uy, uz = v[b] - v[a], v[b + 1] - v[a + 1], v[b + 2] - v[a + 2]
        vx, vy, vz = v[c] - v[a], v[c + 1] - v[a + 1], v[c + 2] - v[a + 2]
        cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        total += 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)
    return total


def pieces_area(pieces):
    total = 0.0
    for pc in pieces:
        pos = pc['pos']
        for tri in pc['trisv']:
            a, b, c = tri[0] * 3, tri[1] * 3, tri[2] * 3
            ux, uy, uz = pos[b] - pos[a], pos[b + 1] - pos[a + 1], pos[b + 2] - pos[a + 2]
            vx, vy, vz = pos[c] - pos[a], pos[c + 1] - pos[a + 1], pos[c + 2] - pos[a + 2]
            cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            total += 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)
    return total


def geometry_stats(geom):
    v = geom['verts']
    xs, ys, zs = v[0::3], v[1::3], v[2::3]
    radii = [math.hypot(y, z) for y, z in zip(ys, zs)]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2,
            min(xs), max(xs), min(radii), max(radii))

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        '~/Downloads/turbine__turbofan_engine__jet_engine.glb')
    out_glb = sys.argv[2] if len(sys.argv) > 2 else 'public/models/turbofan.glb'
    out_json = sys.argv[3] if len(sys.argv) > 3 else 'public/models/turbofan-parts.json'

    g, bn = load(src)
    pieces = pieces_of(g, bn)
    parts = parts_from_pieces(pieces)
    print('connected pieces', len(pieces), '-> parts', len(parts))

    material_names = [m.get('name') for m in g.get('materials', [])]
    shell_parts = [p for p in parts
                   if (p['x1'] - p['x0']) > 1.5 and material_names[p['mat']] == 'plastic-cone-black']
    shell_ids = {id(p) for p in shell_parts}
    print('long shell parts to split', len(shell_parts))

    replaced = set()
    for p in parts:
        if id(p) in shell_ids:
            continue
        module, component = classify(p)
        p['module'], p['component'] = module, component
        if component == 'turbine.stage-1-blades':
            replaced.add(id(p))

    unknown = [p for p in parts if id(p) not in shell_ids and p.get('module') is None]
    print('unclassified parts', len(unknown))
    for p in unknown[:20]:
        print('  x=%.2f r=%.2f tris=%d' % (p['cx'], p['r'], p['tris']))

    # Stage-1 inner blades are regenerated: drop the original plates.
    kept = [p for p in parts if id(p) not in replaced and id(p) not in shell_ids]
    print('stage-1 plates replaced', len(replaced))

    by_component = collections.defaultdict(list)
    for p in kept:
        if p.get('module') is None:
            continue
        by_component[p['component']].append(p)

    # Rotor flags.
    rotor_components = {
        'fan.blades', 'fan.blade-tips', 'fan.hub', 'fan.spinner',
        'compressor.stage-1', 'compressor.stage-2', 'compressor.stage-3', 'compressor.stage-4',
        'compressor.drum', 'shaft.main',
        'turbine.stage-1-blades', 'turbine.stage-2-blades', 'turbine.stage-3-blades',
        'turbine.stage-4-blades', 'turbine.stage-5-blades', 'turbine.stage-1-disk',
        'turbine.stage-1-tip-ring', 'turbine.stage-2-tip-ring', 'turbine.stage-3-tip-ring',
        'turbine.stage-4-tip-ring', 'turbine.stage-5-tip-ring',
        'turbine.stage-2-hub', 'turbine.stage-3-hub', 'turbine.stage-4-hub', 'turbine.stage-5-hub',
    }

    # Build the part list in ring order (theta ascending) per component.
    manifest_parts = []
    nodes = []
    shapes = []
    shape_by_sig = {}
    component_parts = collections.defaultdict(list)

    def centroid(geom):
        b = bbox_of(geom)
        return ((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2)

    def rot_x(theta, v):
        c, s = math.cos(theta), math.sin(theta)
        return (v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c)

    def add_part(pid, name, ptype, component, module, center, axial, radius, rotor, geom,
                 placement=None, piece_count=0, generated=False, extra=None):
        if placement is None:
            sig = signature(geom)
            c = centroid(geom)
            mesh = None
            trans, rot = [0, 0, 0], [0, 0, 0, 1]
            for si, c0 in shape_by_sig.get(sig, []):
                if abs(math.hypot(c0[1], c0[2]) - math.hypot(c[1], c[2])) > 5e-3:
                    continue
                theta = math.atan2(c[2], c[1]) - math.atan2(c0[2], c0[1])
                moved = rot_x(theta, c0)
                if all(abs(moved[i] - c[i]) < 5e-3 for i in range(3)):
                    mesh = si
                    trans = [c[i] - moved[i] for i in range(3)]
                    rot = [math.sin(theta / 2), 0, 0, math.cos(theta / 2)]
                    break
            if mesh is None:
                shapes.append(geom)
                mesh = len(shapes) - 1
                shape_by_sig.setdefault(sig, []).append((mesh, c))
        else:
            mesh = placement['mesh']
            trans, rot = placement['t'], placement['r']
        nodes.append({'name': pid, 'mesh': mesh, 'translation': trans, 'rotation': rot})
        entry = {
            'id': pid, 'name': name, 'type': ptype, 'component': component, 'module': module,
            'center': [round(c, 4) for c in center],
            'axial': [round(axial[0], 4), round(axial[1], 4)],
            'radius': [round(radius[0], 4), round(radius[1], 4)],
            'rotor': rotor,
            'pieceCount': piece_count,
            'triangles': geom['tris'],
            'area': round(triangle_area(geom), 6),
            'generated': generated,
        }
        if extra:
            entry.update(extra)
        manifest_parts.append(entry)
        component_parts[component].append(entry)
        return entry

    for component, items in sorted(by_component.items()):
        items.sort(key=lambda p: p['theta'])
        for i, p in enumerate(items, 1):
            geom = geometry_of(p)
            pid = '%s.%03d' % (component, i)
            add_part(pid, '%s %03d' % (COMPONENTS[component][0], i),
                     'component', component, p['module'],
                     (p['cx'], p['cy'], p['cz']),
                     (p['x0'], p['x1']), (p['r0'], p['r1']),
                     component in rotor_components, geom, piece_count=len(p['pieces']))

    # Regenerated stage-1 blades: one generated shape, 100 placed nodes.
    verts, normals, indices = blade_mod.blade_geometry()
    blade_geom = {'verts': verts, 'normals': normals, 'indices': indices,
                  'mat': 1, 'tris': len(indices) // 3}
    shapes.append(blade_geom)
    blade_shape = len(shapes) - 1
    x_stage = STAGE_X[0]
    r_root = 0.304
    for i in range(100):
        theta = 2 * math.pi * i / 100
        cy, cz = math.cos(theta), math.sin(theta)
        pid = 'turbine.stage-1-blades.%03d' % (i + 1)
        add_part(pid, '第一级涡轮叶片 %03d' % (i + 1), 'blade', 'turbine.stage-1-blades', 'turbine',
                 (x_stage, r_root * cy, r_root * cz), (x_stage - 0.025, x_stage + 0.025),
                 (r_root - 0.026, r_root + 0.146), True, blade_geom,
                 {'mesh': blade_shape, 't': [x_stage, r_root * cy, r_root * cz],
                  'r': [math.sin(theta / 2), 0, 0, math.cos(theta / 2)]},
                 piece_count=0, generated=True)

    # Generated first-stage rotor disc, placed under the blade roots.
    dv, dn, di = rotor_disk.disc_geometry()
    disk_geom = {'verts': dv, 'normals': dn, 'indices': di, 'mat': 1, 'tris': len(di) // 3}
    shapes.append(disk_geom)
    disk_shape = len(shapes) - 1
    add_part('turbine.stage-1-disk.001', '第一级涡轮盘 001', 'disk', 'turbine.stage-1-disk', 'turbine',
             (x_stage, 0, 0), (x_stage - 0.015, x_stage + 0.015), (0.170, 0.302), True, disk_geom,
             {'mesh': disk_shape, 't': [x_stage, 0, 0], 'r': [0, 0, 0, 1]},
             piece_count=0, generated=True)

    # Detailed blade for close-up shots: hidden by default, outside the assembly order.
    for hp in hero_blade.build():
        hv = hp['verts']
        hvx, hvy, hvz = hv[0::3], hv[1::3], hv[2::3]
        off = hp['offset']
        radii = [math.hypot(y + off[1], z + off[2]) for y, z in zip(hvy, hvz)]
        geom = {'verts': hv, 'normals': hp['normals'], 'indices': hp['indices'],
                'mat': 1, 'tris': hp['tris']}
        shapes.append(geom)
        mesh_index = len(shapes) - 1
        add_part('turbine.hero-blade.%s' % hp['id'], hp['name'], hp['type'],
                 'turbine.hero-blade', 'turbine',
                 ((min(hvx) + max(hvx)) / 2 + off[0], (min(hvy) + max(hvy)) / 2 + off[1],
                  (min(hvz) + max(hvz)) / 2 + off[2]),
                 (min(hvx) + off[0], max(hvx) + off[0]), (min(radii), max(radii)),
                 False, geom,
                 {'mesh': mesh_index, 't': off, 'r': [0, 0, 0, 1]},
                 piece_count=0, generated=True,
                 extra={'hero': True, 'cut': hp.get('cut'), 'coat': hp.get('coat')})

    # The long black shell is cut into one part per module.
    for part in shell_parts:
        verts, normals, tris = flatten(part)
        for idx, (module, component, _order) in enumerate(SHELL_SEGMENTS):
            lo = SHELL_CUTS[idx - 1] if idx > 0 else -1e9
            hi = SHELL_CUTS[idx] if idx < len(SHELL_CUTS) else 1e9
            geom = segment_geometry(verts, normals, tris, lo, hi, part['mat'])
            if not geom['tris']:
                continue
            cx, cy, cz, x0, x1, r0, r1 = geometry_stats(geom)
            add_part('%s.001' % component, '%s 001' % COMPONENTS[component][0],
                     component.split('.')[1], component, module,
                     (cx, cy, cz), (x0, x1), (r0, r1),
                     component in rotor_components, geom,
                     piece_count=0, generated=False)

    # Manifest.
    modules = []
    components = []
    for module_id, module_name in MODULES:
        comp_ids = sorted({p['component'] for p in manifest_parts if p['module'] == module_id})
        module = {'id': module_id, 'name': module_name, 'components': comp_ids,
                  'partCount': sum(len(component_parts[c]) for c in comp_ids)}
        modules.append(module)
        for cid in comp_ids:
            name, order = COMPONENTS[cid]
            components.append({'id': cid, 'name': name, 'module': module_id,
                               'partCount': len(component_parts[cid]), 'order': order,
                               'parts': [p['id'] for p in component_parts[cid]]})
    components.sort(key=lambda c: (c['order'], c['id']))
    for c in components:
        c['hero'] = c['id'] == 'turbine.hero-blade'
    manifest = {'modules': modules, 'components': components, 'parts': manifest_parts,
                'assembly': [c['id'] for c in components if c['id'] != 'turbine.hero-blade'],
                'audit': {
                    'sourcePieces': len(pieces),
                    'sourceTriangles': sum(p['tris'] for p in parts),
                    'replacedTriangles': sum(p['tris'] for p in parts if id(p) in replaced),
                    'sourceArea': round(pieces_area(pieces), 4),
                    'replacedArea': round(sum(pieces_area(p['pieces']) for p in parts if id(p) in replaced), 4),
                    'assignedArea': round(sum(p['area'] for p in manifest_parts if not p['generated']), 4),
                    'generatedArea': round(sum(p['area'] for p in manifest_parts if p['generated']), 4),
                    'parts': len(manifest_parts),
                    'generatedBlades': 100,
                }}

    write_glb(out_glb, g, shapes, nodes, modules, components)
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    total = sum(len(component_parts[c]) for c in component_parts)
    print('parts in manifest', total, 'components', len(components))
    print('wrote', out_glb, os.path.getsize(out_glb) / 1e6, 'MB')
    print('wrote', out_json, os.path.getsize(out_json) / 1e3, 'kB')
    for m in modules:
        print('  %-12s %-6s parts=%d components=%d' % (m['id'], m['name'], m['partCount'], len(m['components'])))


def write_glb(path, source, shapes, part_nodes, modules, components):
    bin_parts, views, accessors, meshes, nodes = [], [], [], [], []
    offset = 0

    def add_view(data):
        nonlocal offset
        pad = (-len(data)) % 4
        data = data + b'\x00' * pad
        views.append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(data) - pad})
        bin_parts.append(data)
        offset += len(data)
        return len(views) - 1

    for shape in shapes:
        v = shape['verts']
        pv = add_view(struct.pack('<%df' % len(v), *v))
        accessors.append({'bufferView': pv, 'componentType': 5126, 'count': len(v) // 3,
                          'type': 'VEC3', 'min': [min(v[i::3]) for i in range(3)],
                          'max': [max(v[i::3]) for i in range(3)]})
        attrs = {'POSITION': len(accessors) - 1}
        if shape['normals']:
            nv = add_view(struct.pack('<%df' % len(shape['normals']), *shape['normals']))
            accessors.append({'bufferView': nv, 'componentType': 5126,
                              'count': len(shape['normals']) // 3, 'type': 'VEC3'})
            attrs['NORMAL'] = len(accessors) - 1
        iv = add_view(struct.pack('<%dI' % len(shape['indices']), *shape['indices']))
        accessors.append({'bufferView': iv, 'componentType': 5125,
                          'count': len(shape['indices']), 'type': 'SCALAR'})
        meshes.append({'name': 'shape-%d' % len(meshes),
                       'primitives': [{'attributes': attrs, 'indices': len(accessors) - 1,
                                       'mode': 4, 'material': shape['mat']}]})

    # Node tree: root > module > component > part.
    root = {'name': 'turbofan', 'children': []}
    nodes.append(root)
    module_nodes = {}
    for module_id, module_name in MODULES:
        mn = {'name': module_id, 'children': []}
        nodes.append(mn)
        root['children'].append(len(nodes) - 1)
        module_nodes[module_id] = len(nodes) - 1
    component_nodes = {}
    for comp in components:
        cn = {'name': comp['id'], 'children': []}
        nodes.append(cn)
        nodes[module_nodes[comp['module']]]['children'].append(len(nodes) - 1)
        component_nodes[comp['id']] = len(nodes) - 1
    for pn in part_nodes:
        node = {'name': pn['name'], 'mesh': pn['mesh']}
        if pn['translation'] != [0, 0, 0]:
            node['translation'] = pn['translation']
        if pn['rotation'] != [0, 0, 0, 1]:
            node['rotation'] = pn['rotation']
        nodes.append(node)
        component = pn['name'].rsplit('.', 1)[0]
        nodes[component_nodes[component]]['children'].append(len(nodes) - 1)

    gltf = {
        'asset': {'version': '2.0', 'generator': 'turbofan part splitter'},
        'scene': 0, 'scenes': [{'nodes': [0]}],
        'nodes': nodes, 'meshes': meshes,
        'materials': strip_materials(source),
        'accessors': accessors, 'bufferViews': views,
        'buffers': [{'byteLength': offset}],
    }
    js = json.dumps(gltf, separators=(',', ':')).encode()
    js += b' ' * ((-len(js)) % 4)
    binary = b''.join(bin_parts)
    total = 12 + 8 + len(js) + 8 + len(binary)
    with open(path, 'wb') as f:
        f.write(struct.pack('<4sII', b'glTF', 2, total))
        f.write(struct.pack('<I4s', len(js), b'JSON')); f.write(js)
        f.write(struct.pack('<I4s', len(binary), b'BIN\x00')); f.write(binary)


def strip_materials(source):
    out = []
    for m in source.get('materials', []):
        m = dict(m)
        m.pop('extensions', None)
        out.append(m)
    return out


if __name__ == '__main__':
    main()
