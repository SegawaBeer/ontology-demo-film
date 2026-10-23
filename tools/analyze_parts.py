"""Cluster connected components into candidate parts and summarise them.

Read-only analysis helper: prints axial/radial bins, repeated-shape groups and
the pieces that no rule recognises yet.
"""
import sys, math, collections, json
sys.path.insert(0, 'tools')
from glb_pieces import load, pieces_of

SRC = '<下载目录>/turbine__turbofan_engine__jet_engine.glb'


def main():
    g, bn = load(SRC)
    pieces = pieces_of(g, bn)
    print('pieces', len(pieces), 'tris', sum(p['tris'] for p in pieces))
    mats = g.get('materials', [])
    names = [m.get('name') for m in mats]

    bins = collections.Counter()
    tris = collections.Counter()
    for p in pieces:
        cx = (p['x0'] + p['x1']) / 2
        r = (p['r0'] + p['r1']) / 2
        key = (round(cx * 10) / 10, round(r * 10) / 10)
        bins[key] += 1
        tris[key] += p['tris']
    print('\nAXIAL/RADIAL BINS (x, r): count / tris')
    for key in sorted(bins):
        print(f'  x={key[0]:+.1f} r={key[1]:.1f}  n={bins[key]:4d}  tris={tris[key]:6d}')

    print('\nREPEATED SHAPES (tris, bbox size, material): count')
    groups = collections.defaultdict(list)
    for p in pieces:
        size = (round(p['x1'] - p['x0'], 3), round(p['y1'] - p['y0'], 3), round(p['z1'] - p['z0'], 3))
        groups[(p['tris'], size, p['mat'])].append(p)
    for key, items in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:25]:
        if len(items) < 4:
            continue
        xs = [(p['x0'] + p['x1']) / 2 for p in items]
        rs = [(p['r0'] + p['r1']) / 2 for p in items]
        print(f'  tris={key[0]} size={key[1]} mat={names[key[2]] if key[2] is not None else None}'
              f' n={len(items)} x={min(xs):.2f}..{max(xs):.2f} r={min(rs):.2f}..{max(rs):.2f}')

    print('\nPIECES BY MATERIAL')
    per = collections.Counter(p['mat'] for p in pieces)
    for m, n in per.most_common():
        print(' ', names[m] if m is not None else None, n)

    print('\nBIGGEST PIECES')
    for p in sorted(pieces, key=lambda p: -p['tris'])[:20]:
        print(f'  tris={p["tris"]:6d} mat={names[p["mat"]] if p["mat"] is not None else None:16s}'
              f' x={p["x0"]:+.2f}..{p["x1"]:+.2f} r={p["r0"]:.2f}..{p["r1"]:.2f}')


if __name__ == '__main__':
    main()
