"""Join the exported segments, check the seams, and write the two finished files.

Usage:
  assemble.py --seg opening.mkv:0:30 --seg film.mkv:30:103 --seg ending.mkv:103:120
              --audio 音频/全片音效.wav --out 成片/本体能力演示 [--pad-audio]

Segments are given in order as FILE:START:END and must touch: each one has to
start where the one before it ended, and hold exactly (END - START) * 60 frames.
The result is a lossless join, a pixel-exact check either side of every seam, a
4K60 file (crf 14) and a 1080p file (crf 16) with the audio track, ffprobe checks,
two contact sheets, a JSON record, and no intermediates left behind.

--pad-audio lets a short audio track pass for a dry run by filling it with
silence; it must not be used for the finished film.
"""
import argparse, json, os, subprocess, sys, tempfile, time

FPS = 60
PAD_ONLY = 'dry run only'


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def probe(path):
    out = run(['ffprobe', '-v', 'error', '-show_entries',
               'stream=codec_type,width,height,r_frame_rate,nb_frames,duration',
               '-show_entries', 'format=duration', '-of', 'json', path]).stdout
    data = json.loads(out)
    info = {'duration': float(data['format']['duration']), 'video': None, 'audio': None}
    for st in data['streams']:
        if st['codec_type'] == 'video' and info['video'] is None:
            num, den = st['r_frame_rate'].split('/')
            info['video'] = {'width': int(st['width']), 'height': int(st['height']),
                             'fps': float(num) / float(den),
                             'frames': int(st.get('nb_frames') or 0),
                             'duration': float(st.get('duration') or 0)}
        elif st['codec_type'] == 'audio' and info['audio'] is None:
            info['audio'] = {'duration': float(st.get('duration') or 0)}
    return info


def frame_png(path, index, out):
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', path,
                    '-vf', f'select=eq(n\\,{index})', '-frames:v', '1', out], check=True)
    return out


def frame_diff(a, b):
    from PIL import Image, ImageChops, ImageStat
    ia, ib = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    return sum(ImageStat.Stat(ImageChops.difference(ia, ib)).mean) / 3


