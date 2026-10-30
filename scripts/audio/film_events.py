"""Read a picture page's sound events (声音任务说明.md 7.4).

    python3 film_events.py URL [OUT.json]

Runs with the system python3 (it has Playwright; no numpy needed).  Opens URL
(must carry &play=0) in Chrome, waits for document.documentElement.dataset.ready
=== '1', reads window.__events, __start and __duration, and writes the events
as a JSON list of {t, kind, gain, src[, dur]}.  OUT defaults to
音频/events-<frame>.json, <frame> from the URL.  Next to it, OUT.page.json
records the page range and what was filled in.

Filled in for pages that do not give them yet:
- src: type, line, tick, alert, slide -> dialog; path -> graph;
  part, swap, tone -> 3d.
- dur of a slide: 2.0 s.
A page's tick is a number landing on its final value, so it becomes tick-num
(the opening's blade tick is a different voice).

Stops with an error if: t is outside [__start, __duration], a kind is not a
known voice, the times are not in ascending order, or a field is malformed.
"""
import json
import math
import os
import sys
from urllib.parse import parse_qs, urlparse

ROOT = '<项目目录>'
OUT_DIR = f'{ROOT}/音频'

# Every voice of synth.VOICES except spin: the rotor hum is computed from
# rotor.py, not taken from a page.  build_film_audio checks the two agree.
KINDS = {'tone', 'tick-num', 'thud', 'type', 'line', 'path', 'slide', 'part', 'swap', 'alert', 'tick'}
SRCS = {'dialog', 'graph', '3d'}
SRC_OF_KIND = {
    'type': 'dialog', 'line': 'dialog', 'tick': 'dialog', 'tick-num': 'dialog',
    'alert': 'dialog', 'slide': 'dialog', 'path': 'graph',
    'part': '3d', 'swap': '3d', 'tone': '3d', 'thud': '3d',
}
SLIDE_DUR = 2.0
TIME_EPS = 1e-9


def frame_of(url):
    q = parse_qs(urlparse(url).query)
    if q.get('play') != ['0']:
        raise SystemExit(f'film_events: the URL must carry &play=0: {url}')
    if 'frame' not in q:
        raise SystemExit(f'film_events: no frame= in {url}')
    return q['frame'][0]


def default_out(url):
    return f'{OUT_DIR}/events-{frame_of(url)}.json'


def fetch(url, timeout_ms=120000):
    """(events, start, duration) as the page has them."""
    frame_of(url)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True,
                                    args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
        try:
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            page.goto(url)
            page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=timeout_ms)
            got = page.evaluate('({events: window.__events, start: window.__start, duration: window.__duration})')
        finally:
            browser.close()
    return got['events'], got['start'], got['duration']


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def convert(raw, start, duration, where='page'):
    """Validate the page's events and fill them in; returns (events, notes)."""
    bad = []
    if not _num(start) or not _num(duration) or not start < duration:
        raise SystemExit(f'{where}: bad __start / __duration: {start!r}, {duration!r}')
    if not isinstance(raw, list) or not raw:
        raise SystemExit(f'{where}: window.__events is missing or empty')
    out, notes = [], {'filled_src': 0, 'filled_dur': 0, 'tick_to_tick_num': 0}
    last = -math.inf
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            bad.append(f'#{i}: not an object')
            continue
        t, kind, gain = e.get('t'), e.get('kind'), e.get('gain', 1.0)
        if not _num(t):
            bad.append(f'#{i}: t {t!r}')
            continue
        if not start - TIME_EPS <= t <= duration + TIME_EPS:
            bad.append(f'#{i}: t {t} outside [{start}, {duration}]')
        if t < last - TIME_EPS:
            bad.append(f'#{i}: t {t} before the previous event ({last})')
        last = max(last, t)
        if kind not in KINDS:
            bad.append(f'#{i}: unknown kind {kind!r}' + (' (the rotor hum comes from rotor.py)' if kind == 'spin' else ''))
            continue
        if not _num(gain) or gain < 0:
            bad.append(f'#{i}: gain {gain!r}')
            continue
        src = e.get('src')
        if src is None:
            src = SRC_OF_KIND[kind]
            notes['filled_src'] += 1
        elif src not in SRCS:
            bad.append(f'#{i}: src {src!r}')
            continue
        ev = {'t': float(t), 'kind': kind, 'gain': float(gain), 'src': src}
        if kind == 'tick':
            ev['kind'], ev['page_kind'] = 'tick-num', 'tick'
            notes['tick_to_tick_num'] += 1
        if 'dur' in e:
            if not _num(e['dur']) or e['dur'] <= 0:
                bad.append(f'#{i}: dur {e["dur"]!r}')
                continue
            ev['dur'] = float(e['dur'])
        elif kind == 'slide':
            ev['dur'] = SLIDE_DUR
            notes['filled_dur'] += 1
        out.append(ev)
    if bad:
        raise SystemExit(f'{where}: {len(bad)} bad events:\n  ' + '\n  '.join(bad[:40]))
    return out, notes


def by_kind(events):
    counts = {}
    for e in events:
        counts[e['kind']] = counts.get(e['kind'], 0) + 1
    return dict(sorted(counts.items()))


def write(url, out=None):
    """Fetch, convert, write OUT and OUT.page.json; returns the page record."""
    out = out or default_out(url)
    raw, start, duration = fetch(url)
    events, notes = convert(raw, start, duration, where=url)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('[\n' + ',\n'.join(json.dumps(e, ensure_ascii=False) for e in events) + '\n]\n')
    page = {'url': url, 'frame': frame_of(url), 'events': os.path.abspath(out), 'start': start,
            'duration': duration, 'count': len(events), 'by_kind': by_kind(events),
            'page_by_kind': by_kind([{'kind': e.get('page_kind', e['kind'])} for e in events]), **notes}
    with open(os.path.splitext(out)[0] + '.page.json', 'w', encoding='utf-8') as f:
        json.dump(page, f, ensure_ascii=False, indent=1)
    return page


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    page = write(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(page, ensure_ascii=False))


if __name__ == '__main__':
    main()
