"""Bounded native video verification and lossless AVI display derivatives."""
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from fractions import Fraction


def _bounded(command, *, deadline, stdout_limit=1_000_000, stderr_limit=100_000, cancel=None,
             on_stdout=None, collect=True):
    """Drain both pipes incrementally; enforce bounds before accepting each chunk."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    assert process.stdout is not None and process.stderr is not None
    output = bytearray(); counts = {'stdout': 0, 'stderr': 0}
    selector = selectors.DefaultSelector()
    try:
        selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
        selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
        while selector.get_map():
            if cancel: cancel()
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise ValueError('Video subprocess exceeded time bounds')
            for key, _ in selector.select(min(.05, remaining)):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj); continue
                name = key.data; counts[name] += len(chunk)
                if counts[name] > (stdout_limit if name == 'stdout' else stderr_limit):
                    raise ValueError('Video subprocess exceeded output/decode bounds')
                if name == 'stdout':
                    if on_stdout: on_stdout(chunk)
                    if collect: output.extend(chunk)
        while process.poll() is None:
            if cancel:cancel()
            if time.monotonic()>=deadline:raise ValueError('Video subprocess exceeded time bounds')
            time.sleep(.05)
        if process.returncode: raise ValueError('Video subprocess failed')
        return bytes(output), counts
    finally:
        selector.close()
        # Descendants can still own the pipes after the leader exits.
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait()
        process.stdout.close(); process.stderr.close()


def _probe(path, deadline, cancel=None):
    executable = shutil.which('ffprobe')
    if not executable: raise ValueError('Native video verification requires ffprobe from FFmpeg')
    output, _ = _bounded([executable, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_entries',
        'format=duration,format_name:stream=codec_type,codec_name,width,height,pix_fmt,nb_frames,sample_rate,channels',
        '-of', 'json', str(path)], deadline=min(deadline, time.monotonic()+20), cancel=cancel)
    return json.loads(output)


def verify_mp4(data, *, cancel=None, deadline=None):
    if not 12 <= len(data) <= 250_000_000 or data[4:8] != b'ftyp':
        raise ValueError('Native video must be a bounded MP4 container')
    with tempfile.NamedTemporaryFile(suffix='.mp4') as source:
        source.write(data); source.flush()
        metadata = _probe(source.name, deadline or time.monotonic()+20, cancel)
    streams = [s for s in metadata.get('streams', []) if s.get('codec_type') == 'video']
    if not streams or any(not 1 <= s.get('width', 0)*s.get('height', 0) <= 50_000_000 for s in streams):
        raise ValueError('Native MP4 lacks a video stream within the pixel budget')
    return metadata


def _frames(path, *, pixels, deadline, cancel=None):
    executable = shutil.which('ffmpeg')
    if not executable: raise ValueError('Native AVI verification requires FFmpeg')
    frames = []; pending = bytearray(); time_base = None
    def consume(chunk):
        nonlocal time_base
        pending.extend(chunk)
        while b'\n' in pending:
            line, _, tail = pending.partition(b'\n'); pending[:] = tail
            if line.startswith(b'#tb 0:'):
                time_base = Fraction(line.split(b':', 1)[1].strip().decode())
            elif line and not line.startswith(b'#'):
                fields = [value.strip() for value in line.split(b',')]
                if len(fields) != 6 or time_base is None: raise ValueError('Invalid decoded-frame receipt')
                frames.append((fields[-2], fields[-1]))
                if len(frames) > 10_000 or pixels*len(frames) > 500_000_000:
                    raise ValueError('Native AVI actual decoded-frame/pixel bounds exceeded')
                end = (int(fields[2])+int(fields[3]))*time_base
                if end > 180: raise ValueError('Native AVI actual decoded duration bounds exceeded')
        if len(pending) > 1000: raise ValueError('Decoded-frame line exceeds bounds')
    _bounded([executable, '-v', 'error', '-xerror', '-nostdin', '-threads', '1', '-max_alloc', '268435456',
        '-protocol_whitelist', 'file,pipe', '-i', str(path), '-map', '0:v:0', '-f', 'framemd5', '-'],
        deadline=deadline, stdout_limit=2_000_000, cancel=cancel, on_stdout=consume, collect=False)
    if pending.strip() or not frames: raise ValueError('Incomplete or empty decoded-frame receipt')
    return frames


def verify_avi(data, *, decode=True, cancel=None):
    if not 12 <= len(data) <= 250_000_000 or data[:4] != b'RIFF' or data[8:12] != b'AVI ':
        raise ValueError('Native video must be a bounded AVI container')
    deadline = time.monotonic()+120
    with tempfile.NamedTemporaryFile(suffix='.avi') as source:
        source.write(data); source.flush()
        metadata = _probe(source.name, deadline, cancel)
        video = [s for s in metadata.get('streams', []) if s.get('codec_type') == 'video']
        audio = [s for s in metadata.get('streams', []) if s.get('codec_type') == 'audio']
        duration = float(metadata.get('format', {}).get('duration', 'nan'))
        if len(video) != 1 or len(audio) > 1 or not math.isfinite(duration) or not 0 < duration <= 180:
            raise ValueError('Native AVI duration or stream count exceeds bounds')
        stream = video[0]; pixels = stream.get('width', 0)*stream.get('height', 0)
        frames = int(stream.get('nb_frames', 0))
        if not 1 <= pixels <= 2_000_000 or not 1 <= frames <= 10_000 or pixels*frames > 500_000_000:
            raise ValueError('Native AVI declared video exceeds bounds')
        for entry in audio:
            if not 1 <= int(entry.get('sample_rate', 0)) <= 192_000 or not 1 <= entry.get('channels', 0) <= 8:
                raise ValueError('Native AVI audio exceeds bounds')
        if decode:
            actual = _frames(source.name, pixels=pixels, deadline=deadline, cancel=cancel)
            metadata['actual_decoded_video_frames'] = len(actual)
            if audio:
                rate = int(audio[0]['sample_rate']); channels = audio[0]['channels']
                maximum = min(500_000_000, int(180*rate*channels*2))
                _, counts = _bounded([shutil.which('ffmpeg'), '-v', 'error', '-xerror', '-nostdin', '-threads', '1',
                    '-max_alloc', '268435456', '-protocol_whitelist', 'file,pipe', '-i', source.name,
                    '-map', '0:a:0', '-c:a', 'pcm_s16le', '-f', 's16le', '-'], deadline=deadline,
                    stdout_limit=maximum, cancel=cancel, collect=False)
                if counts['stdout'] % (channels*2): raise ValueError('Incomplete decoded audio sample')
                metadata['actual_decoded_audio_samples'] = counts['stdout']//(channels*2)
    return metadata


def browser_video_render(data, *, max_output_bytes=100_000_000, cancel=None):
    """Exact decoded video frame parity; supported native audio packets are copied."""
    deadline = time.monotonic()+120
    metadata = verify_avi(data, decode=False, cancel=cancel)
    video = [s for s in metadata['streams'] if s['codec_type'] == 'video'][0]
    audio = [s for s in metadata['streams'] if s['codec_type'] == 'audio']
    if video['pix_fmt'] != 'yuv420p' or any(s['codec_name'] not in {'mp3', 'aac'} for s in audio):
        raise ValueError('AVI browser rendering requires native yuv420p video and MP3/AAC audio')
    executable = shutil.which('ffmpeg')
    if not executable: raise ValueError('AVI browser rendering requires FFmpeg')
    with tempfile.TemporaryDirectory(prefix='atlas-video-') as temporary:
        original = Path(temporary)/'original.avi'; rendered = Path(temporary)/'display.mp4'
        original.write_bytes(data)
        process = subprocess.Popen([executable, '-v', 'error', '-xerror', '-nostdin', '-threads', '1', '-max_alloc', '268435456',
            '-protocol_whitelist', 'file,pipe', '-i', str(original), '-map', '0:v:0', '-map', '0:a?', '-c:v', 'libx264',
            '-threads', '1', '-crf', '0', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', str(rendered)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            while process.poll() is None:
                if cancel: cancel()
                if time.monotonic() > deadline or (rendered.exists() and rendered.stat().st_size > max_output_bytes):
                    raise ValueError('AVI display rendering exceeded time/output bounds')
                time.sleep(.05)
            if process.returncode or not rendered.is_file() or rendered.stat().st_size > max_output_bytes:
                raise ValueError('AVI display rendering failed within its bounds')
            pixels = video['width']*video['height']
            native_frames = _frames(original, pixels=pixels, deadline=deadline, cancel=cancel)
            if native_frames != _frames(rendered, pixels=pixels, deadline=deadline, cancel=cancel):
                raise ValueError('Lossless video display differs from decoded original frames')
            output = rendered.read_bytes(); verify_mp4(output,cancel=cancel,deadline=deadline)
            return output, {'original_sha256': hashlib.sha256(data).hexdigest(), 'frames_verified': len(native_frames),
                'video_pixels': 'exact decoded yuv420p frame parity', 'audio': 'native MP3/AAC packets copied',
                'representation': 'lossless video display derivative'}
        finally:
            if process.poll() is None:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            process.wait()
