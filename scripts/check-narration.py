"""Checks for the narration subtitles and the title cards (任务说明/字幕与标题卡任务说明.md, 二 and 三).

N1  every 0.1 s over 0-120: the subtitle on the page (opening 0-30, film 30-103, ending 103-120,
    all with &narration=1) is the line of 字幕方案-v1.1 3.2 for that moment, word for word, and
    nothing is shown outside the table's spans.
N2  at the same moments: the subtitle box does not meet the box of any other visible text and
    stays inside the 1920x1080 frame.
N3  without &narration=1, 30 moments are pixel-identical to the base build (072d37c).
N4  with &narration=1, seeking somewhere else and back gives the same picture as opening at t.
C1  each card's last frame (u = D - 1/60) is the background PNG, pixel for pixel (3840x2160);
    for cards 1-6 the first frame is too.
C2  each card's texts match 字幕方案-v1.1 2.1, and its __events is one tone at 0.25 s, gain 0.35.

Usage: check-narration.py --new URL --base URL [--cards DIR_URL --cards-dir DIR] [--only N1,C1]
       [--out review/narration]
URL is the frames.html of a build (the new one, and 072d37c for N3); the cards need their
background PNGs c0.png .. c6.png served at DIR_URL and readable at DIR.
"""
import io, json, os, re, sys, time
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '<项目目录>'
args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
NEW, BASE = opt('--new'), opt('--base')
CARDS_URL, CARDS_DIR = opt('--cards'), opt('--cards-dir')
ONLY = set(opt('--only').split(',')) if opt('--only') else None
OUT = opt('--out', os.path.join(HERE, '..', 'review', 'narration'))
os.makedirs(OUT, exist_ok=True)
FPS = 60
CARD_AT = [0.0, 30.0, 33.0, 49.0, 64.0, 86.0, 101.0]
results = {}


