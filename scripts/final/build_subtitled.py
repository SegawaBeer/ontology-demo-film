"""Assemble the subtitled film (字幕与标题卡任务说明.md 第五节): seven title cards cut in as held
frames, 135.2 s, 8,112 frames.

Step 2, the seven card backgrounds (one decoding pass per segment):
  build_subtitled.py stills --opening O.mp4 --film F.mp4 --dir /tmp/sub-dist/cards
Step 4, the finished files:
  build_subtitled.py assemble --opening O.mp4 --film F.mp4 --ending E.mp4 --cards DIR
                     --audio 音频/全片音效-字幕版.wav --out 成片/本体能力演示-字幕版

Segments: opening 0-30, film 30-103, ending 103-120 (export_segment.py, lossless, frame n at
START + n/60); DIR/card0.mp4 .. card6.mp4 are the card pages exported over 0..D. The film
segment is cut by frame number. Order: card 0, opening, card 1, film 30-33, card 2, film 33-49,
card 3, film 49-64, card 4, film 64-86, card 5, film 86-101, card 6, film 101-103, ending.

assemble: checks every piece's frame count and that the pieces touch in film time; joins them
in one filter graph (trim by frame number + concat, nothing written to disk); checks every frame of the join against its source
frame by frame hash (so the two frames either side of each of the 14 seams too); writes the 4K
(crf 14) and 1080p (crf 16) files with the audio, checks them with ffprobe, writes the contact
sheets 拼版-字幕版-每3秒.jpg / -每0.5秒.jpg, the .srt (the 22 narration lines and the closing
line of 字幕方案-v1.1 3.2 in film time), 成片记录-字幕版.json, and deletes its intermediates.
"""
import argparse, itertools, json, os, re, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble import probe, run  # noqa: E402

FPS = 60
ROOT = os.environ.get('FILM_ROOT') or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
PLAN_MD = f'{ROOT}/docs/脚本/字幕方案-v1.1.md'
CARD_AT = (0.0, 30.0, 33.0, 49.0, 64.0, 86.0, 101.0)
CARD_DUR = (2.4, 2.4, 2.0, 2.0, 2.0, 2.0, 2.4)
SEGS = {'opening': (0.0, 30.0), 'film': (30.0, 103.0), 'ending': (103.0, 120.0)}
STILL_OF = [('opening', 0.0), *[('film', a) for a in CARD_AT[1:]]]


def offset(t):
    """Card time cut in at or before original time t."""
    return sum(d for a, d in zip(CARD_AT, CARD_DUR) if a <= t + 1e-9)


def to_new(t):
    return t + offset(t)


def frames(seconds):
    return int(round(seconds * FPS))


def pieces():
    """[(source, first frame, end frame, original start, original end or None for a card)] in order."""
    out = []
    cuts = list(CARD_AT[1:]) + [None]
    for k, at in enumerate(CARD_AT):
        out.append((f'card{k}', 0, frames(CARD_DUR[k]), at, None))
        if k == 0:
            out.append(('opening', 0, frames(30.0), 0.0, 30.0))
            continue
        nxt = cuts[k] if cuts[k] is not None else 103.0
        out.append(('film', frames(at - 30.0), frames(nxt - 30.0), at, nxt))
    out.append(('ending', 0, frames(17.0), 103.0, 120.0))
    return out


def stills(args):
    os.makedirs(args.dir, exist_ok=True)
    for name, path in (('opening', args.opening), ('film', args.film)):
        idx = [(k, frames(t - SEGS[name][0])) for k, (n, t) in enumerate(STILL_OF) if n == name]
        sel = '+'.join(f'eq(n\\,{i})' for _, i in idx)
        tmp = tempfile.mkdtemp(prefix='stills-')
        run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', path, '-vf', f'select={sel}',
             '-fps_mode', 'passthrough', '-pix_fmt', 'rgb24', os.path.join(tmp, '%d.png')])
        got = sorted(os.listdir(tmp), key=lambda f: int(f.split('.')[0]))
        if len(got) != len(idx):
            raise SystemExit(f'{path}: wanted {len(idx)} stills, got {len(got)}')
        for (k, i), f in zip(idx, got):
            os.replace(os.path.join(tmp, f), os.path.join(args.dir, f'c{k}.png'))
            print(f'c{k}.png  {name} frame {i} (t = {STILL_OF[k][1]})', flush=True)
        os.rmdir(tmp)


