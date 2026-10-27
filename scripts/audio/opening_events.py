"""Hand-written event table for the opening, 0-30 s (声音任务说明.md, 三).

    opening_events.py [OUT.json]      # default 音频/events-opening.json

Times come from the picture code, style-frames/src/frames/clip-open.ts
(milestones one to three A), and from 开头三B任务说明.md for 23.0-30.0 s,
which has no picture code yet.  verify() re-reads clip-open.ts and stops if
any constant copied below has changed there.

rotor_rps(t) is the rotor speed for the spin voice, 开头组装动画任务说明.md
21.6; make_audio.py uses it as --spin opening_events:rotor_rps.
"""
import json
import os
import re
import sys

import numpy as np

ROOT = '<项目目录>'
CLIP_OPEN = f'{ROOT}/.claude/worktrees/style-frames/src/frames/clip-open.ts'
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

# ---- 23.0-30.0 s, from 开头三B任务说明.md (三B picture not built yet) --------------

E3_NODE = 23.0
BIZ_GROUPS = [                                  # group start, members in data.ts order
    (23.4, ['design', 'drill', 'std']),
    (23.8, ['mwo', 'spray', 'awo']),
    (24.2, ['insp', 'coat']),
    (24.6, ['po', 'powder', 'supplier', 'stock']),
]
BIZ_STEP = 0.08
# 15 relations.  Fixed by 三B: po->m-comb 27.3, stock->blade 27.6,
# po->supplier 28.0.  The other twelve are not fixed there; until the 三B page
# exports its own times they are spread evenly over 25.0-27.2 in data.ts order.
FREE_RELATIONS = ['design-blade', 'drill-blade', 'std-blade', 'mwo-blade', 'spray-blade',
                  'awo-e7', 'insp-blade', 'coat-powder', 'powder-spray', 'powder-supplier',
                  'po-blade', 'blade-e3']
FIXED_RELATIONS = [('po-m-comb', 27.3), ('stock-blade', 27.6), ('po-supplier', 28.0)]
SLIDE = (30.3, 2.1)                             # dialog panel slides in 30.3-32.4

LINE_GAIN = 10 ** ((-32 - -24) / 20)            # line at -32 dBFS instead of -24

# ---- rotor -------------------------------------------------------------------

OMEGA = 360 / 4.4                               # deg/s
FULL_RPS = OMEGA / 360                          # spin voice is at full level here


def smootherstep(u):
    u = np.clip(u, 0.0, 1.0)
    return u ** 3 * (u * (6 * u - 15) + 10)


def rotor_rps(t):
    """dθ/dt / 360 for θ(t) of 21.6: smootherstep up over 22.0-23.2, constant
    to 26.0, times 1 - smootherstep((t - 26) / 2) to 28.0, zero after."""
    t = np.asarray(t, dtype=np.float64)
    up = smootherstep((t - 22.0) / 1.2)
    down = 1.0 - smootherstep((t - 26.0) / 2.0)
    return np.where((t > 22.0) & (t < 28.0), FULL_RPS * up * down, 0.0)


def rotor_degrees(t):
    """θ(t) of 21.6, for checking rotor_rps against the picture's formula."""
    I = lambda u: u ** 6 - 3 * u ** 5 + 2.5 * u ** 4
    if t <= 22.0:
        return 0.0
    if t >= 28.0:
        return 360.0
    ramp = min(1.0, (t - 22.0) / 1.2)
    cruise = max(0.0, min(t, 26.0) - 23.2)
    ease = (t - 26.0) - 2 * I((t - 26.0) / 2) if t > 26.0 else 0.0
    return OMEGA * (1.2 * I(ramp) + cruise + ease)


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
    add(22.0, 'spin', 'rotor', dur=6.0)
    add(E3_NODE, 'line', 'node e3', LINE_GAIN, 'graph')
    for start, ids in BIZ_GROUPS:
        for j, node in enumerate(ids):
            add(start + j * BIZ_STEP, 'line', f'node {node}', LINE_GAIN, 'graph')
    step = (27.2 - 25.0) / (len(FREE_RELATIONS) - 1)
    rel = [(name, 25.0 + j * step) for j, name in enumerate(FREE_RELATIONS)] + FIXED_RELATIONS
    for name, t in rel:
        add(t, 'path', f'relation {name}', src='graph')
    add(SLIDE[0], 'slide', 'dialog panel in', src='dialog', dur=SLIDE[1])
    ev.sort(key=lambda e: e['t'])
    return ev


def verify():
    """Stop if clip-open.ts no longer has the constants copied above."""
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
    missing = [s for s in need if s not in src]
    stages = [float(x) for x in re.findall(r"start: (\d+\.\d+), node: 'c-t\d'", src)]
    block = src[src.index('const M3_PIECES'):src.index('const m3Pieces')]
    m3 = [float(x) for x in re.findall(r'start: (\d+\.\d+), axis', block)]
    if stages != STAGE_STARTS:
        missing.append(f'STAGE_GROUPS starts {stages}')
    if m3 != [t for _, t in M3_STARTS]:
        missing.append(f'M3_PIECES starts {m3}')
    if missing:
        raise SystemExit('clip-open.ts changed, update opening_events.py:\n  ' + '\n  '.join(missing))
    # rotor_rps must integrate to the picture's rotor angle.
    t = np.arange(21.0, 29.0, 1e-5)
    deg = np.concatenate([[0.0], np.cumsum(360 * (rotor_rps(t[1:]) + rotor_rps(t[:-1])) / 2 * 1e-5)])
    err = max(abs(np.interp(s, t, deg) - rotor_degrees(s)) for s in np.arange(21.5, 28.6, 0.1))
    if err > 0.01:
        raise SystemExit(f'rotor_rps does not integrate to rotor_degrees (max error {err:.4f} deg)')
    return err


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    err = verify()
    ev = events()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('[\n' + ',\n'.join(json.dumps(e, ensure_ascii=False) for e in ev) + '\n]\n')
    kinds = {}
    for e in ev:
        kinds[e['kind']] = kinds.get(e['kind'], 0) + 1
    print(f'{len(ev)} events -> {out}  {kinds}  rotor check {err:.5f} deg')


if __name__ == '__main__':
    main()
