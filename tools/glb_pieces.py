import json, struct, sys, math, collections

def load(path):
    d = open(path, 'rb').read()
    off, js, bn = 12, None, b''
    while off + 8 <= len(d):
        l, t = struct.unpack('<I4s', d[off:off + 8])
        if t == b'JSON':
            js = json.loads(d[off + 8:off + 8 + l])
        elif t.startswith(b'BIN'):
            bn = d[off + 8:off + 8 + l]
        off += 8 + l
    return js, bn

FMT = {5126: ('f', 4), 5125: ('I', 4), 5123: ('H', 2), 5121: ('B', 1)}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}

def reader(g, bn):
    acc, bv = g['accessors'], g['bufferViews']
    def read(ai):
        a = acc[ai]; v = bv[a['bufferView']]
        f, sz = FMT[a['componentType']]; n = NC[a['type']]
        off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = v.get('byteStride') or sz * n
        if stride == sz * n:
            return struct.unpack_from('<%d%s' % (a['count'] * n, f), bn, off), n
        out = []
        for i in range(a['count']):
            out.extend(struct.unpack_from('<%d%s' % (n, f), bn, off + i * stride))
        return tuple(out), n
    return read

def pieces_of(g, bn):
    read = reader(g, bn)
    out = []
    for mi, mesh in enumerate(g['meshes']):
        for pi, prim in enumerate(mesh['primitives']):
            pos, _ = read(prim['attributes']['POSITION'])
            idx, _ = read(prim['indices']) if 'indices' in prim else (tuple(range(len(pos) // 3)), 1)
            nrm = read(prim['attributes']['NORMAL'])[0] if 'NORMAL' in prim['attributes'] else None
            weld, wid = {}, []
            for i in range(0, len(pos), 3):
                k = (round(pos[i] * 1e4), round(pos[i + 1] * 1e4), round(pos[i + 2] * 1e4))
                wid.append(weld.setdefault(k, len(weld)))
            par = list(range(len(weld)))
            def find(x):
                while par[x] != x:
                    par[x] = par[par[x]]; x = par[x]
                return x
            for t in range(0, len(idx), 3):
                a, b, c = wid[idx[t]], wid[idx[t + 1]], wid[idx[t + 2]]
                ra, rb, rc = find(a), find(b), find(c)
                par[rb] = ra
                par[find(rc)] = ra
            groups = collections.defaultdict(list)
            for t in range(0, len(idx), 3):
                groups[find(wid[idx[t]])].append((idx[t], idx[t + 1], idx[t + 2]))
            for root, tris in groups.items():
                vs = sorted({v for tri in tris for v in tri})
                xs = [pos[v * 3] for v in vs]; ys = [pos[v * 3 + 1] for v in vs]; zs = [pos[v * 3 + 2] for v in vs]
                rs = [math.hypot(ys[i], zs[i]) for i in range(len(vs))]
                out.append(dict(mesh=mi, prim=pi, mat=prim.get('material'), tris=len(tris),
                                vs=vs, trisv=tris,
                                x0=min(xs), x1=max(xs), y0=min(ys), y1=max(ys), z0=min(zs), z1=max(zs),
                                r0=min(rs), r1=max(rs), n=nrm, pos=pos, idx=idx))
    return out

if __name__ == '__main__':
    g, bn = load(sys.argv[1])
    ps = pieces_of(g, bn)
    print('pieces', len(ps))
    big = [p for p in ps if p['tris'] >= 100]
    print('pieces>=100 tris', len(big))
    print('\nBY MESH: mesh | pieces | tris | x range | r max')
    bym = collections.defaultdict(lambda: [0, 0, 9, -9, 0])
    for p in ps:
        e = bym[(p['mesh'], p['mat'])]
        e[0] += 1; e[1] += p['tris']; e[2] = min(e[2], p['x0']); e[3] = max(e[3], p['x1']); e[4] = max(e[4], p['r1'])
    for k, e in sorted(bym.items()):
        print(k, e[0], e[1], round(e[2], 2), round(e[3], 2), round(e[4], 2))
    print('\nBIG PIECES (>=2000 tris): id tris x0 x1 r0 r1')
    for i, p in enumerate(sorted(big, key=lambda p: -p['tris'])[:40]):
        print(i, p['tris'], round(p['x0'], 2), round(p['x1'], 2), round(p['r0'], 2), round(p['r1'], 2), 'mat', p['mat'])
