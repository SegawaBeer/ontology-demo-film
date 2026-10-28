"""Export the timed clip frame by frame and encode it with ffmpeg.

Each frame is produced by seeking the page to an exact time, so the result
does not depend on how fast the machine renders.
Usage: export-clip.py URL OUT.mp4 [fps] [scale] [limit_frames] [start_seconds] [crf]
(limit_frames 0 = no limit; crf defaults to 14)
"""
import sys, time, subprocess
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
fps = int(sys.argv[3]) if len(sys.argv) > 3 else 60
scale = int(sys.argv[4]) if len(sys.argv) > 4 else 2
limit = int(sys.argv[5]) if len(sys.argv) > 5 else None
start_at = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0
crf = sys.argv[7] if len(sys.argv) > 7 else '14'

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=scale)
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
    page.evaluate("document.fonts.ready")
    duration = page.evaluate("window.__duration")
    total = int(round((duration - start_at) * fps))
    if limit: total = min(total, limit)
    ffmpeg = subprocess.Popen([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'image2pipe', '-framerate', str(fps), '-i', '-',
        '-c:v', 'libx264', '-preset', 'slow', '-crf', crf, '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', out,
    ], stdin=subprocess.PIPE)
    started = time.time()
    for i in range(total):
        page.evaluate(f"window.__seek({start_at + i / fps})")
        ffmpeg.stdin.write(page.screenshot(type='png'))
        if i % 60 == 0:
            elapsed = time.time() - started
            print(f'frame {i}/{total}  {elapsed:.0f}s elapsed  ~{elapsed / max(1, i) * (total - i):.0f}s left', flush=True)
    ffmpeg.stdin.close()
    ffmpeg.wait()
    browser.close()
    print(f'done {total} frames in {time.time() - started:.0f}s -> {out}')
