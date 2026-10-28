"""Checks of 声音任务说明.md section 五 (and 7.5) on a WAV written by make_audio.py.

    check_audio.py MIX.wav [--samples N]     # reads MIX.mix.json written next to it

- Samples: with --samples, the file has exactly N samples per channel.
- Found: every event of the table lies inside the file, and its own voice is
  on the waveform at its onset at about the level it was mixed at.
- Onsets: every event is found on the final waveform and its onset is within
  5 ms of the event time.  Two measurements:
    locate  - cross-correlate the file with the event's own voice (rebuilt
              exactly as make_audio built it) over +-10 ms; onset = found
              position + the voice's own rise to -20 dB of its peak.  Works
              for every event, including ticks 5 ms apart.
              Where other voices overlap ("dense"), only the voice's first
              8 ms above 2.6 kHz is matched (its own noise burst / attack).
    detect  - no model: on the 400 Hz high-passed file, the first sample whose
              envelope rises 25 % of the way from the level before the event
              to the peak after it.  Only for events no other hit voice
              overlaps from 25 ms before to 40 ms after.
  spin and slide follow a motion that starts from rest, so their sound rises
  with the motion; for them only the locate position is checked.
- Loudness -16 +- 0.5 LUFS and true peak <= -1 dBTP (ffmpeg ebur128; loudnorm
  as a second reading).
- Balance (8.2): each category's momentary maximum from its solo stem, against
  the thud's (T) and the 8.1 ranges; and the mix's own momentary maximum away
  from the thud must not be above T (balance.py).
- 48 kHz / 24-bit / stereo, no clipped samples, |mean| < 0.001 per channel.
- Head: 0-0.3 s below -60 dBFS.  Tail: last 0.5 s below -60 dBFS or falling,
  and no voice cut off by the end of the file.
Results go to MIX.check.json; exit status 1 if any check fails.
"""
import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402
import balance  # noqa: E402
import make_audio as mx  # noqa: E402

SR = synth.SR
TOL_MS = 5.0
SEARCH_MS = 10.0
LOW_VOICES = {'thud'}       # below the 400 Hz high-pass; detected full band
ATTACK_MS = 8.0
SAME_S = 0.001              # events this close are one onset on the waveform
HP_ATTACK = synth._sos('highpass', 2600.0, 4)
CLOSE_MS = 25.0             # another onset this near: match the attack only
# An event counts as found on the waveform when its own voice, fitted at the
# found onset, is there at this share of the level it was mixed at.  A voice
# that is missing fits near 0; the limiter and overlapping voices move a
# present one by a few tens of percent at most.
FOUND_LEVEL = (0.5, 1.5)


def dbfs(v):
    return round(float(20 * np.log10(max(float(v), 1e-12))), 1)