def parse_seg(text):
    parts = text.rsplit(':', 2)
    if len(parts) != 3:
        raise SystemExit(f'bad --seg {text}, want FILE:START:END')
    return {'file': parts[0], 'start': float(parts[1]), 'end': float(parts[2])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seg', action='append', required=True)
    ap.add_argument('--audio', required=True)
    ap.add_argument('--out', required=True, help='path without extension, e.g. 成片/本体能力演示')
    ap.add_argument('--pad-audio', action='store_true', help=PAD_ONLY)
    args = ap.parse_args()

    segs = [parse_seg(s) for s in args.seg]
    total = segs[-1]['end']
    record = {'segments': [], 'steps': {}, 'seams': [], 'outputs': []}

    # 1. the segments must touch and hold the frames they claim
    t0 = time.time()
    for i, seg in enumerate(segs):
        if i and abs(seg['start'] - segs[i - 1]['end']) > 1e-6:
            raise SystemExit(f"gap or overlap at {segs[i - 1]['end']}: next starts {seg['start']}")
        info = probe(seg['file'])
        want = int(round((seg['end'] - seg['start']) * FPS))
        got = info['video']['frames']
        rec = {'file': seg['file'], 'start': seg['start'], 'end': seg['end'],
               'frames': got, 'want': want, 'duration': round(info['duration'], 3)}
        record['segments'].append(rec)
        if abs(got - want) > 1:
            raise SystemExit(f"{seg['file']} has {got} frames, the span wants {want}")
        if abs(info['duration'] - (seg['end'] - seg['start'])) > 1 / FPS:
            raise SystemExit(f"{seg['file']} lasts {info['duration']:.3f}s, the span is {seg['end'] - seg['start']:.3f}s")
    record['steps']['check segments'] = round(time.time() - t0, 2)
    print(f"segments ok: {len(segs)}, {total:.3f}s", flush=True)

    tmp = tempfile.mkdtemp(prefix='final-')
    combined = os.path.join(tmp, 'combined.mkv')
    listing = os.path.join(tmp, 'list.txt')
    with open(listing, 'w') as f:
        for seg in segs:
            f.write(f"file '{os.path.abspath(seg['file'])}'\n")

    # 2. lossless join; re-encode only if the parts do not fit together
    t0 = time.time()
    joined = subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                             '-f', 'concat', '-safe', '0', '-i', listing,
                             '-c', 'copy', combined], capture_output=True, text=True)
    method = 'copy'
    if joined.returncode != 0:
        print('copy failed, re-encoding losslessly', flush=True)
        run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
             '-i', listing, '-c:v', 'libx264', '-qp', '0', '-preset', 'ultrafast',
             '-pix_fmt', 'yuv444p', combined])
        method = 're-encode'
    record['steps']['join'] = {'seconds': round(time.time() - t0, 2), 'method': method}
    print(f'joined by {method} in {record["steps"]["join"]["seconds"]}s', flush=True)

    # 3. every seam: the same frames as the source, and how much the picture
    #    changes across the cut (reported, not judged)
    t0 = time.time()
    for i in range(1, len(segs)):
        seam = segs[i]['start']
        prev, nxt = segs[i - 1], segs[i]
        checks = []
        for t in (seam - 2 / FPS, seam - 1 / FPS, seam, seam + 1 / FPS):
            src = prev if t < seam else nxt
            local = int(round((t - src['start']) * FPS))
            if local < 0 or local >= int(round((src['end'] - src['start']) * FPS)):
                continue
            a = frame_png(combined, int(round(t * FPS)), os.path.join(tmp, 'c.png'))
            b = frame_png(src['file'], local, os.path.join(tmp, 's.png'))
            from PIL import Image, ImageChops
            same = ImageChops.difference(Image.open(a).convert('RGB'), Image.open(b).convert('RGB')).getbbox() is None
            checks.append({'t': round(t, 4), 'same': same})
        before = frame_png(combined, int(round((seam - 1 / FPS) * FPS)), os.path.join(tmp, 'b.png'))
        after = frame_png(combined, int(round(seam * FPS)), os.path.join(tmp, 'a.png'))
        rec = {'at': seam, 'frames': checks, 'step_diff': round(frame_diff(before, after), 3)}
        record['seams'].append(rec)
        bad = [c for c in checks if not c['same']]
        if bad:
            raise SystemExit(f'seam at {seam}s does not match the source: {bad}')
    record['steps']['seams'] = round(time.time() - t0, 2)
    print('seams ok:', ', '.join(f"{s['at']}s step {s['step_diff']}" for s in record['seams']) or 'none', flush=True)

    # 4. the two finished files, each with the audio from zero
    audio = probe(args.audio)['audio']['duration']
    if audio < total - 1 / FPS and not args.pad_audio:
        raise SystemExit(f'audio lasts {audio:.2f}s, the film is {total:.2f}s; pad it or fix the track')
    af = ['-af', f'apad=whole_dur={total}'] if audio < total - 1 / FPS else []
    height = probe(combined)['video']['height']
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    fourk = f'{args.out}-4K60.mp4'
    small = f'{args.out}-1080p.mp4'
    common = ['-map', '0:v:0', '-map', '1:a:0', '-r', str(FPS),
              '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-ac', '2',
              '-movflags', '+faststart', '-t', f'{total}']
    t0 = time.time()
    up = ['-vf', 'scale=3840:2160:flags=lanczos'] if height != 2160 else []
    run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', combined, '-i', args.audio,
         *common, *af, *up, '-c:v', 'libx264', '-profile:v', 'high', '-crf', '14',
         '-preset', 'slow', '-pix_fmt', 'yuv420p', fourk])
    t4k = round(time.time() - t0, 1)
    t0 = time.time()
    run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', combined, '-i', args.audio,
         *common, *af, '-vf', 'scale=1920:1080:flags=lanczos', '-c:v', 'libx264',
         '-crf', '16', '-preset', 'slow', '-pix_fmt', 'yuv420p', small])
    record['steps']['encode'] = {'4k': t4k, '1080p': round(time.time() - t0, 1)}
    print(f'encoded 4K in {t4k}s and 1080p in {record["steps"]["encode"]["1080p"]}s', flush=True)

    # 5. ffprobe both
    t0 = time.time()
    want_frames = int(round(total * FPS))
    for path in (fourk, small):
        info = probe(path)
        v, a = info['video'], info['audio']
        ok = (v['frames'] == want_frames and abs(info['duration'] - total) <= 1 / FPS
              and abs(a['duration'] - total) <= 1 / FPS
              and v['fps'] == FPS
              and (v['width'], v['height']) == ((3840, 2160) if path == fourk else (1920, 1080)))
        rec = {'file': path, 'duration': round(info['duration'], 3), 'frames': v['frames'],
               'size': [v['width'], v['height']], 'fps': v['fps'],
               'audio': round(a['duration'], 3), 'ok': ok}
        record['outputs'].append(rec)
        if not ok:
            raise SystemExit(f'{path} failed its ffprobe check: {rec}')
    record['steps']['ffprobe'] = round(time.time() - t0, 2)
    print('ffprobe ok for both files', flush=True)

    # 6. two contact sheets, jpg so they stay small
    t0 = time.time()
    folder = os.path.dirname(os.path.abspath(args.out))
    every05 = os.path.join(folder, '拼版-每0.5秒.jpg')
    every3 = os.path.join(folder, '拼版-每3秒.jpg')
    run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', small,
         '-vf', 'fps=2,scale=480:270,tile=12x20', '-frames:v', '1', '-q:v', '4', every05])
    run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', small,
         '-vf', 'fps=1/3,scale=480:270,tile=8x5', '-frames:v', '1', '-q:v', '4', every3])
    record['steps']['sheets'] = round(time.time() - t0, 2)
    record['sheets'] = {os.path.basename(p): round(os.path.getsize(p) / 1e6, 2) for p in (every05, every3)}
    if os.path.getsize(every05) > 20e6:
        raise SystemExit(f'{every05} is over 20 MB')
    print('sheets:', record['sheets'], flush=True)

    # 7. the record, and 8. no intermediates
    with open(os.path.join(folder, '成片记录.json'), 'w') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    subprocess.run(['rm', '-rf', tmp], check=True)
    print('done')


if __name__ == '__main__':
    main()
