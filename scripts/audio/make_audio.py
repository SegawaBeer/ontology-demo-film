"""Mix event tables into the film's effects track (声音任务说明.md, 二 and 四).

    make_audio.py OUT.wav EVENTS.json [EVENTS.json ...]
                  [--spin MODULE:FUNC] [--start S] [--end S] [--seed N]

Each event file is a JSON list of {t, kind, gain} with t in film seconds.
Optional fields: "src" ('3d' | 'graph' | 'dialog') picks the pan, "pan"
overrides it, "dur" gives the length of a slide or spin.  A spin event
({t, kind: 'spin', dur}) plays the rotor hum over [t, t + dur], following
--spin, a function MODULE:FUNC in this folder that returns rev/s for an array
of film times (0 when stopped).  If the module has FULL_RPS, that speed plays
at the spin voice's full level.

The output covers film time --start to --end (default: last event + 2 s),
gets the short shared reverb, is normalised to -16 LUFS integrated with true
peak <= -1 dBTP (look-ahead true-peak limiter where needed; measured with
ffmpeg ebur128), and is written as 48 kHz 24-bit stereo WAV.
"""
import argparse
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import wave

import numpy as np
from scipy import ndimage, signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402

FFMPEG = '/opt/homebrew/bin/ffmpeg'
SR = synth.SR
TARGET_LUFS = -16.0
MAX_DBTP = -1.0
CEILING_DBTP = -1.4                 # limiter ceiling, margin under -1 dBTP
PAN = {'3d': 0.0, 'graph': 0.35, 'dialog': -0.35}
# Where a kind is heard when the event does not say (src / pan).
DEFAULT_SRC = {'path': 'graph', 'type': 'dialog', 'line': 'dialog'}
DENSITY_WINDOW = 0.050
DENSITY_MAX = 4


def load_events(paths):
    """All events from the files, stable-sorted by time.  A spin event
    ({t, kind: 'spin', gain, dur}) marks a stretch where the spin voice
    follows the --spin speed function."""
    events = []
    for p in paths:
        with open(p, encoding='utf-8') as f:
            for e in json.load(f):
                if e['kind'] not in synth.VOICES:
                    raise SystemExit(f'{p}: unknown kind {e["kind"]!r}')
                if e['kind'] == 'spin' and 'dur' not in e:
                    raise SystemExit(f'{p}: a spin event needs dur')
                events.append(dict(e, t=float(e['t']), gain=float(e.get('gain', 1.0))))
    events.sort(key=lambda e: e['t'])
    return events


def density_gains(times):
    """1/sqrt(n) for an event with n events (itself included) in the 50 ms
    up to it, when n > 4; 1 otherwise."""
    times = np.asarray(times, dtype=np.float64)
    lo = np.searchsorted(times, times - DENSITY_WINDOW + 1e-9, side='left')
    n = np.arange(len(times)) + 1 - lo
    return np.where(n > DENSITY_MAX, 1.0 / np.sqrt(n), 1.0), n


def pan_of(e):
    if 'pan' in e:
        return float(e['pan'])
    return PAN[e.get('src') or DEFAULT_SRC.get(e['kind'], '3d')]


def load_spin(spec):
    """'MODULE:FUNC' in this folder -> (speed function, full-level rev/s)."""
    if not spec:
        return None
    mod, func = spec.split(':')
    m = importlib.import_module(mod)
    return getattr(m, func), getattr(m, 'FULL_RPS', None)


def voice_of(e, idx, seed, gain=1.0, spin=None):
    """The dry stereo voice of event number idx (events in load_events order).
    Each event draws from its own generator, so check_audio can rebuild it."""
    rng = np.random.default_rng([seed, idx])
    g, pan = e['gain'] * gain, pan_of(e)
    if e['kind'] == 'spin':
        if spin is None:
            raise SystemExit('spin events need --spin')
        speed, full = spin
        return synth.spin(speed, e['t'], float(e['dur']), gain=g, pan=pan, rng=rng, full=full)
    kw = {'dur': float(e['dur'])} if e['kind'] == 'slide' and 'dur' in e else {}
    return synth.VOICES[e['kind']](gain=g, pan=pan, rng=rng, **kw)


