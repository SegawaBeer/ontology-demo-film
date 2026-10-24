"""Generate a simple first-stage turbine rotor disc.

Local frame: axis along X, radius in Y/Z, centred on the disc's mid-plane.
The disc fills r 0.170..0.302 so the generated blade roots (r 0.278..0.304)
sit in its rim.
"""
import math


def disc_geometry(segments=48):
    verts, faces = [], []
    inner, rim_inner, rim_outer = 0.170, 0.276, 0.302
    web, rim = 0.012, 0.030          # axial widths

    def ring(radius, x, n=segments):
        base = len(verts) // 3
        for i in range(n):
            a = 2 * math.pi * i / n
            verts.extend((x, radius * math.cos(a), radius * math.sin(a)))
        return base

    def tube(r0, r1, width):
        x0, x1 = -width / 2, width / 2
        a0 = ring(r0, x0); a1 = ring(r0, x1)
        b0 = ring(r1, x0); b1 = ring(r1, x1)
        n = segments
        for i in range(n):
            j = (i + 1) % n
            faces.extend((a0 + i, a0 + j, b0 + j, a0 + i, b0 + j, b0 + i))      # front annulus
            faces.extend((a1 + i, b1 + j, a1 + j, a1 + i, b1 + i, b1 + j))      # back annulus
            faces.extend((b0 + i, b0 + j, b1 + j, b0 + i, b1 + j, b1 + i))      # outer wall
            faces.extend((a0 + i, a1 + j, a0 + j, a0 + i, a1 + i, a1 + j))      # bore wall

    tube(inner, inner + 0.020, rim)     # bore boss
    tube(rim_inner, rim_outer, rim)     # rim
    tube(inner + 0.020, rim_inner, web) # web

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
    v, n, f = disc_geometry()
    xs, ys, zs = v[0::3], v[1::3], v[2::3]
    print('vertices', len(v) // 3, 'triangles', len(f) // 3)
    print('x %.3f..%.3f  r %.3f..%.3f' % (min(xs), max(xs), (ys[0] ** 2 + zs[0] ** 2) ** .5,
                                          max((y ** 2 + z ** 2) ** .5 for y, z in zip(ys, zs))))
