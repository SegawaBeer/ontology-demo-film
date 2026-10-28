"""Voices for the demo film's sound effects (任务说明/声音任务说明.md, section 二).

Each voice returns a float64 stereo array, shape (n, 2), at 48 kHz.  Sample 0
is the event time and nothing sounds before it, so a voice placed at an
event's sample starts on the event.  At gain 1 and centre pan a voice peaks
at LEVELS[kind] dBFS (before the final loudness normalisation).

    python synth.py      # self-test of every voice
"""
import numpy as np
from scipy import signal

SR = 48000

# Peak level at gain 1, dBFS.  Entries marked * are not given in the spec.
LEVELS = {
    'tone': -24.0,      # *
    'tick': -26.0,      # * (each tick then varies by +-2 dB)
    'thud': -21.0,      # *  (these four are set so the opening needs no limiting)
    'spin': -30.0,      # * at full speed
    'type': -30.0,      # each key then varies by +-3 dB
    'line': -24.0,
    'tick-num': -22.0,
    'path': -30.0,
    'slide': -28.0,
    'part': -26.0,
    'swap': -24.0,
    'alert': -18.0,
}

# Spin tone frequency = blades x rev/s x SPIN_PITCH.  Taken literally
# (SPIN_PITCH = 1) the opening rotor, one turn in 4.4 s, gives 3.6 Hz, which
# nobody can hear; 15.125 puts full speed on 55 Hz, the pitch of the thud.
SPIN_BLADES = 16
SPIN_PITCH = 15.125
SPIN_NOISE_CUT_HZ = 150.0
SPIN_NOISE_CUT_DB = 6.0

LN1000 = np.log(1000.0)          # exp(-LN1000 * t / t60) is -60 dB at t60


def db(x):
    return 10.0 ** (x / 20.0)


def _n(seconds):
    return int(round(seconds * SR))


def _rise(t, attack):
    """Raised-cosine rise from 0 (t <= 0) to 1 (t >= attack)."""
    if attack <= 0:
        return (t >= 0).astype(np.float64)
    return 0.5 - 0.5 * np.cos(np.pi * np.clip(t, 0.0, attack) / attack)


def _gate(t, attack, length, release):
    """Rise over `attack`, stay at 1, fall over `release`, 0 from `length` on."""
    u = np.clip((t - (length - release)) / release, 0.0, 1.0)
    return _rise(t, attack) * (0.5 + 0.5 * np.cos(np.pi * u))


def _ad(attack, t60, hold=0.0, pad=0.01):
    """Time axis and envelope: rise over `attack`, hold, decay to -60 dB in `t60`."""
    t = np.arange(_n(attack + hold + t60 + pad)) / SR
    fall = np.exp(-LN1000 * np.maximum(0.0, t - attack - hold) / t60)
    return t, _rise(t, attack) * fall


def _fade_end(x, seconds=0.003):
    """Cosine fade over the last few ms so a voice never ends on a step."""
    k = min(len(x), _n(seconds))
    if k > 0:
        x[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(1, k + 1) / k)
    return x


def _sos(kind, freq, order=4):
    return signal.butter(order, freq, btype=kind, fs=SR, output='sos')


