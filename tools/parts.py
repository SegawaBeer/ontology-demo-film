"""Shared geometry helpers: split the source mesh into parts.

A part is one physical object: a blade, a bolt, a casing segment. The source
mesh is merged by material, so parts are recovered by connecting components
(pieces) whose bounding boxes overlap and whose angular positions coincide.
"""
import math
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glb_pieces import load, pieces_of

SRC = os.environ.get('SOURCE_GLB', os.path.expanduser('~/Downloads/turbine__turbofan_engine__jet_engine.glb'))


def angular_gap(a, b):
    d = abs(a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def make_parts(pieces, x_gap=0.02, r_gap=0.05, dtheta=0.012):
    """Union pieces that belong to the same physical object.

    Parts on a ring sit at distinct angles; the blocks of one bolt or one blade
    share an angle. Pieces merge when their axial and radial intervals touch
    and their angular positions coincide.
    """
    parent = list(range(len(pieces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    def gap(a0, a1, b0, b1):
        return max(0.0, max(a0, b0) - min(a1, b1))

    dx, dr, dt = 0.06, 0.06, dtheta
    cells = collections.defaultdict(list)
    for i, p in enumerate(pieces):
        cx = (p['x0'] + p['x1']) / 2
        cy = (p['y0'] + p['y1']) / 2
        cz = (p['z0'] + p['z1']) / 2
        p['cx'], p['cy'], p['cz'] = cx, cy, cz
        p['r'] = math.hypot(cy, cz)
        p['theta'] = math.atan2(cz, cy) % (2 * math.pi)
        cells[(round(p['cx'] / dx), round(p['r'] / dr), round(p['theta'] / dt))].append(i)

    for i, p in enumerate(pieces):
        kx, kr, kt = round(p['cx'] / dx), round(p['r'] / dr), round(p['theta'] / dt)
        for ax in (kx - 1, kx, kx + 1):
            for ar in (kr - 1, kr, kr + 1):
                for at in (kt - 1, kt, kt + 1):
                    for j in cells.get((ax, ar, at), ()):
                        if j <= i:
                            continue
                        q = pieces[j]
                        if gap(p['x0'], p['x1'], q['x0'], q['x1']) > x_gap:
                            continue
                        if gap(p['r0'], p['r1'], q['r0'], q['r1']) > r_gap:
                            continue
                        if angular_gap(p['theta'], q['theta']) > dtheta:
                            continue
                        union(i, j)

    groups = collections.defaultdict(list)
    for i in range(len(pieces)):
        groups[find(i)].append(i)

    parts = []
    for members in groups.values():
        ps = [pieces[i] for i in members]
        xs0 = min(p['x0'] for p in ps); xs1 = max(p['x1'] for p in ps)
        ys0 = min(p['y0'] for p in ps); ys1 = max(p['y1'] for p in ps)
        zs0 = min(p['z0'] for p in ps); zs1 = max(p['z1'] for p in ps)
        r0 = min(p['r0'] for p in ps); r1 = max(p['r1'] for p in ps)
        parts.append({
            'pieces': ps,
            'tris': sum(p['tris'] for p in ps),
            'x0': xs0, 'x1': xs1, 'y0': ys0, 'y1': ys1, 'z0': zs0, 'z1': zs1,
            'r0': r0, 'r1': r1,
            'cx': (xs0 + xs1) / 2, 'cy': (ys0 + ys1) / 2, 'cz': (zs0 + zs1) / 2,
            'r': (r0 + r1) / 2,
            'theta': sum(p['theta'] for p in ps) / len(ps) % (2 * math.pi),
            'mat': collections.Counter(p['mat'] for p in ps).most_common(1)[0][0],
        })
    parts.sort(key=lambda p: (p['cx'], p['r'], p['theta']))
    return parts


def load_parts(path=SRC):
    g, bn = load(path)
    pieces = pieces_of(g, bn)
    return g, bn, pieces, make_parts(pieces)


if __name__ == '__main__':
    g, bn, pieces, parts = load_parts()
    print('pieces', len(pieces), 'parts', len(parts))
    names = [m.get('name') for m in g.get('materials', [])]
    singles = [p for p in parts if len(p['pieces']) > 1]
    print('parts made of several pieces:', len(singles))
    biggest = sorted(parts, key=lambda p: -len(p['pieces']))[:8]
    for p in biggest:
        print('  merge', len(p['pieces']), 'pieces x=%.3f r=%.3f tris=%d mat=%s' % (p['cx'], p['r'], p['tris'], names[p['mat']]))
    bins = collections.Counter()
    for p in parts:
        bins[(round(p['cx'], 1), round(p['r'], 1))] += 1
    print('parts per (x,r) bin, bins with >=8 parts:')
    for key in sorted(bins):
        if bins[key] >= 8:
            print('  x=%+.1f r=%.1f n=%d' % (key[0], key[1], bins[key]))
