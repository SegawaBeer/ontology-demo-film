"""Put the effects track under a video (声音任务说明.md 7.6).

    .venv-audio/bin/python scripts/audio/mux.py VIDEO AUDIO.wav OUT.mp4

The video stream is copied as it is (no re-encode); the audio is encoded to
AAC 320 kb/s, 48 kHz (Apple's AudioToolbox encoder).  Checks, written to
OUT.mux.json (exit status 1 if one fails):
- video: every video packet of OUT is byte-identical to VIDEO's;
- audio: AAC, 48 kHz, stereo, about 320 kb/s;
- lengths: audio and video durations differ by at most one frame;
- start: the audio stream starts at 0, and the decoded audio lines up with
  AUDIO.wav with no offset (cross-correlation lag 0 samples); the stream's
  declared length (and Apple's count of valid samples) equals the WAV's.
"""
import json
import os
import re
import subprocess
import sys

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_audio  # noqa: E402

FFMPEG = make_audio.FFMPEG
FFPROBE = '/opt/homebrew/bin/ffprobe'
AFINFO = '/usr/bin/afinfo'
SR = 48000
BITRATE = '320k'
MAX_LAG = 4096                  # samples searched each way for the offset


def run(cmd, binary=False):
    r = subprocess.run(cmd, capture_output=True, text=not binary)
    if r.returncode != 0:
        err = r.stderr.decode(errors='replace') if binary else r.stderr
        raise SystemExit(f'{cmd[0]} failed:\n{err[-2000:]}')
    return r.stdout


def probe(path, sel):
    out = run([FFPROBE, '-v', 'error', '-select_streams', sel, '-show_entries',
               'stream=codec_name,sample_rate,channels,bit_rate,start_time,duration,duration_ts,nb_frames,r_frame_rate',
               '-of', 'json', path])
    return json.loads(out)['streams'][0]


def packet_hashes(path):
    out = run([FFMPEG, '-hide_banner', '-v', 'error', '-i', path, '-map', '0:v:0', '-c', 'copy',
               '-f', 'framemd5', '-'])
    return [line.rsplit(',', 1)[1].strip() for line in out.splitlines() if line and not line.startswith('#')]


def decoded_audio(path):
    raw = run([FFMPEG, '-hide_banner', '-v', 'error', '-i', path, '-map', '0:a:0', '-f', 'f32le',
               '-ac', '2', '-ar', str(SR), '-'], binary=True)
    return np.frombuffer(raw, dtype='<f4').reshape(-1, 2).astype(np.float64)


def offset_samples(ref, got):
    """Lag (samples) at which `got` best matches `ref`; positive = got is late."""
    a, b = ref.sum(axis=1), got.sum(axis=1)
    n = min(len(a), len(b))
    c = signal.correlate(b[:n], a[:n], mode='full', method='fft')
    mid = n - 1
    win = c[mid - MAX_LAG:mid + MAX_LAG + 1]
    return int(np.argmax(win)) - MAX_LAG


def mux(video, audio, out):
    run([FFMPEG, '-hide_banner', '-v', 'error', '-y', '-i', video, '-i', audio,
         '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
         '-c:a', 'aac_at', '-aac_at_mode', 'cbr', '-b:a', BITRATE, '-ar', str(SR), '-ac', '2',
         '-movflags', '+faststart', out])


def check(video, audio, out):
    ok, res = {}, {}
    v_in, v_out = packet_hashes(video), packet_hashes(out)
    ok['video_copied'] = v_in == v_out
    res['video_copied'] = {'packets': len(v_out), 'source_packets': len(v_in)}

    vs, a = probe(out, 'v:0'), probe(out, 'a:0')
    num, den = vs['r_frame_rate'].split('/')
    frame = int(den) / int(num)
    ok['audio_format'] = (a['codec_name'] == 'aac' and int(a['sample_rate']) == SR and int(a['channels']) == 2
                          and 300_000 <= int(a.get('bit_rate', 0)) <= 340_000)
    res['audio_format'] = {k: a.get(k) for k in ('codec_name', 'sample_rate', 'channels', 'bit_rate')}

    vd, ad = float(vs['duration']), float(a['duration'])
    ok['lengths'] = abs(vd - ad) <= frame + 1e-6
    res['lengths'] = {'video_s': vd, 'audio_s': ad, 'diff_frames': round(abs(vd - ad) / frame, 3)}

    ref, _, _ = make_audio.read_wav(audio)
    got = decoded_audio(out)
    lag = offset_samples(ref, got)
    n = min(len(ref), len(got))
    err = got[:n] - ref[:n]
    snr = 10 * np.log10(np.sum(ref[:n] ** 2) / max(np.sum(err ** 2), 1e-30))
    # The container trims the encoder's 2112 priming samples and its padding
    # after the end (MP4 edit list).  ffmpeg's decoder applies the first but
    # hands out the padding of the last packet, so the stream's declared
    # length is what players use; anything decoded past it must be silence.
    declared = int(a['duration_ts'])
    valid = apple_valid_frames(out)
    extra = got[len(ref):]
    extra_db = 20 * np.log10(max(float(np.abs(extra).max()) if len(extra) else 0.0, 1e-12))
    ok['start'] = (abs(float(a['start_time'])) < 1e-6 and abs(float(vs['start_time'])) < 1e-6
                   and lag == 0 and declared == len(ref) and valid in (None, len(ref))
                   and len(got) >= len(ref) and extra_db < -60.0)
    res['start'] = {'audio_start_s': float(a['start_time']), 'video_start_s': float(vs['start_time']),
                    'offset_samples': lag, 'declared_samples': declared, 'apple_valid_samples': valid,
                    'wav_samples': len(ref), 'decoded_past_end': len(extra),
                    'decoded_past_end_dbfs': round(float(extra_db), 1), 'aac_snr_db': round(float(snr), 1)}
    return ok, res


def apple_valid_frames(path):
    """Samples Apple's AudioToolbox counts as valid (afinfo), or None off macOS."""
    if not os.path.exists(AFINFO):
        return None
    m = re.search(r'(\d+) valid frames', run([AFINFO, path]))
    return int(m.group(1)) if m else None


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    video, audio, out = sys.argv[1:]
    mux(video, audio, out)
    ok, res = check(video, audio, out)
    ok = {k: bool(v) for k, v in ok.items()}
    record = {'video': os.path.abspath(video), 'audio': os.path.abspath(audio), 'out': os.path.abspath(out),
              'pass': all(ok.values()), 'ok': ok, 'results': res}
    with open(os.path.splitext(out)[0] + '.mux.json', 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
    for k, v in ok.items():
        print(f"{'PASS' if v else 'FAIL'}  {k:13s} {json.dumps(res[k], ensure_ascii=False)}")
    sys.exit(0 if record['pass'] else 1)


if __name__ == '__main__':
    main()