def _pink(n, rng):
    """Pink noise (power falling 3 dB per octave), unit RMS."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    spec /= np.sqrt(np.maximum(f, 20.0))
    spec[0] = 0.0
    x = np.fft.irfft(spec, n)
    return x / (np.sqrt(np.mean(x ** 2)) + 1e-12)


def _cut_below(x, f0, cut_db, width_oct=0.5):
    """x with everything below f0 turned down by cut_db (linear-phase, in the
    frequency domain), rising back to 0 dB over width_oct octaves above f0.
    Meant for stationary noise, where wrapping round the ends does not show."""
    n = len(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    u = np.clip(np.log2(np.maximum(f, 1e-9) / f0) / width_oct, 0.0, 1.0)
    g = db(-cut_db * (0.5 + 0.5 * np.cos(np.pi * u)))
    return np.fft.irfft(np.fft.rfft(x) * g, n)


def _rng(rng):
    return rng if rng is not None else np.random.default_rng(0)


def pan_gains(p):
    """Constant-power pan: -1 left, 0 centre (both channels at unity), +1 right."""
    a = (float(np.clip(p, -1.0, 1.0)) + 1.0) * np.pi / 4.0
    return np.sqrt(2.0) * np.cos(a), np.sqrt(2.0) * np.sin(a)


def _out(x, kind, gain, pan, scale=None):
    """Scale a mono voice to its level and spread it to stereo."""
    x = _fade_end(np.array(x, dtype=np.float64))
    peak = np.max(np.abs(x)) if scale is None else scale
    x *= db(LEVELS[kind]) * gain / max(peak, 1e-12)
    left, right = pan_gains(pan)
    return np.stack([x * left, x * right], axis=1)


# ---- voices ------------------------------------------------------------------
# "Decay N s" in the spec is read as the time to fall to -60 dB.

def _bell(t, f, second, attack, t60):
    """Sine at f plus its octave `second` dB down, attack then exponential decay."""
    env = _rise(t, attack) * np.exp(-LN1000 * np.maximum(0.0, t - attack) / t60)
    return env * (np.sin(2 * np.pi * f * t) + db(second) * np.sin(4 * np.pi * f * t))


def tone(gain=1.0, pan=0.0, rng=None):
    """660 Hz + 1320 Hz (-14 dB), 8 ms attack, 1.6 s decay.  The light reverb
    is the mix's shared reverb."""
    t = np.arange(_n(1.62)) / SR
    return _out(_bell(t, 660.0, -14.0, 0.008, 1.6), 'tone', gain, pan)


def tick(gain=1.0, pan=0.0, rng=None):
    """4 ms white-noise burst through 3-6 kHz plus a 2.2 kHz sine decaying in
    20 ms; pitch +-3 % and level +-2 dB at random on every call."""
    rng = _rng(rng)
    p = 1.0 + rng.uniform(-0.03, 0.03)
    level = db(rng.uniform(-2.0, 2.0))
    t = np.arange(_n(0.03)) / SR
    burst = rng.standard_normal(len(t)) * _gate(t, 0.0, 0.004, 0.0005)
    burst = signal.sosfilt(_sos('bandpass', (3000.0 * p, 6000.0 * p), 2), burst)
    ping = np.sin(2 * np.pi * 2200.0 * p * t) * np.exp(-LN1000 * t / 0.020)
    return _out(burst / np.max(np.abs(burst)) + ping, 'tick', gain * level, pan)


def thud(gain=1.0, pan=0.0, rng=None):
    """55 Hz + 110 Hz (-10 dB), 5 ms attack, 0.9 s decay, plus 60 ms of noise
    low-passed at 200 Hz."""
    rng = _rng(rng)
    t = np.arange(_n(0.92)) / SR
    env = _rise(t, 0.005) * np.exp(-LN1000 * np.maximum(0.0, t - 0.005) / 0.9)
    body = env * (np.sin(2 * np.pi * 55.0 * t) + db(-10.0) * np.sin(2 * np.pi * 110.0 * t))
    noise = rng.standard_normal(len(t)) * np.exp(-LN1000 * t / 0.06) * (t < 0.06)
    noise = signal.sosfilt(_sos('lowpass', 200.0, 4), noise)
    noise *= db(-6.0) / np.max(np.abs(noise))
    return _out(body + noise, 'thud', gain, pan)


def _spin_scale():
    ph = np.linspace(0.0, 2 * np.pi, 20001)
    return float(np.max(np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.33 * np.sin(3 * ph)))


