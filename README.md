# 本体能力演示 · 航空发动机制造

一支约 2 分钟的演示影片，讲「本体」在航空发动机工厂里能做什么。片子已经做完，成品视频在本仓库的 [Release v1.0](https://github.com/SegawaBeer/ontology-demo-film/releases/tag/v1.0) 里下载，代码和全部过程文档在这个仓库里。

- **无字幕版**：120 秒，4K 60 帧和 1080p 两份。
- **字幕版**：135.2 秒，加了 22 条旁白字幕和 7 张转场标题卡，4K、1080p 和 srt 字幕文件。
- 画面分三栏：左边对话框，中间三维发动机，右边本体族谱（对象和关系组成的网）。开头和结尾是左右分屏。
- 片中的公司、批次、工单、数字全部是虚构的演示数据，查询和执行都由程序模拟，不接任何真实平台，也不出现任何产品标识。
- 整个制作过程怎么做的、用了什么、踩过什么坑，见 [docs/实现过程.md](docs/实现过程.md)。

## 片子讲了什么

一个夜里，02:07 到第二天 09:00，工厂里四个部门各遇到一个普通问题：

1. **研发 02:07**：第一级涡轮叶片的冷却孔缩小 0.1 毫米，会影响到哪些东西？
2. **总装 02:11**：7 号发动机明早 9 点能按时上试车台吗？结论是可以。
3. **质量 02:15**：一批涂层粉末杂质超标。查出用到这批粉末的 46 枚叶片，7 号发动机上的 16 枚被停用，问题二的「可以按时」自己变成红色。
4. **供应链 02:24**：缺的 16 枚最快什么时候补齐？本库 6 枚加二号厂区 10 枚，05:10 到齐，问题二的答案又变回绿色。

结尾回到开头那一枚叶片和那一个节点：「同一套对象，整个工厂一起用。」

## 文件夹

| 位置 | 内容 |
| --- | --- |
| `src/` | 网页程序。`src/frames/` 是影片的各个画面页，其余是可以拖动、拆开看的三维发动机 |
| `public/` | 三维模型、字体、环境光贴图和它们的许可文件 |
| `tools/` | 把下载的原始模型拆成零件、生成叶片和轮盘的 Python 程序 |
| `scripts/` | 逐帧导出、自动检查、截图拼版的程序 |
| `scripts/audio/` | 音效合成和混音 |
| `scripts/final/` | 成片导出：逐帧无损导出、拼接、合音轨、核对 |
| `docs/实现过程.md` | 完整的制作过程记录 |
| `docs/脚本/` | 影片脚本 v1.0–v1.3、本体结构清单 v1.0–v1.2、字幕方案 v1.0–v1.1 |
| `docs/任务说明/` | 每一块活的任务说明；`成片总计划.md` 是总计划和进度记录 |
| `docs/review/` | 每一轮的检查结果、报告和验收截图 |
| `docs/样式图/` | 四张定稿样式图（浅色），未选用的放在 `未选用/` |
| `docs/成片说明/`、`docs/音频说明/` | 成片和声音的说明、检查记录 |
| `docs/交接说明.md` | 2026-10-26 换会话时写的交接说明 |
| `THIRD_PARTY_NOTICES.md` | 第三方素材和代码的来源与许可 |

成品视频、样片和音轨体积大，不放进 git，全部在 Release 里。
## 下载成品

[Release v1.0](https://github.com/SegawaBeer/ontology-demo-film/releases/tag/v1.0) 里有：四份成品视频、srt 字幕、四张整片抽帧拼版、制作中途的样片、各版音轨和带声预览。每个文件是什么，Release 说明里逐条写了。

正式使用请选 4K 60 帧那份；1080p 内容完全相同，方便发送和预览。声音整体偏轻（约 −23 LUFS），播放时音量开大一点。

## 准备环境

只在 macOS（Apple 芯片）上跑通过。需要：

- Node 22.18 以上（实际用 26.3.1）和 npm；
- 系统 Python 3（实际用 Homebrew 的 3.14.6），装 Playwright 和 Pillow；
- 一个单独的 Python 虚拟环境，装 numpy 和 scipy，给声音程序用；
- ffmpeg 和 ffprobe（实际用 8.1.2，需要带 libx264）；
- Google Chrome。导出时用无头 Chrome 调 Metal 显卡渲染，不需要另装 Playwright 自带的浏览器。

```sh
npm ci
python3 -m pip install playwright==1.60.0 pillow==12.2.0
python3 -m venv .venv-audio
.venv-audio/bin/pip install numpy==2.3.4 scipy==1.16.3
```

声音程序默认用 `/opt/homebrew/bin/python3` 去读页面（它要有 Playwright）。系统 Python 不在这个位置时，先 `export SYSTEM_PY=$(which python3)`。

## 本地预览

```sh
npm run dev
```

打开终端里给出的地址：

- 根地址是可以拖动、拆开、单独看某个零件的三维发动机。
- 影片画面在 `frames.html` 下，按 `frame=` 选段，打开就按实时播放：
  - `frames.html?frame=opening&theme=light`：开头 0–30 秒；
  - `frames.html?frame=film&theme=light`：30–103 秒，三栏和四个问题；
  - `frames.html?frame=ending&theme=light`：结尾 103–120 秒；
  - `frames.html?frame=card&id=0&theme=light`：转场标题卡，`id` 从 0 到 6。
- 加 `&t=70` 停在某一秒；加 `&narration=1` 显示旁白字幕；加 `&play=0` 停在开头不动，等程序逐帧驱动。

## 重新做出成片

结论先说：先构建静态页面，用一个本地静态服务器提供；再出音轨、逐帧导出三段画面、拼接合成、核对。全部命令在仓库根目录执行。4K 无字幕版约 45 分钟，字幕版约一个半小时；三段无损中间文件要 3–8 GB 磁盘。

不要用开发服务器导出：它在长时间导出中会自己刷新页面，导出会断。

### 第一步：构建并提供静态页面（另开一个终端，一直开着）

```sh
npx tsc && npx vite build --outDir /tmp/film-dist --emptyOutDir
python3 -m http.server 5198 --bind 127.0.0.1 --directory /tmp/film-dist
```

后面的命令都用这个地址：

```sh
P=http://127.0.0.1:5198/frames.html
mkdir -p /tmp/final /tmp/sub/cards
```

### 第二步：无字幕版（120 秒，7,200 帧）

```sh
# 音轨，打印 18/18 checks passed 才算过，产出 音频/全片音效.wav
.venv-audio/bin/python scripts/audio/build_film_audio.py \
  --film "$P?frame=film&theme=light&play=0" --ending "$P?frame=ending&theme=light&play=0"

# 三段 4K 无损画面（中间文件用 .mp4，拼接程序要从文件里读帧数，.mkv 读不到）
python3 scripts/final/export_segment.py "$P?frame=opening&theme=light" /tmp/final/opening.mp4 0 30 --scale 2
python3 scripts/final/export_segment.py "$P?frame=film&theme=light" /tmp/final/film.mp4 30 103 --scale 2
python3 scripts/final/export_segment.py "$P?frame=ending&theme=light" /tmp/final/ending.mp4 103 120 --scale 2

# 拼接、比对拼接点、出 4K 和 1080p、合音轨、出拼版
python3 scripts/final/assemble.py --seg /tmp/final/opening.mp4:0:30 --seg /tmp/final/film.mp4:30:103 \
  --seg /tmp/final/ending.mp4:103:120 --audio 音频/全片音效.wav --out 成片/本体能力演示

# 核对：每 2 秒抽一帧和页面比，量响度和峰值
python3 scripts/final/check_final.py 成片/本体能力演示-4K60.mp4 \
  --seg "$P?frame=opening&theme=light:0:30" --seg "$P?frame=film&theme=light:30:103" \
  --seg "$P?frame=ending&theme=light:103:120"
```

某段导出中途断了，可以加 `--from-frame N` 从第 N 帧续导成另一个文件，把它当下一段传给拼接程序。

### 第三步：字幕版（135.2 秒，8,112 帧）

```sh
# 音轨：在事件这一级给七张卡让出时间，产出 音频/全片音效-字幕版.wav
.venv-audio/bin/python scripts/audio/build_subtitled_audio.py --pages "$P"

# 三段带旁白的画面
python3 scripts/final/export_segment.py "$P?frame=opening&theme=light&narration=1" /tmp/sub/opening.mp4 0 30 --scale 2
python3 scripts/final/export_segment.py "$P?frame=film&theme=light&narration=1" /tmp/sub/film.mp4 30 103 --scale 2
python3 scripts/final/export_segment.py "$P?frame=ending&theme=light&narration=1" /tmp/sub/ending.mp4 103 120 --scale 2

# 七张卡的背景：插入点那一帧的定格画面，放进静态页面目录
python3 scripts/final/build_subtitled.py stills --opening /tmp/sub/opening.mp4 --film /tmp/sub/film.mp4 --dir /tmp/film-dist/cards

# 七张卡，「编号:长度」，长度单位是秒
for kd in 0:2.4 1:2.4 2:2 3:2 4:2 5:2 6:2.4; do
  k=${kd%%:*}; d=${kd#*:}
  python3 scripts/final/export_segment.py "$P?frame=card&id=$k&theme=light&bg=http://127.0.0.1:5198/cards/c$k.png" \
    /tmp/sub/cards/card$k.mp4 0 $d --scale 2
done

# 拼接（逐帧和来源比对）、出 4K 和 1080p、srt、拼版
python3 scripts/final/build_subtitled.py assemble --opening /tmp/sub/opening.mp4 --film /tmp/sub/film.mp4 \
  --ending /tmp/sub/ending.mp4 --cards /tmp/sub/cards --audio 音频/全片音效-字幕版.wav --out 成片/本体能力演示-字幕版

# 核对：每 2 秒抽一帧和页面比
python3 scripts/final/build_subtitled.py check 成片/本体能力演示-字幕版-4K60.mp4 \
  --pages "$P" --bg http://127.0.0.1:5198/cards --report /tmp/sub/check.json
```

做完删掉 /tmp/final、/tmp/sub 和 /tmp/film-dist，关掉静态服务器。

### 关于其它检查程序

`scripts/` 下以 check 开头的程序是制作中每一段的自动检查，当时对着几个固定端口的开发服务器跑（开头 5192/5193，主时间轴 5194/5195），结果写进 `docs/review/`。它们记录了每段的验收标准，重跑前要按各自文件开头的说明起好服务器。

三维模型由 `tools/convert_turbofan.py` 从 Sketchfab 下载的原始模型转换而来，转换结果已经在 `public/models/` 里，不重做也能运行。

## 来源与许可

- 本项目自己的代码用 MIT 许可（见 `LICENSE`，保留了上游项目的版权声明）。
- 界面和场景结构改编自 AlexZhangji 的 [Turbine Explorer](https://github.com/AlexZhangji/turbine-explorer)（MIT），特写镜头里那枚冷却叶片移植自它的叶片研究页。
- 发动机三维模型：[Turbine | Turbofan Engine | Jet Engine](https://sketchfab.com/3d-models/turbine-turbofan-engine-jet-engine-74c6aceed86b4a41aaad3b93afc3e262)，作者 blenderbirb，Sketchfab，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。本项目把它拆成了 9 个模块、51 个组件、2,027 个零件，并替换了第一级涡轮叶片。
- 字体：IBM Plex Mono、Manrope、Space Grotesk，都是 SIL Open Font License 1.1，许可全文在 `public/fonts/`。
- 环境光贴图：Poly Haven 的两张摄影棚 HDR，CC0，来源见 `public/environment/README.md`。
- 声音全部由程序合成，没有用任何录音素材。
- Three.js（MIT）、Vite（MIT）、TypeScript（Apache-2.0），完整说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

片中出现的企业名（澄岭新材料、启衡航空部件、西砚精密铸造、澜川航空）都是虚构的，和真实企业无关。
