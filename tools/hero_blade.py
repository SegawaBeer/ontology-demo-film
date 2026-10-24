"""Generate the detailed turbine blade used for close-up shots.

Local frame matches the ring blades: origin at the fir-tree root centre, +Y
radial, +X chord, +Z tangential. The aerofoil spans y 0.018..0.146 with chord
0.105 (height/chord 1.22), stagger 35 deg and 15 deg of twist.

Every part is returned as its own geometry so the runtime can colour, hide or
move it by id. Flags:
    cut   'pressure'  -> moves aside with the cutaway parameter
    coat  index       -> separates with the coating parameter
    hidden            -> not shown until the runtime asks for it
"""
import math

SPAN = 0.146
ROOT_TOP = 0.018
CHORD = 0.105
STAGGER = math.radians(35)
TWIST = math.radians(18)
SECTIONS = 48
PROFILE = 64
HOLE_R = 0.0028


def camber(t):
    return 0.11 * math.sin(math.pi * t ** 0.9)


def thickness(t, ratio):
    return 5 * ratio * (0.2969 * math.sqrt(max(t, 1e-6)) - 0.126 * t - 0.3516 * t * t
                        + 0.2843 * t ** 3 - 0.1036 * t ** 4)


def section_point(t, thick, twist, side):
    """side +1 suction, -1 pressure; returns x, z after stagger and twist."""
    zc = camber(t) * CHORD
    yt = thickness(t, thick) * CHORD
    z = zc + side * yt
    x = t * CHORD - CHORD / 2
    cs, sn = math.cos(twist), math.sin(twist)
    return x * cs - z * sn, x * sn + z * cs


def section_twist(s):
    return STAGGER - TWIST * s


def section_thickness(s):
    return 0.14 - 0.09 * s


def frame(s, t, side, twist):
    """Position and outward normal at one surface point."""
    x, z = section_point(t, section_thickness(s), twist, side)
    d = 1e-3
    x2, z2 = section_point(min(1, t + d), section_thickness(s), twist + (section_twist(min(1, s + d / TWIST)) - twist), side)
    return (x, ROOT_TOP + s * (SPAN - ROOT_TOP), z), (x2, ROOT_TOP + min(1, s + d) * (SPAN - ROOT_TOP), z2)


def rotate_y(x, z, angle):
    return x * math.cos(angle) - z * math.sin(angle), x * math.sin(angle) + z * math.cos(angle)