def spin(speed, t0, dur, gain=1.0, pan=0.0, rng=None, full=None):
    """Rotor hum from film time t0 for dur seconds.

    speed(t) gives rev/s for an array of film times.  Fundamental
    SPIN_BLADES x rev/s x SPIN_PITCH with its 2nd and 3rd harmonics, plus pink
    noise below 400 Hz; amplitude is speed / full, so it is 0 when stopped.
    At speed == full the tonal part peaks at LEVELS['spin'].
    """
    rng = _rng(rng)
    n = _n(dur)
    rps = np.maximum(0.0, np.asarray(speed(t0 + np.arange(n) / SR), dtype=np.float64))
    full = full if full else max(float(rps.max()), 1e-9)
    amp = rps / full
    f0 = SPIN_BLADES * SPIN_PITCH * rps
    ph = 2 * np.pi * np.concatenate([[0.0], np.cumsum(f0[:-1])]) / SR
    tonal = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.33 * np.sin(3 * ph)
    noise = signal.sosfilt(_sos('lowpass', 400.0, 4), _pink(n, rng))
    noise /= np.sqrt(np.mean(noise ** 2)) + 1e-12
    # 声音任务说明 8.1: the noise layer a further 6 dB down below 150 Hz, so the
    # rotor sounds like turning rather than rumbling.  Done after the level is
    # set, so the 150-400 Hz part keeps its level.
    noise = _cut_below(noise, SPIN_NOISE_CUT_HZ, SPIN_NOISE_CUT_DB)
    x = amp * (tonal + db(-12.0) * noise)
    return _out(x, 'spin', gain, pan, scale=_spin_scale())


def type_(gain=1.0, pan=0.0, rng=None):
    """1.5 ms noise pulse through 2-5 kHz with a 25 ms decay; level +-3 dB."""
    rng = _rng(rng)
    level = db(rng.uniform(-3.0, 3.0))
    t = np.arange(_n(0.03)) / SR
    env = np.where(t < 0.0015, 1.0, np.exp(-LN1000 * (t - 0.0015) / 0.025))
    x = signal.sosfilt(_sos('bandpass', (2000.0, 5000.0), 2), rng.standard_normal(len(t)) * env)
    return _out(x, 'type', gain * level, pan)


def line(gain=1.0, pan=0.0, rng=None):
    """880 Hz, 3 ms attack, 120 ms decay."""
    t = np.arange(_n(0.125)) / SR
    env = _rise(t, 0.003) * np.exp(-LN1000 * np.maximum(0.0, t - 0.003) / 0.12)
    return _out(env * np.sin(2 * np.pi * 880.0 * t), 'line', gain, pan)


def tick_num(gain=1.0, pan=0.0, rng=None):
    """1320 Hz + 1980 Hz (-8 dB), 90 ms decay."""
    t = np.arange(_n(0.095)) / SR
    env = _rise(t, 0.002) * np.exp(-LN1000 * np.maximum(0.0, t - 0.002) / 0.09)
    x = env * (np.sin(2 * np.pi * 1320.0 * t) + db(-8.0) * np.sin(2 * np.pi * 1980.0 * t))
    return _out(x, 'tick-num', gain, pan)


def path(gain=1.0, pan=0.0, rng=None):
    """Sine gliding 500 -> 720 Hz over 0.25 s, 4 ms fade in, 80 ms fade out."""
    t = np.arange(_n(0.25)) / SR
    f = 500.0 + 220.0 * t / 0.25
    ph = 2 * np.pi * np.cumsum(f) / SR
    return _out(_gate(t, 0.004, 0.25, 0.08) * np.sin(ph), 'path', gain, pan)


def smootherstep_speed(u):
    """Speed of a smootherstep move, 30 u^2 (1-u)^2; peak 1.875 at u = 0.5."""
    u = np.clip(u, 0.0, 1.0)
    return 30.0 * u * u * (1.0 - u) ** 2


