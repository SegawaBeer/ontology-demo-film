"""Compare a sample video against the page, one frame per second.

Usage: check-export.py VIDEO URL [start_seconds]

Frame n of the video is the page at t = start + n / 60, so the nth second is
frame 60n. The left column's mean channel difference must stay at or below 2.0.
Exits non-zero when any sampled frame is over.
"""
import os, subprocess, sys, time
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

video, url = sys.argv[1], sys.argv[2]
start = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
FPS = 60
TMP = '/tmp/export-check'
os.makedirs(TMP, exist_ok=True)

if 'play=' not in url:
    url += ('&' if '?' in url else '?') + 'play=0'

dur = float(subprocess.check_output([
    'ffprobe', '-v', 'error', '-select_streams', 'v:0',
    '-show_entries', 'format=duration', '-of', 'csv=p=0', video]).decode().strip())

def video_frame(n, path):
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', video,
                    '-vf', f'select=eq(n\\,{n})', '-vframes', '1', path], check=True)
    return path

def diff(a_path, b_path):
    a = Image.open(a_path).convert('RGB').crop((0, 0, 1280, 1080))
    b = Image.open(b_path).convert('RGB').crop((0, 0, 1280, 1080))
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True,
                                 args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
    page.evaluate("document.fonts.ready")
    rows = []
    n = 0
    while n / FPS < dur - 1e-6:
        t = start + n / FPS
        vp = video_frame(n, f'{TMP}/v.png')
        page.evaluate(f'window.__seek({t})')
        time.sleep(0.05)
        page.screenshot(path=f'{TMP}/p.png')
        rows.append([round(t, 2), round(diff(vp, f'{TMP}/p.png'), 3)])
        n += FPS
    browser.close()

worst = max(rows, key=lambda r: r[1])
for t, d in rows:
    print(f'{t:6.2f}s  {d:.3f}')
print(f'worst {worst[0]:.2f}s {worst[1]:.3f} over {len(rows)} frames')
sys.exit(0 if worst[1] <= 2.0 else 1)
