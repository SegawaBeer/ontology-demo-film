"""Render the opening 3B stills, the contact sheet and the style-frame comparison."""
import os, time
from PIL import Image, ImageChops, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

PROJECT_ROOT = os.environ.get('PROJECT_ROOT', os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
ROOT = PROJECT_ROOT
OUT = f'{ROOT}/review/opening/m3b'
URL = 'http://127.0.0.1:5192/frames.html'
STYLE = f'{ROOT}/样式图/开头0-28树变成网-浅色.png'
TIMES = ['23.0', '23.6', '24.2', '24.8', '25.4', '26.0', '26.6', '27.2', '27.8', '28.0', '28.6', '29.4', '30.0']
os.makedirs(OUT, exist_ok=True)
font = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', 22)

def label(draw, x, y, text):
    box = draw.textbbox((0, 0), text, font=font)
    draw.rectangle([x + 12, y + 12, x + 12 + box[2] - box[0] + 20, y + 12 + box[3] - box[1] + 16], fill=(255, 255, 255, 215))
    draw.text((x + 22, y + 18), text, font=font, fill=(28, 34, 40))

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True,
                                 args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    for t in TIMES:
        page.goto(f'{URL}?frame=opening&theme=light&t={t}')
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
        time.sleep(0.3)
        page.screenshot(path=f'{OUT}/开头三B-{t}秒.png')
    browser.close()

# Contact sheet: 13 stills in a 4-column grid at 480x270.
cols, w, h = 4, 480, 270
rows = (len(TIMES) + cols - 1) // cols
sheet = Image.new('RGB', (cols * w, rows * h), '#ffffff')
draw = ImageDraw.Draw(sheet, 'RGBA')
for i, t in enumerate(TIMES):
    x, y = (i % cols) * w, (i // cols) * h
    sheet.paste(Image.open(f'{OUT}/开头三B-{t}秒.png').convert('RGB').resize((w, h), Image.LANCZOS), (x, y))
    label(draw, x, y, f'{t} 秒')
sheet.save(f'{OUT}/拼版.png')

# 28.0 frame, style frame, and their difference times ten.
frame = Image.open(f'{OUT}/开头三B-28.0秒.png').convert('RGB')
style = Image.open(STYLE).convert('RGB').resize(frame.size, Image.LANCZOS)
diff = ImageChops.difference(frame, style).point(lambda v: min(255, v * 10))
out = Image.new('RGB', (960 * 3, 540), '#ffffff')
draw = ImageDraw.Draw(out, 'RGBA')
for i, (im, text) in enumerate([(frame, '28.0 秒画面'), (style, '样式图'), (diff, '差异 ×10')]):
    out.paste(im.resize((960, 540), Image.LANCZOS), (960 * i, 0))
    label(draw, 960 * i, 0, text)
out.save(f'{OUT}/对样式图.png')
d = ImageChops.difference(frame, style).convert('L')
print('style diff px>8:', sum(d.histogram()[9:]), 'of', frame.size[0] * frame.size[1])
