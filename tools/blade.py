"""Generate one turbine blade as a closed, twisted airfoil with a root platform.

Local frame: +Y is radial outward from the root centre, +X is axial, +Z is
tangential. The blade occupies y = 0 .. 0.146 so it fits the original plate ring
(r 0.304 .. 0.450) without touching the disc or the casing.
"""
import math

SPAN = 0.146
ROOT_R = 0.304


def airfoil(chord, thickness, camber, n=12):
    """NACA-4 style cambered section in (x, z); x along chord, z thickness."""
    upper, lower = [], []
    for i in range(n + 1):
        t = i / n
        x = 0.5 * (1 - math.cos(math.pi * t))
        yt = 5 * thickness * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x * x
                             + 0.2843 * x ** 3 - 0.1015 * x ** 4)
        yc = camber * chord * math.sin(math.pi * x)
        upper.append((x * chord, yc + yt * chord))
        lower.append((x * chord, yc - yt * chord))
    return upper, lower


def blade_geometry(sections=6, profile=10):
    """Return (vertices, normals, indices) for one blade."""
    verts, normals, indices = [], [], []

    def add_loop(points, y):
        base = len(verts) // 3
        for (x, z) in points:
            verts.extend((x, y, z))
        return base

    loops = []
    for s in range(sections):
        t = s / (sections - 1)
        y = 0.012 + t * (SPAN - 0.012)
        chord = 0.038 - 0.012 * t
        thick = 0.30 - 0.14 * t          # thickness / chord
        camber = 0.18 - 0.10 * t          # camber / chord
        twist = math.radians(42 - 24 * t)
        upper, lower = airfoil(chord, thick, camber, profile)
        loop = []
        cs, sn = math.cos(twist), math.sin(twist)
        for (x, z) in upper + list(reversed(lower[1:-1])):
            x0 = x - chord / 2
            loop.append((x0 * cs - z * sn, x0 * sn + z * cs))
        loops.append((loop, y, add_loop(loop, y)))

    n = len(loops[0][0])
    for a in range(len(loops) - 1):
        l0, _, b0 = loops[a]
        l1, _, b1 = loops[a + 1]
        for i in range(n):
            j = (i + 1) % n
            indices.extend((b0 + i, b0 + j, b1 + j, b0 + i, b1 + j, b1 + i))

    # Caps: tip and root.
    tip_loop, tip_y, tip_base = loops[-1]
    root_loop, root_y, root_base = loops[0]
    tip_center = (sum(p[0] for p in tip_loop) / n, tip_y, sum(p[1] for p in tip_loop) / n)
    root_center = (sum(p[0] for p in root_loop) / n, root_y, sum(p[1] for p in root_loop) / n)
    verts.extend(tip_center); tip_c = len(verts) // 3 - 1
    verts.extend(root_center); root_c = len(verts) // 3 - 1
    for i in range(n):
        j = (i + 1) % n
        indices.extend((tip_base + i, tip_base + j, tip_c))
        indices.extend((root_base + j, root_base + i, root_c))

    # Root platform and dovetail, a shallow block under the airfoil.
    px, pz = 0.026, 0.015
    py0, py1 = 0.0, 0.012
    box = [(px, py1, pz), (-px, py1, pz), (-px, py1, -pz), (px, py1, -pz),
           (px, py0, pz), (-px, py0, pz), (-px, py0, -pz), (px, py0, -pz)]
    box_base = len(verts) // 3
    for v in box:
        verts.extend(v)
    faces = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
             (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    for f in faces:
        indices.extend((box_base + f[0], box_base + f[1], box_base + f[2]))

    # Smooth normals: accumulate face normals per vertex.
    normals = [0.0] * len(verts)
    for i in range(0, len(indices), 3):
        a, b, c = indices[i] * 3, indices[i + 1] * 3, indices[i + 2] * 3
        ux, uy, uz = verts[b] - verts[a], verts[b + 1] - verts[a + 1], verts[b + 2] - verts[a + 2]
        vx, vy, vz = verts[c] - verts[a], verts[c + 1] - verts[a + 1], verts[c + 2] - verts[a + 2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        for k in (a, b, c):
            normals[k] += nx; normals[k + 1] += ny; normals[k + 2] += nz
    for i in range(0, len(normals), 3):
        length = math.sqrt(normals[i] ** 2 + normals[i + 1] ** 2 + normals[i + 2] ** 2) or 1.0
        normals[i] /= length; normals[i + 1] /= length; normals[i + 2] /= length

    return verts, normals, indices


if __name__ == '__main__':
    v, n, i = blade_geometry()
    print('vertices', len(v) // 3, 'triangles', len(i) // 3)
    ys = v[1::3]
    print('y range', round(min(ys), 3), round(max(ys), 3))
