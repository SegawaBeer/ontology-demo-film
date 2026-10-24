"""Generate one first-stage turbine blade.

Local frame: origin at the centre of the fir-tree root, +Y radial outward,
+X axial, +Z tangential. Overall height 0.176: root -0.030..0.008,
platform 0.008..0.020, aerofoil 0.020..0.146. The root sits inside the hub.
"""
import math

ROOT_R = 0.304          # radius of the root centre in the engine
SPAN = 0.146            # aerofoil tip radius, local y
PITCH = 2 * math.pi * ROOT_R / 100   # tangential pitch at the root, ~0.0191
CHORD = 0.050
STAGGER = math.radians(35)


def section(chord, thick, camber, twist, n=16):
    """Cambered section, returned as (x, z) around the outline."""
    upper, lower = [], []
    for i in range(n + 1):
        t = i / n
        x = 0.5 * (1 - math.cos(math.pi * t))
        yt = 5 * thick * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x * x
                          + 0.2843 * x ** 3 - 0.1015 * x ** 4)
        yc = camber * chord * math.sin(math.pi * x)
        upper.append((x * chord, yc + yt * chord))
        lower.append((x * chord, yc - yt * chord))
    outline = upper + list(reversed(lower[1:-1]))
    cs, sn = math.cos(twist), math.sin(twist)
    return [((x - chord / 2) * cs - z * sn, (x - chord / 2) * sn + z * cs) for (x, z) in outline]


def add_box(verts, faces, cx, cy, cz, sx, sy, sz, twist=0.0):
    base = len(verts) // 3
    cs, sn = math.cos(twist), math.sin(twist)
    for iy in (-1, 1):
        for ix in (-1, 1):
            for iz in (-1, 1):
                x, z = ix * sx / 2, iz * sz / 2
                verts.extend((cx + x * cs - z * sn, cy + iy * sy / 2, cz + x * sn + z * cs))
    # index order: (iy,ix,iz) -> 0..7
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for a, b, c, d in quads:
        faces.extend((base + a, base + b, base + c, base + a, base + c, base + d))


def blade_geometry(sections=6, profile=16):
    verts, faces = [], []

    loops = []
    for s in range(sections):
        t = s / (sections - 1)
        y = 0.020 + t * (SPAN - 0.020)
        chord = CHORD - 0.014 * t
        thick = 0.26 - 0.14 * t
        camber = 0.20 - 0.11 * t
        twist = STAGGER - math.radians(14) * t
        outline = section(chord, thick, camber, twist, profile)
        base = len(verts) // 3
        for (x, z) in outline:
            verts.extend((x, y, z))
        loops.append((outline, base))

    n = len(loops[0][0])
    for a in range(len(loops) - 1):
        b0 = loops[a][1]
        b1 = loops[a + 1][1]
        for i in range(n):
            j = (i + 1) % n
            faces.extend((b0 + i, b0 + j, b1 + j, b0 + i, b1 + j, b1 + i))

    for loop_index, (outline, base) in enumerate((loops[0], loops[-1])):
        cy = 0.020 if loop_index == 0 else SPAN
        cx = sum(p[0] for p in outline) / n
        cz = sum(p[1] for p in outline) / n
        verts.extend((cx, cy, cz))
        centre = len(verts) // 3 - 1
        for i in range(n):
            j = (i + 1) % n
            if loop_index == 0:
                faces.extend((base + j, base + i, centre))
            else:
                faces.extend((base + i, base + j, centre))

    # Platform: parallelogram across the pitch, aligned with the stagger.
    axial = CHORD * math.cos(STAGGER) + 0.020
    add_box(verts, faces, 0, 0.014, 0, axial, 0.012, PITCH, STAGGER)

    # Fir-tree root: three lobes, each narrower than the one above.
    y = 0.008
    for lobe, (width, height) in enumerate(((PITCH * 0.92, 0.010),
                                            (PITCH * 0.74, 0.010),
                                            (PITCH * 0.56, 0.010))):
        add_box(verts, faces, 0, y - height / 2, 0, axial * 0.72, height, width, STAGGER)
        y -= height
    add_box(verts, faces, 0, y - 0.002, 0, axial * 0.4, 0.004, PITCH * 0.36, STAGGER)

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

    return verts, normals, faces


if __name__ == '__main__':
    v, n, f = blade_geometry()
    xs, ys, zs = v[0::3], v[1::3], v[2::3]
    print('vertices', len(v) // 3, 'triangles', len(f) // 3)
    print('x %.3f..%.3f  y %.3f..%.3f  z %.3f..%.3f' % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
    print('pitch %.4f  chord %.3f  axial width %.4f' % (PITCH, CHORD, CHORD * math.cos(STAGGER)))
