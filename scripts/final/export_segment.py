"""Export one stretch of the film frame by frame, losslessly.

Every frame is a page seek, so the result does not depend on how fast the
machine draws. The page's own playback is forced off, and the export refuses to
start while the picture still moves.

Usage:
  export_segment.py URL OUT.mkv START END [--scale 2] [--from-frame N]

Frame n of the stretch is t = START + n / 60, and there are
round((END - START) * 60) of them. Resuming with --from-frame N writes only the
rest, as a file that covers START + N/60 .. END; pass both parts to assemble.py
as two segments.

Output is lossless H.264 (qp 0, yuv444p) in an mkv, 60 fps. `--scale 2` renders
at 3840x2160.
"""
import argparse, subprocess, sys, time

from playwright.sync_api import sync_playwright

FPS = 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('url')
    ap.add_argument('out')
    ap.add_argument('start', type=float)
    ap.add_argument('end', type=float)
    ap.add_argument('--scale', type=int, default=2)
    ap.add_argument('--from-frame', type=int, default=0)
    args = ap.parse_args()

    url = args.url
    if 'play=' not in url:
        url += ('&' if '?' in url else '?') + 'play=0'

    total = int(round((args.end - args.start) * FPS))
    first = args.from_frame
    if first < 0 or first >= total:
        raise SystemExit(f'--from-frame {first} is outside 0..{total}')

    ffmpeg = subprocess.Popen([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'image2pipe', '-framerate', str(FPS), '-i', '-',
        '-c:v', 'libx264', '-qp', '0', '-preset', 'ultrafast',
        '-pix_fmt', 'yuv444p', '-r', str(FPS), args.out,
    ], stdin=subprocess.PIPE)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True,
                                     args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
        page = browser.new_page(viewport={'width': 1920, 'height': 1080},
                                device_scale_factor=args.scale)
        page.goto(url)
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
        page.evaluate("document.fonts.ready")
        # Seek once to the first frame so the page is driven before the steadiness test.
        page.evaluate(f'window.__seek({args.start})')
        page.evaluate(f'window.__seek({args.start})')
        steady = False
        for _ in range(10):
            a = page.screenshot()
            page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            if a == page.screenshot():
                steady = True
                break
            time.sleep(0.2)
        if not steady:
            ffmpeg.kill()
            raise SystemExit('the page is still playing; pass a URL with play=0')

        started = time.time()
        for i in range(first, total):
            t = args.start + i / FPS
            page.evaluate(f'window.__seek({t})')
            ffmpeg.stdin.write(page.screenshot(type='png'))
            done = i - first + 1
            if done % 300 == 0:
                elapsed = time.time() - started
                left = elapsed / done * (total - first - done)
                print(f'frame {i + 1}/{total}  {elapsed:.0f}s elapsed  ~{left:.0f}s left', flush=True)
        browser.close()
    ffmpeg.stdin.close()
    ffmpeg.wait()
    print(f'done frames {first}..{total - 1} in {time.time() - started:.0f}s -> {args.out}')


if __name__ == '__main__':
    main()
