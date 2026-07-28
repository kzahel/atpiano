from __future__ import annotations

import hashlib
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from atpiano.adapters.local_upload import LocalRecordingUploadAdapter
from atpiano.live import PcmBlock


def _stereo_wav(path: Path) -> bytes:
    frames = bytearray()
    for index in range(800):
        left = (index % 200 - 100) * 100
        right = -left
        frames.extend(left.to_bytes(2, "little", signed=True))
        frames.extend(right.to_bytes(2, "little", signed=True))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(8_000)
        output.writeframes(bytes(frames))
    return path.read_bytes()


@pytest.mark.parametrize(
    ("suffix", "media_type"),
    [(".wav", "audio/wav"), (".mp3", "audio/mpeg")],
)
def test_recording_upload_decodes_wav_and_mp3_to_one_source_clock(
    tmp_path: Path,
    suffix: str,
    media_type: str,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("FFmpeg upload boundary is unavailable")
    wav_path = tmp_path / "source.wav"
    _stereo_wav(wav_path)
    input_path = wav_path
    if suffix == ".mp3":
        input_path = tmp_path / "source.mp3"
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(wav_path),
                str(input_path),
            ],
            check=True,
        )
    adapter = LocalRecordingUploadAdapter(
        tmp_path / "workspace",
        minimum_free_bytes=0,
        ffmpeg_executable=ffmpeg,
        ffprobe_executable=ffprobe,
    )
    spool = adapter.new_spool_path()
    body = input_path.read_bytes()
    byte_count, sha256 = adapter.write_spool(
        spool,
        [body[:31], body[31:]],
        expected_bytes=len(body),
    )
    source = adapter.prepare(
        spool,
        filename=f"Practice take{suffix}",
        media_type=media_type,
        byte_count=byte_count,
        sha256=sha256,
    )
    blocks: list[PcmBlock] = []
    frame_count, block_count = source.stream(
        accept=lambda block, _received_ns: blocks.append(block)
    )

    assert source.sample_rate_hz == 8_000
    assert source.source_channels == 2
    assert frame_count > 0
    assert block_count == len(blocks)
    assert blocks[0].first_sample == 0
    assert all(
        following.first_sample
        == prior.first_sample + prior.frame_count
        for prior, following in zip(blocks, blocks[1:])
    )
    assert sum(block.frame_count for block in blocks) == frame_count
    provenance = source.provenance(
        state="accepted",
        decoded_frame_count=frame_count,
        decoded_block_count=block_count,
    )
    assert provenance["original"] == {
        "filename": f"Practice take{suffix}",
        "media_type": media_type,
        "byte_count": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    assert provenance["decode"]["channel_count"] == 1
    assert provenance["decode"]["downmix"] == "ffmpeg-default"
    source.close()
    assert not spool.exists()


def test_recording_upload_rejects_paths_sizes_and_truncated_bodies(
    tmp_path: Path,
) -> None:
    adapter = LocalRecordingUploadAdapter(
        tmp_path,
        minimum_free_bytes=0,
    )

    with pytest.raises(ValueError, match="wav or .mp3"):
        adapter.validate_request(
            filename="../../recording.flac",
            media_type="application/octet-stream",
            byte_count=100,
        )
    with pytest.raises(ValueError, match="WAV or MP3"):
        adapter.validate_request(
            filename="recording.wav",
            media_type="text/plain",
            byte_count=100,
        )
    spool = adapter.new_spool_path()
    with pytest.raises(ValueError, match="truncated"):
        adapter.write_spool(
            spool,
            [b"short"],
            expected_bytes=10,
        )
    assert not spool.exists()
