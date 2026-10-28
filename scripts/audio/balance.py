"""Loudness balance between the kinds of sound (声音任务说明.md 8).

Every kind belongs to a category of the 8.1 table.  A category's level is the
highest ebur128 momentary loudness (M, 400 ms window) of its solo stem: only
that category's voices, with the same gains, density rule and reverb as the
real mix, times the real mix's output gain (the normalisation gain and the
true-peak limiter's gain, sample by sample, so the stems add up exactly to
the output file).  T is the thud's level.

    fit_mix(...)  per-category multipliers (dB) that put every category at
                  AIM relative to T, with normalisation and limiter in the loop
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
# Where fit_mix puts each category, LU from T.  Mostly 0.3 LU inside the
# loud end of the range (room for ebur128's 0.1 LU rounding): T is capped by
# the thud's true peak, so this keeps the film as loud as the table allows.
# line / tick-num sit 0.3 LU inside the quiet end instead: the small-speaker
# check (九.5) wants the 250 Hz high-passed thud at least as loud as them,
# and the high-pass takes about 6.8 dB off the thud and nothing off them.
AIM = {'thud': 0.0, 'alert': -2.3, 'tone': -3.3, 'line': -7.7, 'part': -6.3,
       'slide': -8.3, 'path': -8.3, 'spin': -10.3, 'type': -12.3}
ORDER = ['thud', 'alert', 'tone', 'line', 'part', 'slide', 'path', 'spin', 'type']
TOL_LU = 0.05               # ebur128 prints 0.1 LU steps
THUD_BODY = 0.9             # s: the thud's decay; M windows over it are "at 21.9 s"
# Most the true-peak limiter may take off any sample (声音任务说明 九.1).  The
# mix's output gain is the one at which the limiter takes exactly this off
# the loudest true peak, the thud's; the integrated loudness then follows
# from the 8.1 table (九.2: anywhere in -23 to -15 LUFS).  More limiting held
# the thud near full level for most of a second (round three's default).
CLEAN_LIMIT_DB = 3.0
SMALL_SPEAKER_HZ = 250.0    # 九.5: 4th-order high-pass, roughly a laptop speaker
FIT_TOL_LU = 0.02          # fit_mix: offsets from AIM, at a fixed output gain
LUFS_TOL = 0.02            # fit_mix: integrated loudness from the target


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


def _at_gain(mx, st, m, gain_db, rounds=8):
    """Multipliers m corrected until every category sits at AIM from T with
    the output gain fixed at gain_db (the limiter computed on the whole mix).
    Each category's offset depends almost only on its own multiplier, so the
    direct correction converges in a few rounds.  Returns (m, envelope,
    offsets, error)."""
    m = dict(m)
    for r in range(rounds):
        mix = sum(x.astype(np.float64) * synth.db(m[c]) for c, x in st.items())
        env = synth.db(gain_db) * mx.limit_gain(mix * synth.db(gain_db))
        lv = {c: _max_m(x * (synth.db(m[c]) * env)[:, None], True)[0] for c, x in st.items()}
        off = {c: lv[c] - lv['thud'] for c in st}
        err = max(abs(off[c] - AIM[c]) for c in st)
        if err < FIT_TOL_LU or r == rounds - 1:
            break                                   # m is the one just measured
        for c in st:
            if c != 'thud':
                m[c] += AIM[c] - off[c]
    return m, env, mix, off, err


def fit_mix(mx, st, target=None, max_limit_db=CLEAN_LIMIT_DB, steps=24):
    """Multipliers (dB, thud 0) and output gain that put every category at
    AIM from T.  Returns (multipliers, record); the record's gain_db is the
    output gain, which make_audio then uses as it is.

    target None (the default): the output gain is the one at which the
    limiter takes exactly max_limit_db off the balanced mix's loudest true
    peak.  The thud's multiplier is fixed, so that gain hardly moves while
    the others are placed; a few rounds settle it.

    With a target (LUFS):
    searched over the output gain G: at a fixed G the multipliers follow
    directly (_at_gain), and the integrated loudness I(G) of the balanced mix
    rises with G (more gain, more of the thud held at the limiter, T and
    everything set against it higher).  I(G) = target is solved by false
    position on a bracket.  With max_limit_db, G may not go above the gain at
    which the limiter would take that much off the loudest true peak."""
    others = [c for c in st if c != 'thud']
    if 'thud' not in st or not others:
        return {c: 0.0 for c in st}, {'note': 'nothing to balance against the thud'}
    lv0 = {c: _max_m(x, True)[0] for c, x in st.items()}
    m = {'thud': 0.0, **{c: lv0['thud'] + AIM[c] - lv0[c] for c in others}}
    trail = []

    def loud(g):
        nonlocal m
        m, env, mix, off, err = _at_gain(mx, st, m, g)
        lufs = integrated_np(mix * env[:, None])
        tp = 20 * np.log10(max(float(mx.true_peak_env(mix).max()), 1e-12))
        trail.append((round(g, 3), round(lufs, 3), round(err, 3)))
        return lufs, {'m': dict(m), 'off': off, 'err': err, 'gain_db': g, 'lufs': lufs,
                      'limit_db': g + tp - mx.CEILING_DBTP}

    mix0 = sum(x.astype(np.float64) * synth.db(m[c]) for c, x in st.items())
    if target is None:
        if max_limit_db is None:
            raise SystemExit('balance: without a loudness target the limiter needs a cap')
        g = mx.CEILING_DBTP + max_limit_db - 20 * np.log10(max(float(mx.true_peak_env(mix0).max()), 1e-12))
        for _ in range(steps):
            lufs, rec = loud(g)
            cap = rec['gain_db'] - rec['limit_db'] + max_limit_db
            if abs(cap - g) < 0.005:
                break
            g = cap
        if rec['err'] >= 5 * FIT_TOL_LU:
            raise SystemExit(f'balance: could not place the categories (error {rec["err"]:.2f} LU)')
        out = {'evaluations': len(trail), 'max_error_lu': round(rec['err'], 3), 'capped': True,
               'gain_db': rec['gain_db'], 'lufs': round(rec['lufs'], 2), 'max_limit_db': max_limit_db,
               'limiter_on_loudest_peak_db': round(rec['limit_db'], 2),
               'offsets': {c: round(v, 2) for c, v in rec['off'].items()}, 'trail': trail}
        return {c: round(v, 4) for c, v in rec['m'].items()}, out
    g = target - integrated_np(mix0)                       # no limiting at all
    cap = None
    if max_limit_db is not None:
        cap = mx.CEILING_DBTP + max_limit_db - 20 * np.log10(max(float(mx.true_peak_env(mix0).max()), 1e-12))
    lo = hi = None
    best = None
    for _ in range(steps):
        if cap is not None:
            g = min(g, cap)
        lufs, rec = loud(g)
        if best is None or abs(lufs - target) < abs(best['lufs'] - target):
            best = rec
        if abs(lufs - target) < LUFS_TOL:
            break
        if lufs < target:
            if cap is not None and g >= cap - 1e-9:
                best = rec                                  # as loud as the cap allows
                break
            lo = (g, lufs)
        else:
            hi = (g, lufs)
        if lo and hi:
            g = lo[0] + (hi[0] - lo[0]) * (target - lo[1]) / (hi[1] - lo[1])
            g = min(max(g, lo[0] + 0.05 * (hi[0] - lo[0])), hi[0] - 0.05 * (hi[0] - lo[0]))
        elif lo:
            g = lo[0] + max(2.0, 2.0 * (target - lo[1]))   # step up until above the target
        else:
            g = hi[0] - max(2.0, 2.0 * (hi[1] - target))
    if best['err'] >= 5 * FIT_TOL_LU:
        raise SystemExit(f'balance: could not place the categories (error {best["err"]:.2f} LU)')
    capped = cap is not None and best['gain_db'] >= cap - 1e-9
    rec = {'evaluations': len(trail), 'max_error_lu': round(best['err'], 3), 'capped': bool(capped),
           'gain_db': best['gain_db'], 'lufs': round(best['lufs'], 2), 'max_limit_db': max_limit_db,
           'limiter_on_loudest_peak_db': round(best['limit_db'], 1),
           'offsets': {c: round(v, 2) for c, v in best['off'].items()}, 'trail': trail}
    return {c: round(v, 4) for c, v in best['m'].items()}, rec


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


def small_speaker(st, env, x, start, thud_times):
    """九.5: the output and each category stem through a 4th-order
    SMALL_SPEAKER_HZ high-pass.  ok when the thud stem's momentary maximum is
    at least the line / tick-num stem's.  Also reports the high-passed mix's
    maximum over the thud and away from it."""
    hp = signal.butter(4, SMALL_SPEAKER_HZ, 'highpass', fs=SR, output='sos')
    lv = {c: _max_m(signal.sosfilt(hp, st[c] * env[:, None], axis=0), False)
          for c in ('thud', 'line') if c in st}
    t, m = momentary(signal.sosfilt(hp, x, axis=0))
    t = t + start
    at = np.zeros(len(t), dtype=bool)
    for th in thud_times:
        at |= (t > th) & (t - 0.4 < th + THUD_BODY)
    res = {'highpass_hz': SMALL_SPEAKER_HZ,
           'thud_M': round(lv['thud'][0], 1) if 'thud' in lv else None,
           'line_M': round(lv['line'][0], 1) if 'line' in lv else None,
           'mix_at_thud_M': round(float(m[at].max()), 1) if at.any() else None,
           'mix_away_M': round(float(m[~at].max()), 1) if (~at).any() else None}
    if 'thud' in lv and 'line' in lv:
        res['margin_lu'] = round(lv['thud'][0] - lv['line'][0], 2)
        res['ok'] = bool(lv['thud'][0] >= lv['line'][0] - TOL_LU)
    else:
        res['ok'] = 'thud' in lv
    return res


def limiter_record(cfg, env, start):
    """Largest gain reduction of the limiter (dB) and when."""
    g = cfg.get('gain_db_exact', cfg['gain_db'])
    red = -20 * np.log10(np.maximum(env / synth.db(g), 1e-12))
    k = int(np.argmax(red))
    return {'max_reduction_db': round(float(red[k]), 2), 'at_s': round(start + k / SR, 3),
            'seconds_reduced': round(float((red > 0.001).sum()) / SR, 3), 'limit_db': CLEAN_LIMIT_DB}


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
