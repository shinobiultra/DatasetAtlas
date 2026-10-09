"""Bounded container inspection and full decoding of original article audio."""
import json
import math
import shutil
import subprocess
import tempfile
import time


def _decoded_samples(command, *, sample_rate, channels, max_samples, max_duration_seconds, timeout_seconds, cancel=None, deadline=None):
    """Count actual PCM without retaining it; cancel and reap through the shared pipe runner."""
    from dataset_atlas.adapters.remote_columnar import MediaLimitError
    from dataset_atlas.storage.video import _bounded
    byte_cap = min(max_samples, math.floor(max_duration_seconds * sample_rate) * channels) * 2
    try:
        _, counts = _bounded(command, deadline=deadline or time.monotonic()+timeout_seconds,
                             stdout_limit=byte_cap, cancel=cancel, collect=False)
    except ValueError as exc:
        if 'output/decode bounds' in str(exc):
            raise MediaLimitError('Native audio exceeds the actual decoded-sample or duration preview limit') from None
        if 'time bounds' in str(exc):
            raise MediaLimitError('Native audio full decoding exceeded the preview deadline') from None
        raise ValueError('Native audio decoding failed') from None
    count = counts['stdout']
    if count == 0 or count % (2 * channels):
        raise ValueError('Native audio decoding failed')
    return count // 2


def verify_audio(data,*,max_duration_seconds=7200,max_samples=500_000_000,timeout_seconds=120,cancel=None):
    from dataset_atlas.adapters.remote_columnar import MediaLimitError
    if not 12<=len(data)<=100_000_000:raise MediaLimitError('Native audio exceeds the100MB original-byte limit')
    from dataset_atlas.storage.video import _bounded
    deadline=time.monotonic()+timeout_seconds
    probe=shutil.which('ffprobe');decoder=shutil.which('ffmpeg')
    if not probe or not decoder:raise ValueError('Native audio verification requires FFmpeg and ffprobe')
    if not (data[:4] in (b'OggS',b'RIFF',b'fLaC',b'ID3\x03',b'ID3\x04') or data[:3]==b'ID3' or data[0]==255):
        raise ValueError('Native audio has an unsupported container header')
    demuxer='ogg' if data.startswith(b'OggS') else 'flac' if data.startswith(b'fLaC') else 'wav' if data.startswith(b'RIFF') else 'mp3'
    with tempfile.NamedTemporaryFile(suffix='.audio') as source:
        source.write(data);source.flush()
        try:
            output,_=_bounded([probe,'-v','error','-protocol_whitelist','file,pipe','-show_entries',
                'format=duration,format_name:stream=codec_type,codec_name,sample_rate,channels','-of','json','-f',demuxer,source.name],
                deadline=min(deadline,time.monotonic()+20),stdout_limit=100_000,cancel=cancel)
            metadata=json.loads(output);duration=float(metadata.get('format',{}).get('duration',0))
            streams=[item for item in metadata.get('streams',[]) if item.get('codec_type')=='audio']
            if not math.isfinite(duration) or not 0<duration<=max_duration_seconds:
                raise MediaLimitError('Native audio exceeds the preview duration limit')
            if len(streams)!=1 or any(not 1<=int(item.get('channels',0))<=8 or not 1<=int(item.get('sample_rate',0))<=192000 for item in streams):
                raise ValueError('Native audio requires one bounded audio stream')
            if duration*int(streams[0]['sample_rate'])*int(streams[0]['channels'])>max_samples:
                raise MediaLimitError('Native audio exceeds the decoded-sample preview limit')
            sample_rate=int(streams[0]['sample_rate']);channels=int(streams[0]['channels'])
            decoded_samples=_decoded_samples([decoder,'-v','error','-xerror','-nostdin','-threads','1','-max_alloc','268435456',
                '-protocol_whitelist','file,pipe','-f',demuxer,'-i',source.name,'-map','0:a:0','-vn','-sn','-dn',
                '-acodec','pcm_s16le','-ar',str(sample_rate),'-ac',str(channels),'-f','s16le','pipe:1'],
                sample_rate=sample_rate,channels=channels,max_samples=max_samples,
                max_duration_seconds=max_duration_seconds,timeout_seconds=timeout_seconds,cancel=cancel,deadline=deadline)
        except subprocess.TimeoutExpired:
            raise MediaLimitError('Native audio full decoding exceeded the preview deadline') from None
        except subprocess.CalledProcessError:
            raise ValueError('Native audio decoding failed') from None
        except ValueError as exc:
            if str(exc).startswith('Video subprocess'):
                raise ValueError('Native audio decoding failed') from None
            raise
    return {**metadata,'full_audio_decode_checked':True,'decoded_sample_count':decoded_samples,
            'decoded_sample_count_upper_bound':decoded_samples,
            'decoded_duration_seconds':decoded_samples/(sample_rate*channels)}