def slide(gain=1.0, pan=0.0, rng=None, dur=0.6, speed=None):
    """Pink noise through 300 Hz-2 kHz, amplitude proportional to the move's
    speed.  speed(u), u in [0, 1] over dur, defaults to a smootherstep move."""
    rng = _rng(rng)
    n = _n(dur)
    u = np.arange(n) / max(n - 1, 1)
    v = np.asarray((speed or smootherstep_speed)(u), dtype=np.float64)
    x = signal.sosfilt(_sos('bandpass', (300.0, 2000.0), 2), _pink(n + _n(0.05), rng))[_n(0.05):]
    x /= np.sqrt(np.mean(x ** 2)) + 1e-12
    return _out(x * v / max(v.max(), 1e-12), 'slide', gain, pan)


def part(gain=1.0, pan=0.0, rng=None):
    """Light metal tap: inharmonic sines near 1.7, 2.9, 4.3 kHz, 1 ms attack,
    0.18 s decay (upper partials faster).  Pitch +-2 % and phases at random so
    two parts on the same instant do not add into one louder copy."""
    rng = _rng(rng)
    p = 1.0 + rng.uniform(-0.02, 0.02)
    t = np.arange(_n(0.19)) / SR
    x = np.zeros_like(t)
    for f, a, t60 in ((1700.0, 1.0, 0.18), (2900.0, 0.6, 0.14), (4300.0, 0.4, 0.10)):
        x += a * np.sin(2 * np.pi * f * p * t + rng.uniform(0, 2 * np.pi)) * np.exp(-LN1000 * t / t60)
    return _out(x * _rise(t, 0.001), 'part', gain, pan)


def swap(gain=1.0, pan=0.0, rng=None):
    """Two tones crossfading over 0.5 s: the 660 Hz tone fades out while one a
    fourth higher (880 Hz) fades in, then rings out."""
    t = np.arange(_n(1.3)) / SR
    cross = 0.5 - 0.5 * np.cos(np.pi * np.clip(t / 0.5, 0.0, 1.0))
    a = _bell(t, 660.0, -14.0, 0.008, 1.2) * np.sqrt(1.0 - cross)
    b = _bell(t, 880.0, -14.0, 0.008, 1.2) * np.sqrt(cross)
    return _out(a + b, 'swap', gain, pan)


def alert(gain=1.0, pan=0.0, rng=None):
    """Two 740 Hz beeps of 0.12 s with 0.16 s of silence between them."""
    t = np.arange(_n(0.40)) / SR
    beep = _gate(t, 0.003, 0.12, 0.003) + _gate(t - 0.28, 0.003, 0.12, 0.003)
    return _out(beep * np.sin(2 * np.pi * 740.0 * t), 'alert', gain, pan)


VOICES = {
    'tone': tone, 'tick': tick, 'thud': thud, 'spin': spin, 'type': type_,
    'line': line, 'tick-num': tick_num, 'path': path, 'slide': slide,
    'part': part, 'swap': swap, 'alert': alert,
}

# Voices whose loudness follows a motion curve that starts from rest, so the
# sound fades in with the motion instead of starting with an attack.
MOTION_VOICES = {'spin', 'slide'}


def onset_ms(x, frac=0.1):
    """Milliseconds from sample 0 to the first sample at frac (-20 dB) of the peak."""
    m = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    return 1000.0 * int(np.argmax(m >= frac * m.max())) / SR


def _selftest():
    rng = np.random.default_rng(1)
    full = 1 / 4.4
    for kind, fn in VOICES.items():
        if kind == 'spin':
            x = fn(lambda t: full * smootherstep_speed(np.clip((t - 22.0) / 6.0, 0, 1)) / 1.875,
                   22.0, 6.0, rng=rng, full=full)
        else:
            x = fn(rng=rng)
        assert x.ndim == 2 and x.shape[1] == 2 and np.all(np.isfinite(x)), kind
        peak = 20 * np.log10(np.abs(x).max())
        print(f'{kind:9s} {len(x) / SR:6.3f} s  peak {peak:6.1f} dBFS  '
              f'onset {onset_ms(x):6.2f} ms  ends {20 * np.log10(np.abs(x[-1]).max() + 1e-12):7.1f} dBFS')


if __name__ == '__main__':
    _selftest()