def event_gains(events):
    """Density gain per event (spin stretches are not counted) and how many
    events were turned down."""
    hits = [i for i, e in enumerate(events) if e['kind'] != 'spin']
    dens, counts = density_gains([events[i]['t'] for i in hits])
    gains = [1.0] * len(events)
    for i, g in zip(hits, dens):
        gains[i] = float(g)
    return gains, int((counts > DENSITY_MAX).sum())


def render(events, start, end, spin=None, seed=0):
    n = int(round((end - start) * SR))
    out = np.zeros((n, 2))
    gains, thinned = event_gains(events)
    skipped, cut = [], []
    for idx, e in enumerate(events):
        i0 = int(round((e['t'] - start) * SR))
        if i0 < 0 or i0 >= n:
            skipped.append(e)
            continue
        x = voice_of(e, idx, seed, gains[idx], spin)
        m = min(len(x), n - i0)
        if m < len(x) and np.abs(x[m:]).max() > synth.db(-80.0):
            cut.append(e)
        out[i0:i0 + m] += x[:m]
    return out, {'skipped': skipped, 'cut': cut, 'thinned': thinned}



def reverb(x, seed=1000, predelay=0.010, t60=0.8, wet_db=-18.0):
    """Short shared reverb: decaying stereo noise IR (unit energy per
    channel), 10 ms pre-delay, -60 dB after 0.8 s, mixed in at -18 dB."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(round((t60 + 0.05) * SR))) / SR
    env = np.exp(-synth.LN1000 * t / t60) * synth._rise(t, 0.002)
    ir = signal.sosfilt(synth._sos('lowpass', 6000.0, 2), rng.standard_normal((len(t), 2)), axis=0)
    ir *= env[:, None]
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    ir = np.concatenate([np.zeros((int(round(predelay * SR)), 2)), ir])
    wet = signal.oaconvolve(x, ir, axes=0)[:len(x)]
    return x + synth.db(wet_db) * wet


# ---- loudness ----------------------------------------------------------------

def write_wav(path, x, bits=24):
    """Stereo float in [-1, 1) -> 24-bit PCM WAV, or 32-bit float if bits == 32."""
    x = np.asarray(x, dtype=np.float64)
    if bits == 32:
        from scipy.io import wavfile
        wavfile.write(path, SR, x.astype(np.float32))
        return
    full = 2 ** (bits - 1)
    q = np.clip(np.round(x * (full - 1)), -full, full - 1).astype('<i4')
    raw = q.view(np.uint8).reshape(-1, 4)[:, :bits // 8].tobytes()
    with wave.open(path, 'wb') as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(bits // 8)
        w.setframerate(SR)
        w.writeframes(raw)


def read_wav(path):
    """24-bit PCM WAV -> (float array (n, channels) in [-1, 1), rate, bits)."""
    with wave.open(path, 'rb') as w:
        ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.uint8)
    if width != 3:
        raise SystemExit(f'{path}: {8 * width}-bit, expected 24-bit')
    b = raw.reshape(-1, 3).astype(np.int32)
    q = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
    q = np.where(q >= 1 << 23, q - (1 << 24), q)
    return q.reshape(-1, ch) / float((1 << 23) - 1), rate, 8 * width


def ebur128(path):
    """Integrated loudness (LUFS) and true peak (dBTP) by ffmpeg's ebur128."""
    r = subprocess.run([FFMPEG, '-nostats', '-hide_banner', '-i', path, '-af',
                        'ebur128=peak=true:framelog=quiet', '-f', 'null', '-'],
                       capture_output=True, text=True, check=True)
    lufs = float(re.findall(r'I:\s+(-?[\d.]+|-inf) LUFS', r.stderr)[-1])
    peak = re.findall(r'Peak:\s+(-?[\d.]+|-inf) dBFS', r.stderr)[-1]
    return lufs, float(peak)


