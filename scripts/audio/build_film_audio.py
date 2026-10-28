"""One command for the film's effects track (声音任务说明.md 7.5).

    .venv-audio/bin/python scripts/audio/build_film_audio.py --film URL [--ending URL]
                                                            [--out 音频/全片音效.wav]

1. Rebuilds the opening table 0-30 s (opening_events.py, checked against the
   opening picture code) and checks the rotor speed (rotor.py).
2. Reads the film page's window.__events (film_events.py, run with the system
   python3 that has Playwright; the page must be served and the URL carry
   &play=0); with --ending also the ending page's, and drops the ending
   events that repeat a film event (same kind, same time within 1 ms).
   Adds the rotor's spin events after 30 s.  Everything goes into one table,
   OUT.events.json.
3. Balances the categories against the 21.9 s thud (balance.py, 声音任务说明
   8.1), synthesises and mixes (make_audio.py) from 0 to the last page's
   __duration: 120 s for the whole film, 5,760,000 samples.  The output gain
   is the one at which the true-peak limiter takes 3 dB off the thud's peak
   and never more anywhere (九.1); the integrated loudness follows from the
   table (九.2 allows -23 to -15 LUFS).
4. Runs every check (check_audio.py plus the samples and found checks of 7.5
   the balance and mix-peak checks of 8.2, the limiter and small-speaker
   checks of 九) and writes OUT.mix.json,
   OUT.check.json and OUT.build.json.

The output must be the full 120 s unless --out names another file (for
example 音频/全片音效-0-64秒.wav from the 30-64 s page).  Exit status 1 if any
check fails.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_audio  # noqa: E402
import balance  # noqa: E402
import film_events  # noqa: E402
import make_audio  # noqa: E402
import opening_events  # noqa: E402
import rotor  # noqa: E402

ROOT = opening_events.ROOT
DEFAULT_OUT = f'{ROOT}/音频/全片音效.wav'
SYSTEM_PY = '/opt/homebrew/bin/python3'          # has Playwright, no numpy
FILM_LENGTH = 120.0
SAME_MS = 1.0


def page_table(url):
    """Run film_events.py on the page; returns (events, page record)."""
    out = film_events.default_out(url)
    r = subprocess.run([SYSTEM_PY, os.path.join(HERE, 'film_events.py'), url, out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f'film_events.py failed on {url}:\n{r.stdout}{r.stderr}')
    with open(out, encoding='utf-8') as f:
        events = json.load(f)
    with open(os.path.splitext(out)[0] + '.page.json', encoding='utf-8') as f:
        page = json.load(f)
    return events, page


def drop_repeats(film, ending):
    """Ending events minus those that repeat a film event: same kind and the
    same time within SAME_MS.  Each film event cancels at most one."""
    used = [False] * len(film)
    keep, dropped = [], []
    for e in ending:
        hit = next((i for i, f in enumerate(film) if not used[i] and f['kind'] == e['kind']
                    and abs(f['t'] - e['t']) * 1000 <= SAME_MS), None)
        if hit is None:
            keep.append(e)
        else:
            used[hit] = True
            dropped.append(e)
    return keep, dropped


def write_table(path, events):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('[\n' + ',\n'.join(json.dumps(e, ensure_ascii=False) for e in events) + '\n]\n')


def build(film_url, ending_url=None, out=None, target=None,
          max_limit_db=balance.CLEAN_LIMIT_DB):
    checks, info = {}, {}

    # 1. rotor and opening table
    r = rotor.verify()                           # stops if either integral is off
    checks['rotor_opening'] = r['opening_err_deg'] <= rotor.TOL_DEG
    checks['rotor_ending_360'] = r['ending_err_deg'] <= rotor.TOL_DEG
    info['rotor'] = r
    opening = opening_events.write()             # stops if the picture code changed
    checks['opening_table'] = True
    info['opening'] = {'events': opening_events.OUT, 'count': len(opening),
                       'by_kind': film_events.by_kind(opening)}

    # 2. picture pages
    film, fpage = page_table(film_url)
    pages = [fpage]
    if abs(fpage['start'] - opening_events.END) > 1e-9:
        raise SystemExit(f'the film page starts at {fpage["start"]}, not {opening_events.END}')
    end, dropped = float(fpage['duration']), []
    tables = [(opening, 'opening'), (film, 'film')]
    if ending_url:
        ending, epage = page_table(ending_url)
        pages.append(epage)
        if epage['start'] > fpage['duration'] + 1e-9:
            raise SystemExit(f'gap between the film page (to {fpage["duration"]}) '
                             f'and the ending page (from {epage["start"]})')
        ending, dropped = drop_repeats(film, ending)
        tables.append((ending, 'ending'))
        end = max(end, float(epage['duration']))
    checks['page_events'] = True                 # film_events.py stops on any bad event
    spins = [{'t': t0, 'kind': 'spin', 'gain': 1.0, 'src': '3d', 'what': 'rotor', 'dur': d}
             for t0, d in rotor.SPIN_EVENTS if opening_events.END <= t0 and t0 + d <= end]
    tables.append((spins, 'rotor'))

    out = os.path.abspath(out or DEFAULT_OUT)
    if out == os.path.abspath(DEFAULT_OUT) and abs(end - FILM_LENGTH) > 1e-9:
        raise SystemExit(f'the pages end at {end} s, not {FILM_LENGTH}: name the output with --out')
    table = [dict(e, **{'from': name}) for evs, name in tables for e in evs]
    table.sort(key=lambda e: e['t'])
    late = [(e['t'], e['kind']) for e in table if not 0.0 <= e['t'] < end]
    if late:
        raise SystemExit(f'events outside 0-{end} s: {late[:10]}')
    stem = os.path.splitext(out)[0]
    write_table(stem + '.events.json', table)
    info['pages'] = pages
    info['dropped_repeats'] = [(e['t'], e['kind']) for e in dropped]
    info['table'] = {'events': stem + '.events.json', 'count': len(table),
                     'by_kind': film_events.by_kind(table),
                     'by_part': {name: len(evs) for evs, name in tables}}

    # 3. balance (声音任务说明 8) and mix
    samples = int(round(end * make_audio.SR))
    events = make_audio.load_events([stem + '.events.json'])
    st = balance.stems(make_audio, events, 0.0, end, make_audio.load_spin('rotor:rotor_rps'), 0)
    cat_db, fit = balance.fit_mix(make_audio, st, target, max_limit_db)
    del st
    info['balance_fit'] = dict(fit, category_db=cat_db, target_lufs=target, max_limit_db=max_limit_db)
    mix = make_audio.mix([stem + '.events.json'], out, 'rotor:rotor_rps', 0.0, end, 0,
                         cat_db=cat_db, target=target, max_limit_db=max_limit_db,
                         start_gain_db=fit.get('gain_db'))
    info['mix'] = {k: v for k, v in mix.items() if k not in ('events',)}

    # 4. checks
    ok, res = check_audio.run(out, samples)
    checks.update(ok)
    info['check'] = res
    result = {'out': out, 'end': end, 'samples': samples, 'passed': sum(checks.values()),
              'total': len(checks), 'checks': checks, **info}
    with open(stem + '.build.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--film', required=True, help='film page URL with &play=0')
    ap.add_argument('--ending', help='ending page URL with &play=0')
    ap.add_argument('--out', help=f'output WAV (default {DEFAULT_OUT})')
    a = ap.parse_args()
    r = build(a.film, a.ending, a.out)
    for k, v in r['checks'].items():
        detail = r['check'].get(k, '')
        print(f"{'PASS' if v else 'FAIL'}  {k:16s} {json.dumps(detail, ensure_ascii=False)[:300]}")
    print(f"{r['passed']}/{r['total']} checks passed; {r['table']['count']} events "
          f"{json.dumps(r['table']['by_part'])}; {r['samples']} samples -> {r['out']}")
    sys.exit(0 if r['passed'] == r['total'] else 1)


if __name__ == '__main__':
    main()