def record(key, ok, **detail):
    results[key] = {'pass': bool(ok), **detail}
    json.dump(results, open(os.path.join(OUT, 'results.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'{key}: {"PASS" if ok else "FAIL"}', json.dumps(detail, ensure_ascii=False)[:700], flush=True)


def want(key):
    return ONLY is None or key in ONLY


def table():
    """22 lines of 3.2 (the closing line is the ending's own) and the 7 cards of 2.1, from the plan itself."""
    md = open(f'{ROOT}/脚本/字幕方案-v1.1.md', encoding='utf-8').read()
    sec = md[md.index('### 3.2'):md.index('### 3.3')]
    lines = [(float(a), float(b), text.split('<br>')) for n, a, b, text in
             re.findall(r'^\| (\d+) \| ([\d.]+)–([\d.]+) \| (.*?) \|', sec, re.M)]
    sec = md[md.index('### 2.1'):md.index('### 2.2')]
    cards = [[c.strip() for c in row] for row in re.findall(r'^\| (?:片头|[一二三四五六]) \| [^|]* \| ([^|]*) \| ([^|]*) \| ([^|]*) \|', sec, re.M)]
    return lines, [[None if c == '—' else c for c in row] for row in cards]


PAGES = [('opening', 0.0, 30.0), ('film', 30.0, 103.0), ('ending', 103.0, 120.5)]
page_of = lambda t: next(p for p in PAGES if p[1] <= t + 1e-9 < p[2])

PROBE_JS = r"""(t) => {
  window.__seek(t);
  const box = document.querySelector('.narration');
  const lines = box ? [...box.children].map(s => s.textContent) : null;
  const shown = !!box && box.style.display !== 'none' && parseFloat(getComputedStyle(box).opacity) > 0;
  if (!shown) return { shown, lines };
  const r = box.getBoundingClientRect();
  const alpha = el => {
    let a = 1;
    for (let e = el; e && e.nodeType === 1; e = e.parentNode) {
      const cs = getComputedStyle(e);
      if (cs.display === 'none' || cs.visibility === 'hidden') return 0;
      a *= parseFloat(cs.opacity);
    }
    return a;
  };
  const clipOf = el => {   // the visible part of el's area: every ancestor that clips its overflow
    let c = { left: 0, top: 0, right: 1920, bottom: 1080 };
    for (let e = el.parentElement; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.overflow !== 'visible' || cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
        const q = e.getBoundingClientRect();
        c = { left: Math.max(c.left, q.left), top: Math.max(c.top, q.top), right: Math.min(c.right, q.right), bottom: Math.min(c.bottom, q.bottom) };
      }
    }
    return c;
  };
  const hits = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const el = n.parentElement;
    if (!el || !n.textContent.trim() || box.contains(el) || alpha(el) <= 0) continue;
    const range = document.createRange();
    range.selectNodeContents(n);
    const c = clipOf(el);
    for (const q of range.getClientRects()) {
      const x0 = Math.max(q.left, c.left), y0 = Math.max(q.top, c.top), x1 = Math.min(q.right, c.right), y1 = Math.min(q.bottom, c.bottom);
      if (x1 <= x0 || y1 <= y0) continue;
      if (x0 < r.right && x1 > r.left && y0 < r.bottom && y1 > r.top)
        hits.push({ text: n.textContent.trim().slice(0, 24), rect: [x0, y0, x1, y1].map(v => Math.round(v * 10) / 10), alpha: +alpha(el).toFixed(3) });
    }
  }
  return { shown, lines, box: [r.left, r.top, r.right, r.bottom].map(v => Math.round(v * 10) / 10), hits };
}"""


def load(page, url):
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
    page.evaluate('document.fonts.ready')


def shot(page, clip=None):
    kw = {'clip': clip} if clip else {}
    return Image.open(io.BytesIO(page.screenshot(**kw))).convert('RGB')


def same(a, b):
    return a.size == b.size and ImageChops.difference(a, b).getbbox() is None
# ---- CHECKS BELOW ----


def n1_n2(browser):
    lines, _ = table()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    bad_text, bad_box, rows, current = [], [], 0, None
    for i in range(0, 1201):
        t = i / 10
        name = page_of(t)[0]
        if name != current:
            load(page, f'{NEW}?frame={name}&theme=light&play=0&narration=1')
            current = name
        got = page.evaluate(PROBE_JS, t)
        want_line = next((l for a, b, l in lines if round(a * 10) < i < round(b * 10)), None)
        rows += 1
        if (want_line is None) != (not got['shown']) or (want_line and got['lines'] != want_line):
            bad_text.append({'t': t, 'want': want_line, 'got': got['lines'] if got['shown'] else None})
        if got['shown']:
            x0, y0, x1, y1 = got['box']
            if got['hits'] or x0 < 0 or y0 < 0 or x1 > 1920 or y1 > 1080:
                bad_box.append({'t': t, 'box': got['box'], 'hits': got['hits'][:4]})
    page.close()
    shown = sum(1 for i in range(1201) if any(round(a * 10) < i < round(b * 10) for a, b, _ in lines))
    record('N1', not bad_text, samples=rows, with_line=shown, lines=len(lines), bad=bad_text[:12])
    record('N2', not bad_box, samples=shown, bad=bad_box[:12])


N3_TIMES = [round(0.4 + i * 4.0, 1) for i in range(30)]   # 0.4 .. 116.4, both with and without a line due


def n3(browser):
    a = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)
    b = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)
    bad, cur = [], None
    for t in N3_TIMES:
        name = page_of(t)[0]
        if name != cur:
            load(a, f'{NEW}?frame={name}&theme=light&play=0')
            load(b, f'{BASE}?frame={name}&theme=light&play=0')
            for p in (a, b):
                p.evaluate(f'window.__seek({page_of(t)[1]})')
            cur = name
        a.evaluate(f'window.__seek({t})'); b.evaluate(f'window.__seek({t})')
        ia, ib = shot(a), shot(b)
        if not same(ia, ib):
            bad.append({'t': t, 'bbox': ImageChops.difference(ia, ib).getbbox()})
    record('N3', not bad, moments=len(N3_TIMES), scale=2, bad=bad)


N4_TIMES = [1.0, 7.3, 21.95, 27.2, 36.4, 46.0, 53.3, 60.1, 73.2, 81.7, 92.1, 100.9, 104.9, 109.0, 110.9]


def n4(browser):
    bad = []
    for t in N4_TIMES:
        name, start, _ = page_of(t)
        url = f'{NEW}?frame={name}&theme=light&play=0&narration=1'
        fresh = browser.new_page(viewport={'width': 1920, 'height': 1080})
        load(fresh, url)
        fresh.evaluate(f'window.__seek({start})')
        fresh.evaluate(f'window.__seek({t})')
        ref = shot(fresh)
        fresh.close()
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        load(page, url)
        for other in (start, min(t + 6.3, page_of(t)[2] - 0.05), max(start, t - 3.1), t + 0.05):
            page.evaluate(f'window.__seek({other})')
        page.evaluate(f'window.__seek({t})')
        got = shot(page)
        page.close()
        if not same(ref, got):
            bad.append({'t': t, 'bbox': ImageChops.difference(ref, got).getbbox()})
    record('N4', not bad, moments=len(N4_TIMES), bad=bad)


def c1_c2(browser):
    _, cards = table()
    bad1, bad2 = [], []
    for k, (label, title, sub) in enumerate(cards):
        page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)
        load(page, f'{NEW}?frame=card&id={k}&theme=light&play=0&bg={CARDS_URL}/c{k}.png')
        info = page.evaluate("""() => ({ start: window.__start, duration: window.__duration, events: window.__events,
          label: document.querySelector('.card-label')?.textContent ?? null,
          red: [...document.querySelectorAll('.card-label .card-alert')].map(e => [e.textContent, getComputedStyle(e).color]),
          labelColour: document.querySelector('.card-label') ? getComputedStyle(document.querySelector('.card-label')).color : null,
          title: document.querySelector('.card-title')?.textContent ?? null,
          sub: document.querySelector('.card-sub')?.textContent ?? null })""")
        D = info['duration']
        want_red = [['自动提示', 'rgb(229, 72, 60)']] if k == 4 else []
        ok2 = (info['label'], info['title'], info['sub']) == (label, title, sub) and info['red'] == want_red \
            and info['start'] == 0 and abs(D - (2.4 if k in (0, 1, 6) else 2.0)) < 1e-9 \
            and info['events'] == [{'t': 0.25, 'kind': 'tone', 'gain': 0.35, 'src': '3d'}]
        if not ok2:
            bad2.append({'card': k, **info})
        bg = Image.open(os.path.join(CARDS_DIR, f'c{k}.png')).convert('RGB')
        frames = [round(D * FPS) - 1] + ([0] if k else [])
        for n in frames:
            page.evaluate(f'window.__seek({n / FPS})')
            got = shot(page)
            if not same(got, bg):
                bad1.append({'card': k, 'frame': n, 'bbox': ImageChops.difference(got, bg).getbbox() if got.size == bg.size else got.size})
        page.close()
    record('C1', not bad1, cards=len(cards), bad=bad1)
    record('C2', not bad2, cards=len(cards), bad=bad2)


if __name__ == '__main__':
    started = time.time()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True,
                                     args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
        if want('N1') or want('N2'):
            n1_n2(browser)
        if want('N3') and BASE:
            n3(browser)
        if want('N4'):
            n4(browser)
        if (want('C1') or want('C2')) and CARDS_URL:
            c1_c2(browser)
        browser.close()
    passed = sum(r['pass'] for r in results.values())
    print(f'{passed}/{len(results)} passed in {time.time() - started:.0f}s')
    sys.exit(0 if passed == len(results) else 1)