def measure(x):
    fd, tmp = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    try:
        write_wav(tmp, x, bits=32)
        return ebur128(tmp)
    finally:
        os.remove(tmp)


def true_peak_env(x):
    """Per-sample peak of the 4x oversampled signal (both channels)."""
    up = np.abs(signal.resample_poly(x, 4, 1, axis=0)).max(axis=1)
    n = len(x)
    up = np.concatenate([up[:4 * n], np.zeros(max(0, 4 * n - len(up)))])
    return np.maximum(up.reshape(n, 4).max(axis=1), np.abs(x).max(axis=1))


def limit(x, ceiling_db=CEILING_DBTP, window=0.010):
    """Look-ahead true-peak limiter.  The gain dips smoothly over `window`
    on each side of any sample whose oversampled peak is above the ceiling
    and is never above ceiling / peak at that sample.  Returns (y, max gain
    reduction dB, seconds with any reduction)."""
    c = synth.db(ceiling_db)
    w = int(round(window * SR))
    total = np.ones(len(x))
    y = x
    for _ in range(4):
        r = np.minimum(1.0, c / np.maximum(true_peak_env(y), 1e-12))
        if r.min() >= 1.0:
            break
        g = ndimage.uniform_filter1d(ndimage.minimum_filter1d(r, 2 * w + 1, mode='nearest'),
                                     w + 1, mode='nearest')
        g = np.minimum(g, r)
        total *= g
        y = x * total[:, None]
    return y, -20 * np.log10(total.min()), float((total < 0.9999).sum()) / SR


def normalise(x, target=TARGET_LUFS):
    """Gain to the target integrated loudness, limiting true peaks; repeat
    until the measured loudness is within 0.05 LU."""
    lufs, _ = measure(x)
    gain_db = target - lufs
    for _ in range(8):
        y, gr, gr_s = limit(x * synth.db(gain_db))
        lufs, peak = measure(y)
        if abs(lufs - target) < 0.05:
            break
        gain_db += target - lufs
    return y, {'gain_db': round(gain_db, 2), 'limiter_max_db': round(gr, 2),
               'limiter_seconds': round(gr_s, 3), 'lufs_float': lufs, 'dbtp_float': peak}


# ---- main ----------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('out')
    ap.add_argument('events', nargs='+')
    ap.add_argument('--spin', help='MODULE:FUNC returning rotor rev/s')
    ap.add_argument('--start', type=float, default=0.0)
    ap.add_argument('--end', type=float)
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args(argv)

    events = load_events(a.events)
    spin = load_spin(a.spin)
    end = a.end if a.end is not None else max(e['t'] for e in events) + 2.0
    dry, info = render(events, a.start, end, spin, a.seed)
    y, norm = normalise(reverb(dry))
    write_wav(a.out, y)
    lufs, peak = ebur128(a.out)

    report = {
        'events': [os.path.abspath(p) for p in a.events], 'spin': a.spin, 'seed': a.seed,
        'start': a.start, 'end': end, 'count': len(events),
        'by_kind': {k: sum(e['kind'] == k for e in events) for k in synth.VOICES if any(e['kind'] == k for e in events)},
        'thinned': info['thinned'],
        'skipped': [(e['t'], e['kind']) for e in info['skipped']],
        'cut': [(e['t'], e['kind']) for e in info['cut']],
        **norm, 'lufs': lufs, 'dbtp': peak,
    }
    with open(os.path.splitext(a.out)[0] + '.mix.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in report.items() if k != 'events'}, ensure_ascii=False))
    if peak > MAX_DBTP or abs(lufs - TARGET_LUFS) > 0.5:
        raise SystemExit(f'loudness off target: {lufs} LUFS, {peak} dBTP')


if __name__ == '__main__':
    main()
