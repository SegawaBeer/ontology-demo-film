"""Hand-written event table for the opening, 0-30 s (声音任务说明.md 三 and 7.2).

    opening_events.py [OUT.json]      # default 音频/events-opening.json

Times are copied from the opening picture code in the style-frames worktree
(read only): clip-open.ts for milestones one to three A, opening-net.ts and
data.ts for three B (23.0-30.0, accepted at 89aca04).  verify() re-reads
those files and stops if any constant copied below has changed there.

The rotor speed for the spin voice lives in rotor.py (whole film);
rotor_rps / FULL_RPS are re-exported here so --spin opening_events:rotor_rps
from the first round still works.
"""
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rotor  # noqa: E402
from rotor import FULL_RPS, OMEGA, rotor_rps  # noqa: E402,F401

ROOT = '<项目目录>'
FRAMES = f'{ROOT}/.claude/worktrees/style-frames/src/frames'
CLIP_OPEN = f'{FRAMES}/clip-open.ts'
OPENING_NET = f'{FRAMES}/opening-net.ts'
DATA_TS = f'{FRAMES}/data.ts'
OUT = f'{ROOT}/音频/events-opening.json'

# ---- times copied from clip-open.ts -----------------------------------------

def blade_start(k):
    """Ring blade k = 2..100 appears (bladeStart)."""
    return 7.65 + 0.95 * np.sqrt((k - 2) / 98)


STAGE_STARTS = [10.10, 10.70, 11.30, 11.90]     # STAGE_GROUPS, turbine stages 2-5
SHAFT_START = 12.70


def comp_start(i):
    """COMP_ORDER item i = 0..7 appears (compStart)."""
    return 13.50 + 2.40 * (i / 7) ** 0.7


# COMP_ORDER: stage-4, stators, stage-3, struts, stage-2, stage-1, drum, inlet-bell.
# Section 三 asks for a part on each compressor blade ring: stages 4, 3, 2, 1.
COMP_RINGS = [0, 2, 4, 5]
M3_STARTS = [                                   # M3_PIECES
    ('combustor', 17.00), ('core-casing', 17.80), ('fan-hub', 18.70),
    ('fan-cowl', 20.20), ('nacelle', 20.20), ('exhaust', 21.30), ('spinner', 21.30),
]


def fan_start(k):
    """Fan blade k = 1..16 appears (fanStart)."""
    return 19.10 + 0.05 * (k - 1)


THUD = 21.90                                    # every part in place

# ---- 23.0-30.0 s, copied from opening-net.ts and data.ts ----------------------

E3_START = 23.0                                 # engine three fades in
GROUP_START = {'rd': 23.4, 'mfg': 23.8, 'qa': 24.2, 'scm': 24.6}
NODE_GAP = 0.08
# BIZ_PLAN: groups in data.ts order, nodes in data.ts order inside a group.
BIZ_ORDER = [
    ('rd', ['design', 'drill', 'std']),
    ('mfg', ['mwo', 'spray', 'awo']),
    ('qa', ['insp', 'coat']),
    ('scm', ['po', 'powder', 'supplier', 'stock']),
]
REL_DUR = 0.35
# REL_PLAN: (from, to, start, end); end None is start + REL_DUR.
REL_PLAN = [
    ('design', 'blade', 25.0, None), ('coat', 'powder', 25.2, None),
    ('drill', 'blade', 25.4, None), ('powder', 'spray', 25.6, None),
    ('std', 'blade', 25.8, None), ('awo', 'e7', 26.0, None),
    ('mwo', 'blade', 26.2, None), ('powder', 'supplier', 26.4, None),
    ('spray', 'blade', 26.6, None), ('insp', 'blade', 26.8, None),
    ('blade', 'e3', 27.0, None), ('po', 'blade', 27.2, None),
    ('po', 'm-comb', 27.3, 27.65), ('stock', 'blade', 27.6, 28.6),
    ('po', 'supplier', 28.0, 28.6),
]
ALL_DRAWN = 28.6            # last relation lands (库存 -> 叶片); the counter is final
ROTOR_LINES = [             # rotorSpeed(): the opening part of rotor.speed_factor
    'if (t <= 22.0 || t >= 28.0) return 0;',
    'if (t < 23.2) return smoother((t - 22.0) / 1.2);',
    'if (t <= 26.0) return 1;',
    'return 1 - smoother((t - 26.0) / 2);',
]
# The table covers 0-30 s only.  The dialog slide at 30.3 (声音任务说明 7: heard
# in the full mix) is in the film page's own event table from 30 s on.
END = 30.0

LINE_GAIN = 10 ** ((-32 - -24) / 20)            # line at -32 dBFS instead of -24
TICK_NUM_GAIN = 0.5


def rel_end(start, end):
    return round(start + REL_DUR, 6) if end is None else end


# ---- the table -----------------------------------------------------------------

