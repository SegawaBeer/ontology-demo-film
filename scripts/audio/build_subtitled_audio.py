"""Effects track for the subtitled film (字幕与标题卡任务说明.md 第四节), 135.2 s.

    .venv-audio/bin/python scripts/audio/build_subtitled_audio.py --pages URL_OF_frames.html
                                                                  [--out 音频/全片音效-字幕版.wav]

Seven title cards are cut into the 120 s film as held frames (card k before original
second CARD_AT[k], CARD_DUR[k] long).  The 120 s track is not cut open: that would chop
the tails that ring across a cut.  Instead, at event level:
- every event of the opening table, the film page and the ending page at original time t
  moves to t + (length of the cards cut in at or before t);
- the rotor speed function moves the same way (rotor_rps below; 0 during a card, the
  rotor is still at every cut);
- each card page's own events (one tone at 0.25 s) are added at the card's start;
- then build_film_audio's balance, mix and checks run on the whole 135.2 s.
URL is the frames.html of a build that has frame=card (pages are opened with &play=0).
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CARD_AT = (0.0, 30.0, 33.0, 49.0, 64.0, 86.0, 101.0)
CARD_DUR = (2.4, 2.4, 2.0, 2.0, 2.0, 2.0, 2.4)
CARD_START = tuple(a + sum(CARD_DUR[:k]) for k, a in enumerate(CARD_AT))   # in the new film
ORIGINAL = 120.0
LENGTH = ORIGINAL + sum(CARD_DUR)                                           # 135.2


def offset(t):
    """Card time cut in at or before original time t (a frame at exactly CARD_AT[k] comes after card k)."""
    return sum(d for a, d in zip(CARD_AT, CARD_DUR) if a <= t + 1e-9)


def to_new(t):
    return t + offset(t)


def to_original(T):
    """New film time -> original time; inside card k, the held moment CARD_AT[k]."""
    T = np.asarray(T, dtype=np.float64)
    out = T.copy()
    before = 0.0
    for a, s, d in zip(CARD_AT, CARD_START, CARD_DUR):
        out = np.where(T >= s, np.where(T < s + d, a, T - before - d), out)
        before += d
    return out


import rotor  # noqa: E402

FULL_RPS = rotor.FULL_RPS


def rotor_rps(T):
    """make_audio's --spin function for the new film: the rotor speed at the original moment."""
    return rotor.rotor_rps(to_original(T))


def verify_rotor():
    """The moved rotor turns the same angles as the original, and is still during every card."""
    res = {}
    for name, (a, b) in {'opening': (21.0, 29.0), 'ending': (102.0, 112.0)}.items():
        t = np.arange(to_new(a), to_new(b), 1e-5)
        res[f'{name}_deg'] = float(np.trapezoid(360 * rotor_rps(t), t))
        t0 = np.arange(a, b, 1e-5)
        res[f'{name}_deg_original'] = float(np.trapezoid(360 * rotor.rotor_rps(t0), t0))
    inside = max(float(np.abs(rotor_rps(np.arange(s, s + d, 1e-3))).max()) for s, d in zip(CARD_START, CARD_DUR))
    res['card_max_rps'] = inside
    res['ok'] = (abs(res['opening_deg'] - res['opening_deg_original']) <= rotor.TOL_DEG
                 and abs(res['ending_deg'] - 360.0) <= rotor.TOL_DEG and inside == 0.0)
    return res


def page_events(url, out, tries=3):
    """film_events.py on one page (system python3 with Playwright), into OUT.  A headless load
    now and then never gets ready (it times out); that run is repeated, up to `tries` times."""
    import build_film_audio as bfa
    for k in range(tries):
        r = subprocess.run([bfa.SYSTEM_PY, os.path.join(HERE, 'film_events.py'), url, out], capture_output=True, text=True)
        if r.returncode == 0 or 'TimeoutError' not in r.stderr or k == tries - 1:
            break
        print(f'{url}: page not ready, reading it again', flush=True)
    if r.returncode != 0:
        raise SystemExit(f'film_events.py failed on {url}:\n{r.stdout}{r.stderr}')
    with open(out, encoding='utf-8') as f:
        events = json.load(f)
    with open(os.path.splitext(out)[0] + '.page.json', encoding='utf-8') as f:
        return events, json.load(f)


