"""Fan rotor speed for the whole film (声音任务说明.md 7.3), the spin voice's
speed function.

    rotor.py            # runs verify()

rotor_rps(t) is the rotor speed in rev/s at film time t (any array):
- 22.0-28.0, the opening (开头组装动画任务说明.md 21.6): smootherstep up over
  22.0-23.2, cruise to 26.0, then times 1 - smootherstep((t - 26) / 2) to 28.0.
- 103.0-111.0, the ending (主时间轴二任务说明.md 9.5): smootherstep((t - 103) / 2)
  to 105.0, 1 to 105.8, then 1 - smootherstep((t - 105.8) / 5.2) to 111.0.
- 0 at every other time.
Cruise is OMEGA = 360 / 4.4 deg/s; make_audio.py takes it as --spin rotor:rotor_rps
and plays FULL_RPS at the spin voice's full level.  SPIN_EVENTS are the two
spin events that cover the rotor's motion.
"""
import numpy as np

OMEGA = 360 / 4.4                       # deg/s at cruise
FULL_RPS = OMEGA / 360                  # spin voice is at full level here
SPIN_EVENTS = [(22.0, 6.0), (103.0, 8.0)]
TOL_DEG = 0.01


def smootherstep(u):
    u = np.clip(u, 0.0, 1.0)
    return u ** 3 * (u * (6 * u - 15) + 10)


def _I(u):
    """Integral of smootherstep over [0, u], u in [0, 1]."""
    return u ** 6 - 3 * u ** 5 + 2.5 * u ** 4


def speed_factor(t):
    """Rotor speed as a share of cruise."""
    t = np.asarray(t, dtype=np.float64)
    opening = smootherstep((t - 22.0) / 1.2) * (1.0 - smootherstep((t - 26.0) / 2.0))
    ending = smootherstep((t - 103.0) / 2.0) * (1.0 - smootherstep((t - 105.8) / 5.2))
    return np.where((t > 22.0) & (t < 28.0), opening,
                    np.where((t > 103.0) & (t < 111.0), ending, 0.0))


def rotor_rps(t):
    return FULL_RPS * speed_factor(t)


def opening_degrees(t):
    """θ(t) of 21.6 in closed form, to check rotor_rps against the picture."""
    if t <= 22.0:
        return 0.0
    if t >= 28.0:
        return 360.0
    ramp = min(1.0, (t - 22.0) / 1.2)
    cruise = max(0.0, min(t, 26.0) - 23.2)
    ease = (t - 26.0) - 2 * _I((t - 26.0) / 2) if t > 26.0 else 0.0
    return OMEGA * (1.2 * _I(ramp) + cruise + ease)


def _integral_deg(a, b, step=1e-5):
    """Degrees turned over [a, b] by trapezoids on rotor_rps; and the running angle."""
    t = np.arange(a, b + step / 2, step)
    v = 360 * rotor_rps(t)
    return t, np.concatenate([[0.0], np.cumsum((v[1:] + v[:-1]) / 2 * step)])


def verify():
    """Stop unless: the opening part integrates to the 21.6 angle within
    0.01 deg, the ending part turns 360 deg within 0.01 deg, and the rotor is
    still outside the two spin events."""
    t, deg = _integral_deg(21.0, 29.0)
    opening_err = max(abs(np.interp(s, t, deg) - opening_degrees(s)) for s in np.arange(21.5, 28.6, 0.1))
    _, deg = _integral_deg(102.0, 112.0)
    ending = float(deg[-1])
    grid = np.arange(0.0, 120.0, 1e-3)
    inside = np.zeros(len(grid), dtype=bool)
    for t0, dur in SPIN_EVENTS:
        inside |= (grid >= t0) & (grid <= t0 + dur)
    outside = float(np.abs(rotor_rps(grid[~inside])).max())
    res = {'opening_err_deg': float(opening_err), 'ending_deg': ending,
           'ending_err_deg': abs(ending - 360.0), 'outside_max_rps': outside}
    bad = []
    if opening_err > TOL_DEG:
        bad.append(f'opening rotor off the 21.6 angle by {opening_err:.4f} deg')
    if abs(ending - 360.0) > TOL_DEG:
        bad.append(f'ending rotor turns {ending:.4f} deg, not 360')
    if outside > 0.0:
        bad.append(f'rotor moves outside the spin events ({outside} rev/s)')
    if bad:
        raise SystemExit('rotor.py: ' + '; '.join(bad))
    return res


if __name__ == '__main__':
    print(verify())