def loudnorm_reading(path):
    r = subprocess.run([mx.FFMPEG, '-nostats', '-hide_banner', '-i', path, '-af',
                        'loudnorm=I=-16:TP=-1:print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True, check=True)
    j = json.loads(re.findall(r'\{[^{}]*\}', r.stderr)[-1])
    return float(j['input_i']), float(j['input_tp'])


def locate(mono, mono_hp, events, group, cfg, gains, spin, close, env):
    """Film-time error (ms) of the event's onset, by cross-correlation, and
    how well the voice is found there.
    When another voice starts within CLOSE_MS of this one ("close"), only
    the voice's first ATTACK_MS above 2.6 kHz is matched: that part is the
    event's own noise burst or attack and differs from its neighbours', so a
    near-identical tick 5 ms away cannot take the match.  Otherwise the
    whole voice is matched, even where it overlaps the tail of an earlier
    one (relation lines 0.2 s apart).  Events at the same instant (group)
    make one onset on the waveform, so their voices are matched together.

    Returns (onset_ms, lag_ms, level, corr): level is the voice's amplitude
    fitted at the found position over the amplitude it was mixed at (the
    output gain there, normalisation x limiter), about 1 where the voice is on the waveform and about
    0 where it is not; corr is the correlation coefficient there."""
    e = events[group[0]]
    vs = [mx.voice_of(events[i], i, cfg['seed'], gains[i], spin, cfg.get('category_db')).sum(axis=1) for i in group]
    v = np.zeros(max(len(u) for u in vs))
    for u in vs:
        v[:len(u)] += u
    rise = 0.0 if e['kind'] in synth.MOTION_VOICES else synth.onset_ms(v)
    sig = mono
    if close and e['kind'] not in synth.MOTION_VOICES:
        v = signal.sosfilt(HP_ATTACK, v)[:int(round(ATTACK_MS * SR / 1000))]
        sig = mono_hp
    i0 = int(round((e['t'] - cfg['start']) * SR))
    w = int(round(SEARCH_MS * SR / 1000))
    a = max(0, i0 - w)
    seg = sig[a:i0 + len(v) + w]
    if len(seg) < len(v) + 1:
        return None, None, 0.0, 0.0
    c = signal.correlate(seg, v, mode='valid')
    k = int(np.argmax(c))
    lag = k + a - i0
    win = seg[k:k + len(v)]
    vv = float(v @ v)
    # Output gain the voice got where it was found: normalisation x limiter.
    g = env[k + a:k + a + len(v)]
    expected = float(np.average(g, weights=v[:len(g)] ** 2 + 1e-30)) if len(g) else synth.db(cfg['gain_db'])
    level = float(c[k]) / vv / expected
    corr = float(c[k]) / np.sqrt(vv * float(win @ win) + 1e-30)
    return 1000.0 * lag / SR + rise, 1000.0 * lag / SR, level, corr


def envelope(mono, highpass):
    """Hilbert envelope, 0.25 ms smoothing; high-passed at 400 Hz if asked."""
    if highpass:
        mono = signal.sosfiltfilt(synth._sos('highpass', 400.0, 4), mono)
    env = np.abs(signal.hilbert(mono))
    return np.convolve(env, np.ones(12) / 12, mode='same')


def detect(env, e, start):
    """Film-time error (ms) of the onset found on the envelope, or None."""
    i = int(round((e['t'] - start) * SR))
    ms = lambda x: int(round(x * SR / 1000))
    if i - ms(25) < 0 or i + ms(40) > len(env):
        return None
    bg = env[i - ms(25):i - ms(5)].max()
    peak = env[i:i + ms(40)].max()
    if peak < 2.0 * bg:
        return None
    th = bg + 0.25 * (peak - bg)
    j = i - ms(20) + int(np.argmax(env[i - ms(20):i + ms(40)] >= th))
    return 1000.0 * (j - i) / SR


def voice_lengths(events, cfg, gains, spin):
    """Seconds each event's voice lasts (to -40 dB of its peak)."""
    out = []
    for idx, e in enumerate(events):
        if e['kind'] in synth.MOTION_VOICES:
            out.append(float(e.get('dur', 0.0)))
            continue
        m = np.abs(mx.voice_of(e, idx, cfg['seed'], gains[idx], spin, cfg.get('category_db'))).max(axis=1)
        out.append(float(np.nonzero(m >= synth.db(-40.0) * m.max())[0][-1]) / SR)
    return np.array(out)


def onsets(x, cfg, env):
    """One row per event inside the file.  "dense": another hit voice is
    sounding from 25 ms before the event to 40 ms after it."""
    events = mx.load_events(cfg['events'])
    spin = mx.load_spin(cfg['spin'])
    gains, _ = mx.event_gains(events)
    mono = x.sum(axis=1)
    mono_hp = signal.sosfilt(HP_ATTACK, mono)
    env_hp, env_full = envelope(mono, True), envelope(mono, False)
    times = np.array([e['t'] for e in events])
    hits = np.array([e['kind'] not in synth.MOTION_VOICES for e in events])
    ends = times + voice_lengths(events, cfg, gains, spin)
    rows, end = [], cfg['start'] + len(x) / SR
    for idx, e in enumerate(events):
        if not cfg['start'] <= e['t'] < end:
            continue
        same = np.abs(times - e['t']) < SAME_S
        group = [idx] if e['kind'] in synth.MOTION_VOICES else list(np.nonzero(same & hits)[0])
        others = hits & ~same & (times < e['t'] + 0.040) & (ends > e['t'] - 0.025)
        dense = bool(others.any())
        close = bool((hits & ~same & (np.abs(times - e['t']) * 1000 < CLOSE_MS)).any())
        loc, lag, level, corr = locate(mono, mono_hp, events, group, cfg, gains, spin, close, env)
        det = None
        if e['kind'] not in synth.MOTION_VOICES and not dense:
            det = detect(env_full if e['kind'] in LOW_VOICES else env_hp, e, cfg['start'])
        rows.append({'t': e['t'], 'kind': e['kind'], 'what': e.get('what', ''),
                     'locate_ms': None if loc is None else round(loc, 2),
                     'lag_ms': None if lag is None else round(lag, 2),
                     'detect_ms': None if det is None else round(det, 2),
                     'level': round(level, 3), 'corr': round(corr, 3),
                     'dense': dense, 'close': close, 'same_instant': len(group)})
    return rows


def run(path, expect_samples=None):
    """All checks on PATH (reads PATH.mix.json); writes PATH.check.json and
    returns (ok, results) with one entry per check."""
    with open(os.path.splitext(path)[0] + '.mix.json', encoding='utf-8') as f:
        cfg = json.load(f)
    x, rate, bits = mx.read_wav(path)
    res, ok = {}, {}

    ok['format'] = rate == 48000 and bits == 24 and x.shape[1] == 2
    res['format'] = f'{rate} Hz, {bits}-bit, {x.shape[1]} ch, {len(x) / rate:.3f} s'
    if expect_samples is not None:
        ok['samples'] = len(x) == expect_samples
        res['samples'] = {'samples': len(x), 'expected': expect_samples}

    built = balance.rebuild(mx, cfg, x)       # stems, output gain, rebuild error
    rows = onsets(x, cfg, built[1])
    worst = lambda key, rs: max((abs(r[key]) for r in rs if r[key] is not None), default=0.0)
    missing = [r for r in rows if r['locate_ms'] is None]
    hit_rows = [r for r in rows if r['kind'] not in synth.MOTION_VOICES]
    motion = [r for r in rows if r['kind'] in synth.MOTION_VOICES]
    detected = [r for r in rows if r['detect_ms'] is not None]
    alone = [r for r in hit_rows if not r['dense']]
    late = [r for r in rows if (r['locate_ms'] is not None and abs(r['locate_ms']) > TOL_MS)
            or (r['detect_ms'] is not None and abs(r['detect_ms']) > TOL_MS)]
    ok['onsets'] = not missing and not late
    res['onsets'] = {
        'events': len(rows), 'max_locate_ms': round(worst('locate_ms', hit_rows), 2),
        'max_motion_lag_ms': round(worst('lag_ms', motion), 2),
        'detected': len(detected), 'isolated': len(alone),
        'max_detect_ms': round(worst('detect_ms', detected), 2),
        'undetected_isolated': [(r['t'], r['kind']) for r in alone if r['detect_ms'] is None],
        'over_5ms': [(r['t'], r['kind'], r['locate_ms'], r['detect_ms']) for r in late],
    }

    # Every event inside the file is on the waveform: its own voice is found at
    # its onset at the level it was mixed at, and no event fell outside the file.
    in_file = len([e for e in mx.load_events(cfg['events']) if cfg['start'] <= e['t'] < cfg['start'] + len(x) / SR])
    lost = [r for r in rows if r['locate_ms'] is None or not FOUND_LEVEL[0] <= r['level'] <= FOUND_LEVEL[1]]
    ok['found'] = not lost and len(rows) == in_file == cfg['count'] and not cfg.get('skipped')
    levels = [r['level'] for r in rows]
    res['found'] = {'events': len(rows), 'in_table': cfg['count'],
                    'level_min': round(min(levels), 3) if levels else None,
                    'level_max': round(max(levels), 3) if levels else None,
                    'not_found': [(r['t'], r['kind'], r['level']) for r in lost],
                    'outside_file': cfg.get('skipped', [])}

    lufs, tp = mx.ebur128(path)
    ln_i, ln_tp = loudnorm_reading(path)
    target = cfg.get('target_lufs', mx.TARGET_LUFS)
    # Always judged against the spec's -16 LUFS, whatever the mix aimed at.
    ok['loudness'] = abs(lufs - mx.TARGET_LUFS) <= 0.5
    ok['true_peak'] = tp <= mx.MAX_DBTP
    res['loudness'] = {'ebur128_lufs': lufs, 'loudnorm_lufs': ln_i, 'target_lufs': target,
                       'gain_capped': cfg.get('capped', False)}
    res['true_peak'] = {'ebur128_dbtp': tp, 'loudnorm_dbtp': ln_tp}

    # 声音任务说明 8.2: each category's momentary maximum against T, and the
    # mix's own momentary maximum away from the thud.
    rows_b, T, peak, rebuilt = balance.report(mx, cfg, x, built)
    ok['balance'] = bool(rows_b) and all(r['ok'] for r in rows_b) and rebuilt < 1e-4
    res['balance'] = {'T': None if T is None else round(T, 1), 'stems_rebuild_error': float(f'{rebuilt:.1e}'),
                      'rows': rows_b}
    ok['mix_peak'] = peak['ok']
    res['mix_peak'] = peak

    full = 1.0 - 1.5 / (1 << 23)
    clipped = int((np.abs(x) >= full).sum())
    ok['clipping'] = clipped == 0
    res['clipping'] = {'clipped_samples': clipped, 'sample_peak_dbfs': dbfs(np.abs(x).max())}
    mean = np.abs(x.mean(axis=0))
    ok['dc'] = bool(mean.max() < 0.001)
    res['dc'] = {'abs_mean': [float(f'{m:.2e}') for m in mean]}

    head = np.abs(x[:int(0.3 * rate)]).max()
    ok['head'] = head < synth.db(-60.0)
    res['head'] = {'peak_0_0.3s_dbfs': dbfs(head)}
    tail = np.abs(x[-int(0.5 * rate):]).max(axis=1)
    q = np.array_split(tail, 5)
    falling = all(q[i + 1].max() <= q[i].max() + 1e-9 for i in range(4))
    cut = cfg.get('cut', [])
    ok['tail'] = (tail.max() < synth.db(-60.0) or falling) and not cut and np.abs(x[-1]).max() < synth.db(-60.0)
    res['tail'] = {'peak_last_0.5s_dbfs': dbfs(tail.max()), 'silent': bool(tail.max() < synth.db(-60.0)),
                   'falling': falling, 'last_sample_dbfs': dbfs(np.abs(x[-1]).max()), 'cut_off_voices': cut}

    ok = {k: bool(v) for k, v in ok.items()}
    out = {'file': os.path.abspath(path), 'pass': all(ok.values()), 'ok': ok, 'results': res}
    with open(os.path.splitext(path)[0] + '.check.json', 'w', encoding='utf-8') as f:
        json.dump(dict(out, rows=rows), f, ensure_ascii=False, indent=1)
    return ok, res


def main():
    ap = argparse.ArgumentParser(description='Section five checks on a make_audio.py WAV.')
    ap.add_argument('wav')
    ap.add_argument('--samples', type=int, help='exact sample count the file must have')
    a = ap.parse_args()
    ok, res = run(a.wav, a.samples)
    for k in ok:
        print(f"{'PASS' if ok[k] else 'FAIL'}  {k:10s} {json.dumps(res[k], ensure_ascii=False)}")
    sys.exit(0 if all(ok.values()) else 1)


if __name__ == '__main__':
    main()