def framemd5(path):
    """Hash of every decoded frame; path is a file, or ffmpeg input options (a list, e.g. a concat list)."""
    inp = path if isinstance(path, list) else ['-i', path, '-map', '0:v:0']
    out = run(['ffmpeg', '-hide_banner', '-loglevel', 'error', *inp, '-f', 'framemd5', '-']).stdout
    return [line.rsplit(',', 1)[1].strip() for line in out.splitlines() if line and not line.startswith('#')]


def srt(path):
    md = open(PLAN_MD, encoding='utf-8').read()
    sec = md[md.index('### 3.2'):md.index('### 3.3')]
    rows = re.findall(r'^\| (\d+|片尾) \| ([\d.]+)–([\d.]+) \| (.*?) \|', sec, re.M)
    stamp = lambda s: f'{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d},{int(round(s * 1000)) % 1000:03d}'
    cues = []
    for i, (_, a, b, text) in enumerate(rows, 1):
        # A line that ends exactly at a cut (17 at 86.0, 20 at 101.0) ends before that card, not after it.
        a, b = to_new(float(a)), float(b) + sum(d for at, d in zip(CARD_AT, CARD_DUR) if at < float(b) - 1e-9)
        cues.append(f'{i}\n{stamp(a)} --> {stamp(b)}\n' + '\n'.join(text.split('<br>')) + '\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(cues))
    return len(rows)
# ---- assemble below ----


ORDER = [f'card{k}' for k in range(7)] + ['opening', 'film', 'ending']   # ffmpeg input order


def graph(tail=None):
    """Filter graph over the inputs in ORDER: each piece trimmed by frame number, all concatenated
    into [c] with frame n at n/60 exactly (no frame can be dropped or doubled), then `tail`."""
    idx = {n: i for i, n in enumerate(ORDER)}
    uses = sum(1 for p in pieces() if p[0] == 'film')
    parts = [f'[{idx["film"]}:v]split={uses}' + ''.join(f'[fs{j}]' for j in range(uses))]
    labels, j = [], 0
    for i, (name, a, b, _, _) in enumerate(pieces()):
        if name == 'film':
            inp, j = f'[fs{j}]', j + 1
        else:
            inp = f'[{idx[name]}:v]'
        parts.append(f'{inp}trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS,settb=1/{FPS}[p{i}]')
        labels.append(f'[p{i}]')
    parts.append(''.join(labels) + f'concat=n={len(labels)}:v=1:a=0,setpts=N/{FPS}/TB[c]')
    return ';'.join(parts + ([tail] if tail else []))


def assemble(args):
    record, t_all = {'pieces': [], 'steps': {}, 'seams': [], 'outputs': []}, time.time()
    src = {'opening': args.opening, 'film': args.film, 'ending': args.ending,
           **{f'card{k}': os.path.join(args.cards, f'card{k}.mp4') for k in range(7)}}
    want = {'opening': 1800, 'film': 4380, 'ending': 1020, **{f'card{k}': frames(d) for k, d in enumerate(CARD_DUR)}}
    for name, path in src.items():
        got = probe(path)['video']['frames']
        if got != want[name]:
            raise SystemExit(f'{name} ({path}) has {got} frames, wants {want[name]}')
    # 1. the pieces touch in film time: each starts where the one before it ended
    at = 0
    for name, a, b, t0, t1 in pieces():
        start = sum(CARD_DUR[:int(name[4:])]) + CARD_AT[int(name[4:])] if name.startswith('card') else to_new(t0)
        if frames(start) != at:
            raise SystemExit(f'{name} {t0}: starts at frame {frames(start)} of the film, the one before ends at {at}')
        record['pieces'].append({'source': name, 'frames': [a, b], 'original': [t0, t1], 'film': [round(start, 4), round((at + b - a) / FPS, 4)]})
        at += b - a
    total = at
    if total != frames(120.0 + sum(CARD_DUR)):
        raise SystemExit(f'{total} frames, not {frames(120.0 + sum(CARD_DUR))}')
    print(f'pieces ok: {len(record["pieces"])}, {total} frames', flush=True)

    # 2. the join is one filter graph: trim by frame number, concat. Nothing is written to disk
    #    (cut pieces would be another ~1 GB); the hash check, the seam frames and both encodes run
    #    the same graph, so what is checked is exactly what is encoded.
    tmp = tempfile.mkdtemp(prefix='subtitled-')
    inputs = [x for name in ORDER for x in ('-threads', '2', '-i', src[name])]

    # 3. every frame of the join is its source frame (decoded-frame hashes), and the step at each seam
    t0 = time.time()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(4) as pool:
        joined = pool.submit(framemd5, [*inputs, '-filter_complex', graph(), '-map', '[c]'])
        hashes = dict(zip(src, pool.map(framemd5, src.values())))
        hashes['combined'] = joined.result()
    expect = [h for name, a, b, _, _ in pieces() for h in hashes[name][a:b]]
    bad = [i for i, (x, y) in enumerate(zip(hashes['combined'], expect)) if x != y]
    if len(hashes['combined']) != total or bad:
        raise SystemExit(f'join differs from its sources: {len(hashes["combined"])} frames, first bad {bad[:5]}')
    from assemble import frame_diff
    edges = list(itertools.accumulate(b - a for _, a, b, _, _ in pieces()))[:-1]
    sel = '+'.join(f'eq(n\\,{e - 1})+eq(n\\,{e})' for e in edges)
    run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', *inputs, '-filter_complex', graph(f'[c]select={sel}[s]'),
         '-map', '[s]', '-fps_mode', 'passthrough', os.path.join(tmp, 'seam%d.png')])
    for k, (e, piece) in enumerate(zip(edges, pieces())):
        record['seams'].append({'frame': e, 't': round(e / FPS, 4), 'after': piece[0],
                                'same_as_source': [e - 2, e - 1, e, e + 1],
                                'step_diff': round(frame_diff(os.path.join(tmp, f'seam{2 * k + 1}.png'),
                                                              os.path.join(tmp, f'seam{2 * k + 2}.png')), 3)})
    record['steps']['frame check'] = round(time.time() - t0, 1)
    print(f'all {total} frames equal their sources; {len(record["seams"])} seams', flush=True)
    finish(args, record, inputs, tmp, total, t_all)
