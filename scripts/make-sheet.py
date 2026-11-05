"""Tile the four light style frames into one 1920x1080 review sheet."""
import os
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = os.environ.get('PROJECT_ROOT', os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
ROOT = PROJECT_ROOT
OUT = f'{ROOT}/review/style-frames/四张拼版.png'
TILES = [
    (f'{ROOT}/样式图/开头0-03一枚叶片-浅色.png', '开头0-03一枚叶片', 0, 0),
    (f'{ROOT}/样式图/开头0-28树变成网-浅色.png', '开头0-28树变成网', 960, 0),
    (f'{ROOT}/样式图/问题三第三步-浅色.png', '问题三第三步', 0, 540),
    (f'{ROOT}/样式图/问题三停用后旧答案变红-浅色.png', '问题三停用后旧答案变红', 960, 540),
]
font = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', 22)
sheet = Image.new('RGB', (1920, 1080), '#ffffff')
draw = ImageDraw.Draw(sheet, 'RGBA')
for path, label, x, y in TILES:
    sheet.paste(Image.open(path).convert('RGB').resize((960, 540), Image.LANCZOS), (x, y))
    box = draw.textbbox((0, 0), label, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    draw.rectangle([x + 16, y + 16, x + 16 + w + 20, y + 16 + h + 16], fill=(255, 255, 255, 205))
    draw.text((x + 26, y + 22), label, font=font, fill=(28, 34, 40))
sheet.save(OUT)
print(OUT, sheet.size)