class Builder:
    def __init__(self):
        self.parts = []

    def part(self, pid, name, ptype, verts, faces, offset=(0, 0, 0), **flags):
        normals = smooth_normals(verts, faces)
        entry = {'id': pid, 'name': name, 'type': ptype,
                 'verts': verts, 'normals': normals, 'indices': faces,
                 'offset': list(offset), 'tris': len(faces) // 3}
        entry.update(flags)
        self.parts.append(entry)


def smooth_normals(verts, faces):
    normals = [0.0] * len(verts)
    for i in range(0, len(faces), 3):
        a, b, c = faces[i] * 3, faces[i + 1] * 3, faces[i + 2] * 3
        ux, uy, uz = verts[b] - verts[a], verts[b + 1] - verts[a + 1], verts[b + 2] - verts[a + 2]
        vx, vy, vz = verts[c] - verts[a], verts[c + 1] - verts[a + 1], verts[c + 2] - verts[a + 2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        for k in (a, b, c):
            normals[k] += nx; normals[k + 1] += ny; normals[k + 2] += nz
    for i in range(0, len(normals), 3):
        length = math.sqrt(normals[i] ** 2 + normals[i + 1] ** 2 + normals[i + 2] ** 2) or 1.0
        normals[i] /= length; normals[i + 1] /= length; normals[i + 2] /= length
    return normals


def add_box(verts, faces, cx, cy, cz, sx, sy, sz, angle=0.0):
    base = len(verts) // 3
    cs, sn = math.cos(angle), math.sin(angle)
    for iy in (-1, 1):
        for ix in (-1, 1):
            for iz in (-1, 1):
                x, z = ix * sx / 2, iz * sz / 2
                verts.extend((cx + x * cs - z * sn, cy + iy * sy / 2, cz + x * sn + z * cs))
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for a, b, c, d in quads:
        faces.extend((base + a, base + b, base + c, base + a, base + c, base + d))


def add_cylinder(verts, faces, cx, cy, cz, radius, length, axis='z', segments=12):
    base = len(verts) // 3
    for end in (-1, 1):
        for i in range(segments):
            a = 2 * math.pi * i / segments
            u, v = radius * math.cos(a), radius * math.sin(a)
            if axis == 'z':
                verts.extend((cx + u, cy + v, cz + end * length / 2))
            elif axis == 'y':
                verts.extend((cx + u, cy + end * length / 2, cz + v))
            else:
                verts.extend((cx + end * length / 2, cy + u, cz + v))
    for i in range(segments):
        j = (i + 1) % segments
        faces.extend((base + i, base + j, base + segments + j, base + i, base + segments + j, base + segments + i))


def add_torus(verts, faces, cx, cy, cz, radius, tube, normal, major=14, minor=6):
    """Ring around the hole axis given by the surface normal."""
    base = len(verts) // 3
    nx, ny, nz = normal
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    nx, ny, nz = nx / length, ny / length, nz / length
    # any two vectors perpendicular to the normal
    tx, ty, tz = (0, 1, 0) if abs(ny) < 0.9 else (1, 0, 0)
    ux, uy, uz = ty * nz - tz * ny, tz * nx - tx * nz, tx * ny - ty * nx
    ul = math.sqrt(ux * ux + uy * uy + uz * uz)
    ux, uy, uz = ux / ul, uy / ul, uz / ul
    vx, vy, vz = ny * uz - nz * uy, nz * ux - nx * uz, nx * uy - ny * ux
    for i in range(major):
        a = 2 * math.pi * i / major
        dx, dy, dz = (ux * math.cos(a) + vx * math.sin(a), uy * math.cos(a) + vy * math.sin(a),
                      uz * math.cos(a) + vz * math.sin(a))
        for j in range(minor):
            b = 2 * math.pi * j / minor
            r = radius + tube * math.cos(b)
            verts.extend((cx + dx * r + nx * tube * math.sin(b) * .6,
                          cy + dy * r + ny * tube * math.sin(b) * .6,
                          cz + dz * r + nz * tube * math.sin(b) * .6))
    for i in range(major):
        for j in range(minor):
            a = base + i * minor + j
            b = base + i * minor + (j + 1) % minor
            c = base + ((i + 1) % major) * minor + (j + 1) % minor
            d = base + ((i + 1) % major) * minor + j
            faces.extend((a, b, c, a, c, d))


def hole_centres(side, holes):
    out = []
    for (s, t) in holes:
        twist = section_twist(s)
        x, z = section_point(t, section_thickness(s), twist, side)
        out.append((x, ROOT_TOP + s * (SPAN - ROOT_TOP), z))
    return out


def build_wall(side, holes):
    """One side of the aerofoil with circular film holes cut out."""
    verts, faces = [], []
    grid = []
    for si in range(SECTIONS + 1):
        s = si / SECTIONS
        twist = section_twist(s)
        y = ROOT_TOP + s * (SPAN - ROOT_TOP)
        row = []
        for pi in range(PROFILE + 1):
            t = pi / PROFILE
            x, z = section_point(t, section_thickness(s), twist, side)
            row.append(len(verts) // 3)
            verts.extend((x, y, z))
        grid.append(row)
    centres = hole_centres(side, holes)
    lim = (HOLE_R * 1.02) ** 2

    for si in range(SECTIONS):
        for pi in range(PROFILE):
            a, b = grid[si][pi], grid[si][pi + 1]
            c, d = grid[si + 1][pi + 1], grid[si + 1][pi]
            idx = (a, b, c, d)
            px = sum(verts[i * 3] for i in idx) / 4
            py = sum(verts[i * 3 + 1] for i in idx) / 4
            pz = sum(verts[i * 3 + 2] for i in idx) / 4
            if any((px - cx) ** 2 + (py - cy) ** 2 + (pz - cz) ** 2 < lim for (cx, cy, cz) in centres):
                continue
            faces.extend((a, b, c, a, c, d))
    return verts, faces


def add_tube(verts, faces, p, normal, radius, length, segments=12):
    """Open tube through the wall, centred on the surface point."""
    nx, ny, nz = normal
    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
    nx, ny, nz = nx / ln, ny / ln, nz / ln
    tx, ty, tz = (0, 1, 0) if abs(ny) < 0.9 else (1, 0, 0)
    ux, uy, uz = ty * nz - tz * ny, tz * nx - tx * nz, tx * ny - ty * nx
    ul = math.sqrt(ux * ux + uy * uy + uz * uz)
    ux, uy, uz = ux / ul, uy / ul, uz / ul
    vx, vy, vz = ny * uz - nz * uy, nz * ux - nx * uz, nx * uy - ny * ux
    base = len(verts) // 3
    for end in (-0.006, length):
        for i in range(segments):
            a = 2 * math.pi * i / segments
            dx, dy, dz = (ux * math.cos(a) + vx * math.sin(a), uy * math.cos(a) + vy * math.sin(a),
                          uz * math.cos(a) + vz * math.sin(a))
            verts.extend((p[0] + dx * radius + nx * end, p[1] + dy * radius + ny * end,
                          p[2] + dz * radius + nz * end))
    for i in range(segments):
        j = (i + 1) % segments
        faces.extend((base + i, base + j, base + segments + j, base + i, base + segments + j, base + segments + i))


def hole_frames(side, holes):
    out = []
    for (s, t) in holes:
        twist = section_twist(s)
        x, z = section_point(t, section_thickness(s), twist, side)
        p = (x, ROOT_TOP + s * (SPAN - ROOT_TOP), z)
        ds = min(1, s + 0.002)
        x1, z1 = section_point(t, section_thickness(ds), section_twist(ds), side)
        p1 = (x1, ROOT_TOP + ds * (SPAN - ROOT_TOP), z1)
        dt = min(1, t + 0.002)
        x2, z2 = section_point(dt, section_thickness(s), twist, side)
        p2 = (x2, p[1], z2)
        u = (p1[0] - p[0], p1[1] - p[1], p1[2] - p[2])
        v = (p2[0] - p[0], p2[1] - p[1], p2[2] - p[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        if side < 0:
            n = (-n[0], -n[1], -n[2])
        out.append((p, n))
    return out


ROW_DEFS = [
    ('film-le-1', '前缘喷淋孔 1', 1, [(0.15, 0.05), (0.30, 0.05), (0.45, 0.05), (0.60, 0.05)]),
    ('film-le-2', '前缘喷淋孔 2', 1, [(0.22, 0.085), (0.37, 0.085), (0.52, 0.085), (0.67, 0.085)]),
    ('film-le-3', '前缘喷淋孔 3', -1, [(0.18, 0.055), (0.33, 0.055), (0.48, 0.055), (0.63, 0.055)]),
    ('film-le-4', '前缘喷淋孔 4', -1, [(0.25, 0.09), (0.40, 0.09), (0.55, 0.09), (0.70, 0.09)]),
    ('film-ps-1', '压力面气膜孔 1', -1, [(0.20, 0.36), (0.32, 0.36), (0.44, 0.36), (0.56, 0.36), (0.68, 0.36)]),
    ('film-ps-2', '压力面气膜孔 2', -1, [(0.22, 0.58), (0.34, 0.58), (0.46, 0.58), (0.58, 0.58), (0.70, 0.58)]),
    ('film-ss-1', '吸力面气膜孔 1', 1, [(0.22, 0.50), (0.34, 0.50), (0.46, 0.50), (0.58, 0.50), (0.70, 0.50)]),
]

TE_SLOTS = [(0.14 + i * 0.105, 0.965) for i in range(8)]


def build():
    b = Builder()

    for side, pid, name in ((1, 'skin-suction', '叶身吸力面'), (-1, 'skin-pressure', '叶身压力面')):
        holes = [(s, t) for (_id, _n, sd, hs) in ROW_DEFS if sd == side for (s, t) in hs]
        verts, faces = build_wall(side, holes + [(s, t) for (s, t) in TE_SLOTS])
        b.part(pid, name, 'blade-wall', verts, faces,
               cut='pressure' if side < 0 else None)

    # Film rows: rim and a short tube through the wall.
    for rid, name, side, spots in ROW_DEFS:
        verts, faces = [], []
        for (p, n) in hole_frames(side, spots):
            add_torus(verts, faces, p[0], p[1], p[2], HOLE_R * 1.25, HOLE_R * .32, n)
            add_tube(verts, faces, p, n, HOLE_R * .82, .0008, segments=10)
        b.part(rid, name, 'film-row', verts, faces,
               side='pressure' if side < 0 else 'suction',
               cut='pressure' if side < 0 else None)

    # Trailing-edge slots.
    verts, faces = [], []
    for (s, t) in TE_SLOTS:
        twist = section_twist(s)
        x, z = section_point(t, section_thickness(s), twist, 1)
        add_box(verts, faces, x, ROOT_TOP + s * (SPAN - ROOT_TOP), z, .0025, .005, .0075, twist)
    b.part('slot-te', '尾缘劈缝', 'slot-row', verts, faces, cut='pressure')

    # Tip: a rim band around the outline with a recessed floor.
    twist = section_twist(1.0)
    outline = []
    for side in (1, -1):
        pts = [section_point(i / PROFILE, section_thickness(1), twist, side) for i in range(PROFILE)]
        outline.extend(pts if side > 0 else list(reversed(pts)))
    verts, faces = [], []
    depth = .008
    n = len(outline)
    top = []
    for (x, z) in outline:
        top.append(len(verts) // 3)
        verts.extend((x, SPAN, z))
    low = []
    for (x, z) in outline:
        low.append(len(verts) // 3)
        verts.extend((x, SPAN - depth, z))
    for i in range(n):
        j = (i + 1) % n
        faces.extend((top[i], top[j], low[j], top[i], low[j], low[i]))
    cx = sum(p[0] for p in outline) / n
    cz = sum(p[1] for p in outline) / n
    floor = [len(verts) // 3]
    verts.extend((cx, SPAN - depth, cz))
    for i in range(n):
        j = (i + 1) % n
        faces.extend((low[i], low[j], floor[0]))
    b.part('tip', '叶尖围边与凹槽', 'blade-tip', verts, faces)

    # Platform, neck and fir-tree root.
    verts, faces = [], []
    add_box(verts, faces, 0, .012, 0, CHORD * math.cos(STAGGER) + .012, .012, .032, STAGGER)
    b.part('platform', '缘板', 'platform', verts, faces)
    verts, faces = [], []
    add_box(verts, faces, 0, .002, 0, CHORD * math.cos(STAGGER) * .55, .010, .022, STAGGER)
    b.part('neck', '叶根颈部', 'neck', verts, faces)
    verts, faces = [], []
    y = 0.0
    for width, height in ((.026, .010), (.021, .010), (.016, .010)):
        add_box(verts, faces, 0, y - height / 2, 0, CHORD * .32, height, width, STAGGER)
        y -= height
    add_box(verts, faces, 0, y - .003, 0, CHORD * .18, .006, .010, STAGGER)
    b.part('root', '枞树形叶根', 'root', verts, faces)

    # Three serpentine passages with angled ribs, swept inside the aerofoil.
    passage_zones = [(0.10, 0.30), (0.32, 0.56), (0.58, 0.86)]
    for index, (t0, t1) in enumerate(passage_zones, 1):
        verts, faces = [], []
        stations = [ROOT_TOP + .012 + (SPAN - ROOT_TOP - .024) * (k / 8) for k in range(9)]
        rings = []
        for k, y in enumerate(stations):
            s_frac = (y - ROOT_TOP) / (SPAN - ROOT_TOP)
            twist = section_twist(s_frac)
            thick = thickness((t0 + t1) / 2, section_thickness(s_frac)) * CHORD
            half = max(0.0022, thick * 0.42)
            x0, z0 = section_point(t0, 0, twist, 1)
            x1, z1 = section_point(t1, 0, twist, 1)
            px, pz = -math.sin(twist), math.cos(twist)
            pts = []
            for (x, z, sign) in ((x0, z0, -1), (x1, z1, -1), (x1, z1, 1), (x0, z0, 1)):
                pts.append(len(verts) // 3)
                verts.extend((x + px * half * sign, y, z + pz * half * sign))
            rings.append(pts)
        for k in range(len(rings) - 1):
            for i in range(4):
                j = (i + 1) % 4
                ra, rb = rings[k][i], rings[k][j]
                rc, rd = rings[k + 1][j], rings[k + 1][i]
                faces.extend((ra, rb, rc, ra, rc, rd))
        for k in (0, len(rings) - 1):
            r = rings[k]
            faces.extend((r[0], r[2], r[1], r[0], r[3], r[2]))
        for station in (0.18, 0.4, 0.62, 0.84):
            y = ROOT_TOP + .012 + (SPAN - ROOT_TOP - .024) * station
            s_frac = (y - ROOT_TOP) / (SPAN - ROOT_TOP)
            twist = section_twist(s_frac)
            thick = thickness((t0 + t1) / 2, section_thickness(s_frac)) * CHORD
            half = max(0.0022, thick * 0.42)
            x0, z0 = section_point(t0, 0, twist, 1)
            x1, z1 = section_point(t1, 0, twist, 1)
            add_box(verts, faces, (x0 + x1) / 2, y, (z0 + z1) / 2, (x1 - x0) * .8, .0026, half * 1.7, twist)
        b.part('passage-%d' % index, '冷却通道 %d' % index, 'passage', verts, faces)

    # Pin fins near the trailing edge.
    verts, faces = [], []
    for s in [0.15 + i * 0.09 for i in range(9)]:
        for t in (0.88, 0.905, 0.93):
            x, _ = section_point(t, 0, section_twist(s), 1)
            add_cylinder(verts, faces, x, ROOT_TOP + s * (SPAN - ROOT_TOP), 0, .0022, .014, axis='z', segments=8)
    b.part('pin-fin', '尾缘针肋', 'pin-fin', verts, faces)

    # Coating sample: four curved plates beside the blade.
    thicknesses = [.010, .0015, .0008, .006]
    names = [('coat-base', '镍基高温合金基体'), ('coat-bond', '金属粘结层'),
             ('coat-tgo', '热生长氧化层'), ('coat-ysz', '陶瓷热障层')]
    z = .075
    stack = [.075, .075 + .005 + .00075, .075 + .0065 + .0004, .075 + .0073 + .003]
    for index, (((pid, name), thick)) in enumerate(zip(names, thicknesses)):
        verts, faces = [], []
        cols, rows = 12, 8
        width, height = .048, .036
        for iy in range(rows + 1):
            for ix in range(cols + 1):
                u = ix / cols - .5
                v = iy / rows
                x = u * width
                y = .06 + v * height
                curve = .004 * math.cos(u * math.pi)
                verts.extend((x, y, curve))
                verts.extend((x, y, curve + thick))
        for iy in range(rows):
            for ix in range(cols):
                qa = iy * (cols + 1) + ix
                qb = qa + 1
                qc = qa + cols + 2
                qd = qa + cols + 1
                faces.extend((qa, qb, qc, qa, qc, qd))
                off = (cols + 1) * (rows + 1)
                faces.extend((qa + off, qc + off, qb + off, qa + off, qd + off, qc + off))
        b.part(pid, name, 'coating', verts, faces, offset=[0, 0, stack[index]], coat=index, hidden=True)

    return b.parts


if __name__ == '__main__':
    parts = build()
    total = sum(p['tris'] for p in parts)
    print('parts', len(parts), 'triangles', total)
    for p in parts:
        print('  %-14s %-12s tris %6d' % (p['id'], p['type'], p['tris']))
