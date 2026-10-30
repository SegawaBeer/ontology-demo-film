"""Check a finished film against the page and against its own sound track.

Usage:
  check_final.py 成片/本体能力演示-4K60.mp4 \
      --seg 'URL:0:30' --seg 'URL:30:103' --seg 'URL:103:120' [--step 2] [--audio-only]

Picture: every STEP seconds inside each segment, the frame at that time is taken
from the film and compared with the page rendered at the same moment (3840x2160).
The mean channel difference has to stay at or below 2.0.

Sound: EBU R128 loudness and true peak (the peak has to be at or below -1 dBTP),
and the first 0.3 s and the last 0.5 s have to be silent.

The page is only needed for the picture part; --audio-only skips it.
"""
import argparse, json, os, re, subprocess, sys, tempfile

FPS = 60
LIMIT = 2.0
PEAK_LIMIT = -1.0
SILENCE_DB = -60.0


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def mean_diff(a_path, b_path):
    from PIL import Image, ImageChops, ImageStat
    a = Image.open(a_path).convert('RGB')
    b = Image.open(b_path).convert('RGB')
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3


def frame_at(video, t, path):
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                    '-ss', f'{t:.3f}', '-i', video, '-frames:v', '1', path], check=True)
    return path


def loudness(video):
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', video,
                          '-filter_complex', 'ebur128=peak=true', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    block = out[out.rfind('Summary:'):]
    integrated = re.search(r'I:\s+(-?[\d.]+) LUFS', block)
    peak = re.search(r'Peak:\s+(-?[\d.]+) dBFS', block)
    return {'integrated_lufs': float(integrated.group(1)) if integrated else None,
            'true_peak_db': float(peak.group(1)) if peak else None}


def max_volume(video, start=None, length=None, tail=None):
    cmd = ['ffmpeg', '-hide_banner', '-nostats']
    if tail:
        cmd += ['-sseof', f'-{tail:.3f}']
    cmd += [*(['-ss', f'{start:.3f}'] if start is not None else []),
            *( ['-t', f'{length:.3f}'] if length is not None else []),
            '-i', video, '-af', 'volumedetect', '-f', 'null', '-']
    out = subprocess.run(cmd, capture_output=True, text=True).stderr
    m = re.search(r'max_volume:\s+(-?[\d.]+) dB', out)
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--seg', action='append', default=[])
    ap.add_argument('--step', type=float, default=2.0)
    ap.add_argument('--audio-only', action='store_true')
    args = ap.parse_args()

    report = {'video': args.video, 'picture': [], 'sound': {}, 'ok': True}

    # sound first: it needs no page
    loud = loudness(args.video)
    head = max_volume(args.video, start=0.0, length=0.3)
    tail = max_volume(args.video, tail=0.5)
    report['sound'] = {**loud, 'head_max_db': head, 'tail_max_db': tail}
    if loud['true_peak_db'] is None or loud['true_peak_db'] > PEAK_LIMIT:
        report['ok'] = False
    if head is None or head > SILENCE_DB or tail is None or tail > SILENCE_DB:
        report['ok'] = False
    print(f"sound: I {loud['integrated_lufs']} LUFS, peak {loud['true_peak_db']} dBTP, "
          f"head {head} dB, tail {tail} dB", flush=True)

    if not args.audio_only:
        from playwright.sync_api import sync_playwright
        tmp = tempfile.mkdtemp(prefix='final-check-')
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='chrome', headless=True,
                                         args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
            page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)
            for spec in args.seg:
                url, start, end = spec.rsplit(':', 2)
                start, end = float(start), float(end)
                if 'play=' not in url:
                    url += ('&' if '?' in url else '?') + 'play=0'
                page.goto(url)
                page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
                page.evaluate("document.fonts.ready")
                t = start
                while t < end - 1e-6:
                    page.evaluate(f'window.__seek({t})')
                    shot = os.path.join(tmp, 'page.png')
                    page.screenshot(path=shot)
                    got = frame_at(args.video, t, os.path.join(tmp, 'film.png'))
                    d = mean_diff(got, shot)
                    report['picture'].append([round(t, 2), round(d, 3)])
                    if d > LIMIT:
                        report['ok'] = False
                    t += args.step
            browser.close()
        subprocess.run(['rm', '-rf', tmp], check=True)
        worst = max(report['picture'], key=lambda r: r[1]) if report['picture'] else [0, 0]
        print(f'picture: {len(report["picture"])} frames, worst {worst[0]}s {worst[1]}', flush=True)

    print(json.dumps(report['sound'], ensure_ascii=False))
    sys.exit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