def build(pages, out, target=None):
    import tempfile
    import balance
    import build_film_audio as bfa
    import check_audio
    import film_events
    import make_audio
    import opening_events
    checks, info = {}, {}

    # 1. rotor (original and moved) and the opening table
    r = rotor.verify()
    checks['rotor_opening'] = r['opening_err_deg'] <= rotor.TOL_DEG
    checks['rotor_ending_360'] = r['ending_err_deg'] <= rotor.TOL_DEG
    moved = verify_rotor()
    info['rotor'] = dict(r, moved=moved)
    if not moved['ok']:
        raise SystemExit(f'moved rotor does not match the original: {moved}')
    opening = opening_events.write()
    checks['opening_table'] = True

    # 2. the three film pages and the seven card pages
    tmp = tempfile.mkdtemp(prefix='sub-audio-')
    q = '&theme=light&play=0'
    film, fpage = page_events(f'{pages}?frame=film{q}', os.path.join(tmp, 'film.json'))
    ending, epage = page_events(f'{pages}?frame=ending{q}', os.path.join(tmp, 'ending.json'))
    if (fpage['start'], fpage['duration'], epage['start'], epage['duration']) != (30, 103, 103, 120):
        raise SystemExit(f'page ranges changed: film {fpage["start"]}-{fpage["duration"]}, ending {epage["start"]}-{epage["duration"]}')
    ending, dropped = bfa.drop_repeats(film, ending)
    # The opening table has the 22 s spin itself; like build_film_audio, only the later ones come from rotor.py.
    spins = [{'t': t0, 'kind': 'spin', 'gain': 1.0, 'src': '3d', 'what': 'rotor', 'dur': d}
             for t0, d in rotor.SPIN_EVENTS if opening_events.END <= t0]
    cards, cpages = [], []
    for k, (s, d) in enumerate(zip(CARD_START, CARD_DUR)):
        evs, cp = page_events(f'{pages}?frame=card&id={k}{q}', os.path.join(tmp, f'card{k}.json'))
        if abs(cp['duration'] - d) > 1e-9 or cp['start'] != 0:
            raise SystemExit(f'card {k} page lasts {cp["start"]}-{cp["duration"]}, want 0-{d}')
        cards += [dict(e, t=s + e['t'], card=k) for e in evs]
        cpages.append(cp)
    subprocess.run(['rm', '-rf', tmp], check=True)
    checks['page_events'] = True
    moved_tables = [(opening, 'opening'), (film, 'film'), (ending, 'ending'), (spins, 'rotor')]
    table = [dict(e, t=to_new(e['t']), t_original=e['t'], **{'from': name}) for evs, name in moved_tables for e in evs]
    table += [dict(e, **{'from': 'card'}) for e in cards]
    table.sort(key=lambda e: e['t'])
    late = [(e['t'], e['kind']) for e in table if not 0.0 <= e['t'] < LENGTH]
    if late:
        raise SystemExit(f'events outside 0-{LENGTH} s: {late[:10]}')
    stem = os.path.splitext(out)[0]
    bfa.write_table(stem + '.events.json', table)
    info['pages'] = [fpage, epage, *cpages]
    info['dropped_repeats'] = [(e['t'], e['kind']) for e in dropped]
    info['cards'] = [{'card': k, 'start': round(s, 3), 'end': round(s + d, 3), 'at_original': a}
                     for k, (a, s, d) in enumerate(zip(CARD_AT, CARD_START, CARD_DUR))]
    info['table'] = {'events': stem + '.events.json', 'count': len(table), 'by_kind': film_events.by_kind(table),
                     'by_part': {name: sum(e['from'] == name for e in table) for name in ('opening', 'film', 'ending', 'rotor', 'card')}}

    # 3. balance and mix, exactly as build_film_audio, over 0-135.2 s with the moved rotor
    spin_spec = 'build_subtitled_audio:rotor_rps'
    samples = int(round(LENGTH * make_audio.SR))
    events = make_audio.load_events([stem + '.events.json'])
    st = balance.stems(make_audio, events, 0.0, LENGTH, make_audio.load_spin(spin_spec), 0)
    cat_db, fit = balance.fit_mix(make_audio, st, target, balance.CLEAN_LIMIT_DB)
    del st
    info['balance_fit'] = dict(fit, category_db=cat_db, target_lufs=target, max_limit_db=balance.CLEAN_LIMIT_DB)
    mix = make_audio.mix([stem + '.events.json'], out, spin_spec, 0.0, LENGTH, 0, cat_db=cat_db, target=target,
                         max_limit_db=balance.CLEAN_LIMIT_DB, start_gain_db=fit.get('gain_db'))
    info['mix'] = {k: v for k, v in mix.items() if k != 'events'}

    # 4. the same checks, samples for 135.2 s
    ok, res = check_audio.run(out, samples)
    checks.update(ok)
    info['check'] = res
    result = {'out': out, 'end': LENGTH, 'samples': samples, 'passed': sum(checks.values()),
              'total': len(checks), 'checks': checks, **info}
    with open(stem + '.build.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return result


def main():
    import opening_events
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pages', required=True, help='frames.html of a build with frame=card')
    ap.add_argument('--out', default=f'{opening_events.ROOT}/音频/全片音效-字幕版.wav')
    a = ap.parse_args()
    r = build(a.pages, os.path.abspath(a.out))
    for k, v in r['checks'].items():
        detail = r['check'].get(k, '')
        print(f"{'PASS' if v else 'FAIL'}  {k:16s} {json.dumps(detail, ensure_ascii=False)[:300]}")
    print(f"{r['passed']}/{r['total']} checks passed; {r['table']['count']} events "
          f"{json.dumps(r['table']['by_part'])}; {r['samples']} samples -> {r['out']}")
    sys.exit(0 if r['passed'] == r['total'] else 1)


if __name__ == '__main__':
    main()
