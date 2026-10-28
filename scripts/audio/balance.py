"""Loudness balance between the kinds of sound (声音任务说明.md 8).

Every kind belongs to a category of the 8.1 table.  A category's level is the
highest ebur128 momentary loudness (M, 400 ms window) of its solo stem: only
that category's voices, with the same gains, density rule and reverb as the
real mix, times the real mix's output gain (the normalisation gain and the
true-peak limiter's gain, sample by sample, so the stems add up exactly to
the output file).  T is the thud's level.

    fit_mix(...)  per-category multipliers (dB) that put every category at
                  AIM relative to T, with the limiter in the loop
    report(...)   for a written mix: each category's level, offset from T and
                  whether it is in range; the mix's highest M, and its highest
                  M away from the thud (must be <= T)

    balance.py MIX.wav      # prints the table for a make_audio.py output

fit_mix meters with a numpy copy of BS.1770 (fast, within 0.05 LU of
ffmpeg); report() measures with ffmpeg ebur128.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402

FFMPEG = '/opt/homebrew/bin/ffmpeg'
SR = synth.SR

CATEGORY = {
    'thud': 'thud', 'alert': 'alert', 'tone': 'tone', 'swap': 'tone',
    'line': 'line', 'tick-num': 'line', 'part': 'part', 'tick': 'part',
    'slide': 'slide', 'path': 'path', 'spin': 'spin', 'type': 'type',
}
# Allowed momentary maximum, LU relative to T (8.1).  None: no lower bound.
RANGES = {
    'thud': (0.0, 0.0), 'alert': (-4.0, -2.0), 'tone': (-6.0, -3.0),
    'line': (-8.0, -5.0), 'part': (-9.0, -6.0), 'slide': (-11.0, -8.0),
    'path': (None, -8.0), 'spin': (-13.0, -10.0), 'type': (-15.0, -12.0),
}
# Where fit_mix puts each category: 0.5 LU inside the loud end of its range.
# The overall level is limited by the thud (see MAX_LIMIT_DB), so every other
# category is kept as loud as its range allows, with room for rounding.
AIM = {'thud': 0.0, 'alert': -2.5, 'tone': -3.5, 'line': -5.5, 'part': -6.5,
       'slide': -8.5, 'path': -8.5, 'spin': -10.5, 'type': -12.5}
ORDER = ['thud', 'alert', 'tone', 'line', 'part', 'slide', 'path', 'spin', 'type']
TOL_LU = 0.05               # ebur128 prints 0.1 LU steps
FIT_TOL_LU = 0.03
THUD_BODY = 0.9             # s: the thud's decay; M windows over it are "at 21.9 s"
# Most the limiter may take off any sample.  More than a few dB flattens the
# thud's decay into a held low note (声音任务说明 一: short and clean).
MAX_LIMIT_DB = 3.0


def category(kind):
    return CATEGORY[kind]


# ---- meters --------------------------------------------------------------------
# BS.1770-4 K-weighting at 48 kHz: high shelf, then high-pass.
_SHELF = ([1.53512485958697, -2.69169618940638, 1.19839281085285],
          [1.0, -1.69065929318241, 0.73248077421585])
_HPF = ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])


def _kpow(x):
    y = signal.lfilter(*_SHELF, x, axis=0)
    y = signal.lfilter(*_HPF, y, axis=0)
    return (y ** 2).sum(axis=1)


def momentary_np(x):
    """(window end times, M) every 100 ms over 400 ms windows, as ebur128."""
    c = np.concatenate([[0.0], np.cumsum(_kpow(np.asarray(x, dtype=np.float64)))])
    hop, win = SR // 10, 4 * SR // 10
    ends = np.arange(win, len(x) + 1, hop)
    p = (c[ends] - c[ends - win]) / win
    return ends / SR, -0.691 + 10 * np.log10(np.maximum(p, 1e-30))


def integrated_np(x):
    """Gated integrated loudness (absolute -70, relative -10)."""
    _, m = momentary_np(x)
    p = 10 ** ((m + 0.691) / 10)
    g = m > -70.0
    rel = -0.691 + 10 * np.log10(p[g].mean()) - 10.0
    g &= m > rel
    return float(-0.691 + 10 * np.log10(p[g].mean()))


def momentary(x):
    """(window end times, M) from ffmpeg ebur128, every 100 ms."""
    fd, tmp = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    try:
        from scipy.io import wavfile
        wavfile.write(tmp, SR, np.asarray(x, dtype=np.float32))
        r = subprocess.run([FFMPEG, '-nostats', '-hide_banner', '-v', 'verbose', '-i', tmp,
                            '-af', 'ebur128=framelog=verbose', '-f', 'null', '-'],
                           capture_output=True, text=True, check=True)
    finally:
        os.remove(tmp)
    rows = re.findall(r't: *([\d.]+)\s+TARGET:.*?M: *(-?[\d.]+|-inf|nan)', r.stderr)
    t = np.array([float(a) for a, _ in rows])
    m = np.array([float(b) if b not in ('-inf', 'nan') else -200.0 for _, b in rows])
    return t, m


def _max_m(x, fast):
    t, m = momentary_np(x) if fast else momentary(x)
    k = int(np.argmax(m))
    return float(m[k]), float(t[k])


# ---- stems and fitting -----------------------------------------------------------

def stems(mx, events, start, end, spin, seed, cat_db=None):
    """Solo stem per category: the dry render of that category alone (density
    gains of the whole table) through the shared reverb, before the output
    gain.  float32 to keep a 120 s film in memory."""
    out = {}
    for c in [c for c in ORDER if any(category(e['kind']) == c and start <= e['t'] < end for e in events)]:
        dry, _ = mx.render(events, start, end, spin, seed, cat_db, only={c})
        out[c] = mx.reverb(dry).astype(np.float32)
    return out


def output_gain(mx, x, target, max_limit_db, gain_db=None, meter=integrated_np):
    """Per-sample output gain of make_audio.normalise_gain (same rule), metered
    with `meter`.  Returns (envelope, gain_db, capped)."""
    gain_db = target - meter(x) if gain_db is None else gain_db
    cap = None
    if max_limit_db is not None:
        cap = mx.CEILING_DBTP + max_limit_db - 20 * np.log10(max(float(mx.true_peak_env(x).max()), 1e-12))
    capped = False
    for _ in range(12):
        if cap is not None and gain_db >= cap:
            gain_db, capped = cap, True
        used = gain_db
        env = synth.db(used) * mx.limit_gain(x * synth.db(used))
        lufs = meter(x * env[:, None])
        if capped or abs(lufs - target) < 0.02:
            break
        gain_db += target - lufs
    return env, used, capped


def fit_mix(mx, st, target, max_limit_db=MAX_LIMIT_DB, rounds=30):
    """Multipliers (dB, thud 0) that put every category's level at AIM from
    T after normalisation and limiting.  Returns (multipliers, record)."""
    if 'thud' not in st:
        return {c: 0.0 for c in st}, {'note': 'no thud in the table; levels left as they are'}
    lv = {c: _max_m(x, True)[0] for c, x in st.items()}
    m = {c: (0.0 if c == 'thud' else lv['thud'] + AIM[c] - lv[c]) for c in st}
    gain_db, err, off = None, None, {}
    for r in range(rounds):
        mix = sum(x.astype(np.float64) * synth.db(m[c]) for c, x in st.items())
        env, gain_db, capped = output_gain(mx, mix, target, max_limit_db, gain_db)
        lv = {c: _max_m(x * (synth.db(m[c]) * env)[:, None], True)[0] for c, x in st.items()}
        off = {c: lv[c] - lv['thud'] for c in st}
        err = max(abs(off[c] - AIM[c]) for c in st)
        if err < FIT_TOL_LU:
            break
        for c in st:
            if c != 'thud':
                m[c] += AIM[c] - off[c]
    rec = {'rounds': r + 1, 'max_error_lu': round(err, 3), 'capped': capped,
           'offsets': {c: round(v, 2) for c, v in off.items()}}
    return {c: round(v, 2) for c, v in m.items()}, rec


# ---- judging a written mix ----------------------------------------------------------

def judge(lv):
    """Rows {category, M, at, offset, range, ok} in table order, and T."""
    T = lv['thud'][0]
    rows = []
    for c in ORDER:
        if c not in lv:
            continue
        lo, hi = RANGES[c]
        d = lv[c][0] - T
        ok = (lo is None or d >= lo - TOL_LU) and d <= hi + TOL_LU
        rows.append({'category': c, 'M': round(lv[c][0], 1), 'at': round(lv[c][1], 1),
                     'offset': round(d, 1), 'range': [lo, hi], 'ok': bool(ok)})
    return rows, T


def mix_peak(x, start, thud_times, T):
    """Highest M of the mix and where; highest M over the windows away from
    the thud (not overlapping its body [t, t + THUD_BODY]), and whether that
    is <= T."""
    t, m = momentary(x)
    t = t + start
    k = int(np.argmax(m))
    at_thud = np.zeros(len(t), dtype=bool)
    for th in thud_times:
        at_thud |= (t > th) & (t - 0.4 < th + THUD_BODY)
    rest = np.where(at_thud, -200.0, m)
    j = int(np.argmax(rest))
    return {'max_M': round(float(m[k]), 1), 'max_at': round(float(t[k]), 1),
            'max_away_from_thud_M': round(float(rest[j]), 1), 'away_at': round(float(t[j]), 1),
            'T': round(T, 1), 'ok': bool(rest[j] <= T + TOL_LU)}


def rebuild(mx, cfg, x):
    """Stems of the written mix x (its .mix.json record cfg), the exact
    per-sample output gain (normalisation x limiter) and how far the stems
    times that gain are from the file (should be quantisation only)."""
    events = mx.load_events(cfg['events'])
    spin = mx.load_spin(cfg['spin'])
    start = cfg['start']
    st = stems(mx, events, start, start + len(x) / SR, spin, cfg['seed'], cfg.get('category_db'))
    mix = sum(s.astype(np.float64) for s in st.values())
    g = cfg.get('gain_db_exact', cfg['gain_db'])
    env = synth.db(g) * mx.limit_gain(mix * synth.db(g))
    return st, env, float(np.abs(mix * env[:, None] - x).max())


def report(mx, cfg, x, built=None):
    """Balance rows, T, the mix-peak record and the rebuild error for the
    written mix x.  built: rebuild()'s result, if already made."""
    st, env, rebuilt = built or rebuild(mx, cfg, x)
    if 'thud' not in st:
        return [], None, {'ok': False, 'note': 'no thud'}, rebuilt
    lv = {c: _max_m(s * env[:, None], False) for c, s in st.items()}
    rows, T = judge(lv)
    thuds = [e['t'] for e in mx.load_events(cfg['events']) if e['kind'] == 'thud']
    peak = mix_peak(x, cfg['start'], thuds, T)
    return rows, T, peak, rebuilt


def main():
    import make_audio as mx
    path = sys.argv[1]
    with open(os.path.splitext(path)[0] + '.mix.json', encoding='utf-8') as f:
        cfg = json.load(f)
    x, _, _ = mx.read_wav(path)
    rows, T, peak, rebuilt = report(mx, cfg, x)
    for r in rows:
        print(f"{'ok ' if r['ok'] else 'OUT'} {r['category']:6s} M {r['M']:6.1f} at {r['at']:5.1f}  "
              f"T{r['offset']:+5.1f}  range {r['range']}")
    print(json.dumps(peak), f'stems rebuild the file to {rebuilt:.1e}')


if __name__ == '__main__':
    main()