def events():
    ev = []

    def add(t, kind, what, gain=1.0, src='3d', **extra):
        ev.append({'t': round(float(t), 6), 'kind': kind, 'gain': round(gain, 6),
                   'src': src, 'what': what, **extra})

    add(0.3, 'tone', 'first blade')
    for k in range(2, 101):
        add(blade_start(k), 'tick', f'ring blade {k}')
    for s, t in enumerate(STAGE_STARTS, start=2):
        add(t, 'part', f'turbine stage {s}')
    add(SHAFT_START, 'part', 'shaft')
    for n, i in zip((4, 3, 2, 1), COMP_RINGS):
        add(comp_start(i), 'part', f'compressor stage {n}')
    for name, t in M3_STARTS:
        add(t, 'part', name)
    for k in range(1, 17):
        add(fan_start(k), 'tick', f'fan blade {k}')
    add(THUD, 'thud', 'engine complete')
    for t0, dur in rotor.SPIN_EVENTS:
        if t0 < END:
            add(t0, 'spin', 'rotor', dur=dur)
    add(E3_START, 'line', 'node e3', LINE_GAIN, 'graph')
    for group, ids in BIZ_ORDER:
        for j, node in enumerate(ids):
            add(GROUP_START[group] + j * NODE_GAP, 'line', f'node {node}', LINE_GAIN, 'graph')
    for a, b, start, _ in REL_PLAN:
        add(start, 'path', f'relation {a} -> {b}', src='graph')
    add(ALL_DRAWN, 'tick-num', 'relation counter final', TICK_NUM_GAIN, 'graph')
    ev.sort(key=lambda e: e['t'])
    assert all(e['t'] < END for e in ev)
    return ev


# ---- check against the picture code -------------------------------------------

def _block(src, head, tail):
    i = src.index(head)
    return src[i:src.index(tail, i)]


def _check_clip_open(bad):
    src = open(CLIP_OPEN, encoding='utf-8').read()
    need = [
        'const bladeStart = (k: number) => 7.65 + 0.95 * Math.sqrt((k - 2) / 98);',
        "addPiece(['shaft.main'], 12.70,",
        'const compStart = (i: number) => 13.50 + 2.40 * Math.pow(i / 7, 0.7);',
        'const fanStart = (k: number) => 19.10 + 0.05 * (k - 1);',
        'const OMEGA = 360 / 4.4;',
        "const COMP_ORDER = ['compressor.stage-4', 'compressor.stators', 'compressor.stage-3', "
        "'compressor.struts', 'compressor.stage-2', 'compressor.stage-1', 'compressor.drum', 'compressor.inlet-bell'];",
    ]
    bad += [f'clip-open.ts: {s}' for s in need if s not in src]
    stages = [float(x) for x in re.findall(r"start: (\d+\.\d+), node: 'c-t\d'", src)]
    m3 = [float(x) for x in re.findall(r'start: (\d+\.\d+), axis', _block(src, 'const M3_PIECES', 'const m3Pieces'))]
    if stages != STAGE_STARTS:
        bad.append(f'clip-open.ts: STAGE_GROUPS starts {stages}')
    if m3 != [t for _, t in M3_STARTS]:
        bad.append(f'clip-open.ts: M3_PIECES starts {m3}')


def _check_opening_net(bad):
    src = open(OPENING_NET, encoding='utf-8').read()
    data = open(DATA_TS, encoding='utf-8').read()
    need = [
        f'export const E3_START = {E3_START};',
        f'const NODE_GAP = {NODE_GAP};',
        f'const REL_DUR = {REL_DUR};',
        'export const BIZ_PLAN = groups.flatMap(g => nodes.filter(n => n.group === g.id)',
        'start: GROUP_START[g.id] + NODE_GAP * i',
        'end = start + REL_DUR',
        *ROTOR_LINES,
    ]
    bad += [f'opening-net.ts: {s}' for s in need if s not in src]
    m = re.search(r'export const GROUP_START: Record<string, number> = \{([^}]*)\}', src)
    groups = {k: float(v) for k, v in re.findall(r'(\w+): ([\d.]+)', m.group(1))} if m else None
    if groups != GROUP_START:
        bad.append(f'opening-net.ts: GROUP_START {groups}')
    plan = [(a, b, float(s), float(e) if e else None) for a, b, s, e in re.findall(
        r"rel\('([\w-]+)', '([\w-]+)', ([\d.]+)(?:, ([\d.]+))?", _block(src, 'export const REL_PLAN', '];'))]
    if plan != REL_PLAN:
        bad.append(f'opening-net.ts: REL_PLAN {plan}')
    if max(rel_end(s, e) for _, _, s, e in REL_PLAN) != ALL_DRAWN:
        bad.append('opening-net.ts: last relation no longer lands at 28.6')
    order = re.findall(r"id: '(\w+)'", _block(data, 'export const groups', '] as const;'))
    biz = re.findall(r"\{ id: '([\w-]+)'[^}]*kind: 'biz', group: '(\w+)'", data)
    plan_biz = [(g, [n for n, ng in biz if ng == g]) for g in order]
    if plan_biz != BIZ_ORDER:
        bad.append(f'data.ts: business nodes by group {plan_biz}')


def verify():
    """Stop if the picture code no longer has the constants copied above."""
    bad = []
    _check_clip_open(bad)
    _check_opening_net(bad)
    if bad:
        raise SystemExit('opening picture changed, update opening_events.py:\n  ' + '\n  '.join(bad))
    return {'clip_open': CLIP_OPEN, 'opening_net': OPENING_NET, 'data': DATA_TS}


def write(out=OUT):
    """verify(), then write the table; returns the events."""
    verify()
    ev = events()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('[\n' + ',\n'.join(json.dumps(e, ensure_ascii=False) for e in ev) + '\n]\n')
    return ev


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    r = rotor.verify()
    ev = write(out)
    kinds = {}
    for e in ev:
        kinds[e['kind']] = kinds.get(e['kind'], 0) + 1
    print(f'{len(ev)} events -> {out}  {kinds}  rotor {r}')


if __name__ == '__main__':
    main()