# ---- finish below ----


def finish(args, record, inputs, tmp, total, t_all):
    # 4. the two finished files, with the audio from zero
    length = total / FPS
    audio = probe(args.audio)['audio']['duration']
    if abs(audio - length) > 1 / FPS:
        raise SystemExit(f'audio lasts {audio:.3f}s, the film {length:.3f}s')
    fourk, small = f'{args.out}-4K60.mp4', f'{args.out}-1080p.mp4'
    audio_in = f'{len(ORDER)}:a:0'
    common = ['-map', audio_in, '-r', str(FPS), '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-ac', '2',
              '-movflags', '+faststart', '-t', f'{length}', '-c:v', 'libx264', '-profile:v', 'high',
              '-preset', 'slow', '-pix_fmt', 'yuv420p']
    t0 = time.time()
    run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', *inputs, '-i', args.audio,
         '-filter_complex', graph('[c]split=2[v4][vs];[vs]scale=1920:1080:flags=lanczos[v1]'),
         '-map', '[v4]', *common, '-crf', '14', fourk, '-map', '[v1]', *common, '-crf', '16', small])
    record['steps']['encode 4K and 1080p'] = round(time.time() - t0, 1)
    print(f'encoded both in {record["steps"]["encode 4K and 1080p"]}s', flush=True)
    # 5. ffprobe both
    for path, size in ((fourk, (3840, 2160)), (small, (1920, 1080))):
        info = probe(path)
        v, a = info['video'], info['audio']
        ok = (v['frames'] == total and abs(info['duration'] - length) <= 1 / FPS and abs(a['duration'] - length) <= 1 / FPS
              and v['fps'] == FPS and (v['width'], v['height']) == size)
        record['outputs'].append({'file': path, 'duration': round(info['duration'], 3), 'frames': v['frames'],
                                  'size': [v['width'], v['height']], 'fps': v['fps'], 'audio': round(a['duration'], 3), 'ok': ok})
        if not ok:
            raise SystemExit(f'{path} failed its ffprobe check: {record["outputs"][-1]}')
    # 6. contact sheets, subtitles, record; 7. no intermediates
    folder = os.path.dirname(os.path.abspath(args.out))
    sheets = {'拼版-字幕版-每0.5秒.jpg': 'fps=2,scale=480:270,tile=12x23', '拼版-字幕版-每3秒.jpg': 'fps=1/3,scale=480:270,tile=8x6'}
    for name, vf in sheets.items():
        run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', small, '-vf', vf, '-frames:v', '1', '-q:v', '4',
             os.path.join(folder, name)])
    record['sheets'] = {n: round(os.path.getsize(os.path.join(folder, n)) / 1e6, 2) for n in sheets}
    record['srt'] = {'file': f'{args.out}.srt', 'cues': srt(f'{args.out}.srt')}
    record['steps']['total'] = round(time.time() - t_all, 1)
    with open(os.path.join(folder, '成片记录-字幕版.json'), 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
    subprocess.run(['rm', '-rf', tmp], check=True)
    print('sheets', record['sheets'], 'srt', record['srt'], 'done', flush=True)


def page_at(T, pages, bg):
    """(url, page time) of the moment film time T shows."""
    edge = 0
    for name, a, b, t0, _ in pieces():
        if T < (edge + b - a) / FPS - 1e-9:
            u = T - edge / FPS
            if name.startswith('card'):
                k = int(name[4:])
                return f'{pages}?frame=card&id={k}&theme=light&play=0&bg={bg}/c{k}.png', u
            frame = {'opening': 'opening', 'film': 'film', 'ending': 'ending'}[name]
            return f'{pages}?frame={frame}&theme=light&play=0&narration=1', t0 + u
        edge += b - a
    raise ValueError(T)


def check(args):
    """Every STEP s of the film against its page at the same moment (card pieces against the card page)."""
    from playwright.sync_api import sync_playwright
    from assemble import frame_diff
    tmp = tempfile.mkdtemp(prefix='subtitled-check-')
    rows, T, length = [], 0.0, probe(args.video)['video']['frames'] / FPS
    picks = [frames(k * args.step) for k in range(int((length - 1e-6) // args.step) + 1)]
    # one decoding pass for every sampled frame
    run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', args.video, '-vf',
         'select=' + '+'.join(f'eq(n\\,{n})' for n in picks), '-fps_mode', 'passthrough', os.path.join(tmp, 'f%d.png')])
    if len([f for f in os.listdir(tmp) if f.startswith('f')]) != len(picks):
        raise SystemExit('could not decode every sampled frame')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True, args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
        page, current = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2), None
        for idx, n in enumerate(picks, 1):
            T = n / FPS
            url, t = page_at(T, args.pages, args.bg)
            if url != current:
                for k in range(3):
                    page.goto(url)
                    try:
                        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=60000)
                        break
                    except Exception:
                        if k == 2:
                            raise
                page.evaluate('document.fonts.ready')
                current = url
            page.evaluate(f'window.__seek({t})')
            page.screenshot(path=os.path.join(tmp, 'page.png'))
            d = frame_diff(os.path.join(tmp, f'f{idx}.png'), os.path.join(tmp, 'page.png'))
            rows.append([round(T, 2), url.split('?')[1].split('&')[0] + ('&' + url.split('&')[1] if 'card' in url else ''), round(t, 3), round(d, 3)])
            print(rows[-1], flush=True)
        browser.close()
    subprocess.run(['rm', '-rf', tmp], check=True)
    worst = max(rows, key=lambda r: r[3])
    ok = worst[3] <= 2.0
    with open(args.report, 'w', encoding='utf-8') as f:
        json.dump({'video': args.video, 'limit': 2.0, 'frames': len(rows), 'worst': worst, 'ok': ok, 'rows': rows}, f, ensure_ascii=False, indent=1)
    print(f'{len(rows)} frames, worst {worst}, {"PASS" if ok else "FAIL"}')
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('stills'); s.add_argument('--opening', required=True); s.add_argument('--film', required=True); s.add_argument('--dir', required=True)
    a = sub.add_parser('assemble')
    for k in ('--opening', '--film', '--ending', '--cards', '--audio', '--out'):
        a.add_argument(k, required=True)
    c = sub.add_parser('check'); c.add_argument('video'); c.add_argument('--pages', required=True)
    c.add_argument('--bg', required=True, help='URL of the folder with c0.png .. c6.png'); c.add_argument('--step', type=float, default=2.0)
    c.add_argument('--report', required=True)
    args = ap.parse_args()
    {'stills': stills, 'assemble': assemble, 'check': check}[args.cmd](args)


if __name__ == '__main__':
    main()
