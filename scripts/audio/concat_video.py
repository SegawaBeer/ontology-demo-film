"""Join video files without a second lossy encode (声音任务说明.md 7.6).

    python3 scripts/audio/concat_video.py OUT.mp4 IN1.mp4 IN2.mp4 [...]

Runs with any python3 (only ffmpeg / ffprobe).  First tries ffmpeg's concat
demuxer with -c copy.  Accepted only if every decoded frame of OUT is
bit-identical to the matching frame of the inputs (ffmpeg framemd5) and the
frame times run on without a gap; on macOS, Apple's decoder must also show
the same pictures around each splice.  If not, the inputs are decoded and joined
into lossless H.264 (-qp 0): the frames are still exactly the inputs'
decoded frames.  Prints the splice frames (where each input starts in OUT)
and writes OUT.concat.json.  Exit status 1 if a check fails.
"""
import json
import os
import subprocess
import sys
import tempfile

FFMPEG = '/opt/homebrew/bin/ffmpeg'
FFPROBE = '/opt/homebrew/bin/ffprobe'
AVCONVERT = '/usr/bin/avconvert'


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f'{cmd[0]} failed:\n{r.stderr[-2000:]}')
    return r.stdout


def frame_hashes(path):
    """MD5 of every decoded video frame, in order."""
    out = run([FFMPEG, '-hide_banner', '-v', 'error', '-i', path, '-map', '0:v:0', '-f', 'framemd5', '-'])
    return [line.rsplit(',', 1)[1].strip() for line in out.splitlines() if line and not line.startswith('#')]


def frame_times(path):
    """Presentation time of every video frame, in seconds, from the packets."""
    out = run([FFPROBE, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'packet=pts_time',
               '-of', 'csv=p=0', path])
    return sorted(float(x) for x in out.split())


def stream(path):
    out = run([FFPROBE, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
               'stream=codec_name,profile,width,height,pix_fmt,r_frame_rate,start_time,duration,nb_frames',
               '-of', 'json', path])
    s = json.loads(out)['streams'][0]
    num, den = s['r_frame_rate'].split('/')
    s['fps'] = int(num) / int(den)
    return s


def join_copy(out, inputs):
    fd, lst = tempfile.mkstemp(suffix='.txt')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        for p in inputs:
            f.write("file '" + os.path.abspath(p).replace("'", "'\\''") + "'\n")
    try:
        run([FFMPEG, '-hide_banner', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst,
             '-map', '0:v:0', '-c', 'copy', '-movflags', '+faststart', out])
    finally:
        os.remove(lst)


def join_lossless(out, inputs, fps):
    args = [FFMPEG, '-hide_banner', '-v', 'error', '-y']
    for p in inputs:
        args += ['-i', p]
    chain = ''.join(f'[{i}:v:0]' for i in range(len(inputs))) + f'concat=n={len(inputs)}:v=1:a=0[v]'
    run(args + ['-filter_complex', chain, '-map', '[v]', '-c:v', 'libx264', '-qp', '0', '-preset', 'medium',
                '-pix_fmt', 'yuv420p', '-r', str(fps), '-movflags', '+faststart', out])


def avf_splice_psnr(out, splices, fps, half=1.0):
    """Lowest PSNR (dB) between Apple's decoder (avconvert to ProRes) and
    ffmpeg's over +-half s around each splice.  Two inputs with different
    picture parameter sets keep only the first input's copy in the MP4 header;
    the later ones decode from the copies inside the stream.  A decoder that
    ignored those would break up right after the splice (PSNR far below 30).
    ProRes 422 itself costs a few dB, so above 40 dB the pictures agree."""
    if not os.path.exists(AVCONVERT):
        return None
    worst = []
    with tempfile.TemporaryDirectory() as d:
        for i, f in enumerate(splices):
            t0 = max(0.0, f / fps - half)
            mov, log = os.path.join(d, f'{i}.mov'), os.path.join(d, f'{i}.log')
            run([AVCONVERT, '-s', out, '-p', 'PresetAppleProRes422LPCM', '-o', mov,
                 '--start', f'{t0:.6f}', '--duration', f'{2 * half:.6f}', '--replace'])
            run([FFMPEG, '-hide_banner', '-v', 'error', '-i', mov, '-ss', f'{t0:.6f}', '-t', f'{2 * half:.6f}',
                 '-i', out, '-lavfi', '[0:v]format=yuv420p,setpts=PTS-STARTPTS[a];'
                 f'[1:v]format=yuv420p,setpts=PTS-STARTPTS[b];[a][b]psnr=stats_file={log}', '-f', 'null', '-'])
            with open(log) as fh:
                vals = [float(line.split('psnr_avg:')[1].split()[0]) for line in fh if 'psnr_avg:' in line]
            if len(vals) < int(2 * half * fps) - 1:
                return 0.0
            worst.append(min(vals))
    return min(worst) if worst else None


def check(out, inputs, want_hashes, splices, fps):
    got = frame_hashes(out)
    times = frame_times(out)
    step = 1.0 / fps
    gaps = [i for i in range(len(times)) if abs(times[i] - i * step) > step / 4]
    first_bad = next((i for i, (a, b) in enumerate(zip(got, want_hashes)) if a != b), None)
    ok = {
        'frames': len(got) == len(want_hashes),
        'identical': len(got) == len(want_hashes) and first_bad is None,
        'times': not gaps and len(times) == len(got),
    }
    res = {'frames': len(got), 'expected_frames': len(want_hashes), 'first_different_frame': first_bad,
           'splice_frames': splices, 'splice_times': [times[i] if i < len(times) else None for i in splices],
           'time_gaps_at': gaps[:10], 'duration_s': len(got) / fps}
    if all(ok.values()):
        psnr = avf_splice_psnr(out, splices, fps)
        if psnr is not None:
            ok['apple_decoder'] = psnr >= 40.0
            res['apple_decoder_min_psnr_db'] = round(psnr, 2)
    return ok, res


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    out, inputs = sys.argv[1], sys.argv[2:]
    streams = [stream(p) for p in inputs]
    fps = streams[0]['fps']
    keys = ('codec_name', 'width', 'height', 'pix_fmt', 'fps')
    if any(tuple(s[k] for k in keys) != tuple(streams[0][k] for k in keys) for s in streams):
        raise SystemExit(f'inputs differ in {keys}: {streams}')
    hashes = [frame_hashes(p) for p in inputs]
    want = [h for hs in hashes for h in hs]
    splices = [sum(len(h) for h in hashes[:i]) for i in range(1, len(inputs))]

    join_copy(out, inputs)
    ok, res = check(out, inputs, want, splices, fps)
    method = 'concat demuxer, -c copy'
    if not all(ok.values()):
        first = dict(ok=ok, results=res)
        join_lossless(out, inputs, fps)
        ok, res = check(out, inputs, want, splices, fps)
        method = 'lossless H.264 (-qp 0); -c copy failed: ' + json.dumps(first)
    record = {'out': os.path.abspath(out), 'inputs': [os.path.abspath(p) for p in inputs], 'method': method,
              'input_frames': [len(h) for h in hashes], 'pass': all(ok.values()), 'ok': ok, 'results': res}
    with open(os.path.splitext(out)[0] + '.concat.json', 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
    for k, v in ok.items():
        print(f"{'PASS' if v else 'FAIL'}  {k}")
    print(json.dumps({k: record[k] for k in ('method', 'input_frames')} | res, ensure_ascii=False))
    sys.exit(0 if record['pass'] else 1)


if __name__ == '__main__':
    main()
