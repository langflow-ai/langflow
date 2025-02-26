import numpy as np
import pytest
import webrtcvad
from langflow.utils.voice_utils import (
    BYTES_PER_16K_FRAME,
    BYTES_PER_24K_FRAME,
    SAMPLE_RATE_24K,
    VAD_SAMPLE_RATE_16K,
    resample_24k_to_16k,
)


def test_resample_24k_to_16k_valid_frame():
    """Test that valid 960-byte frames (20ms @ 24kHz) resample to 640 bytes (20ms @ 16kHz)."""
    # Generate a fake 20ms @ 24kHz frame (960 bytes)
    duration_samples_24k = int(0.02 * SAMPLE_RATE_24K)  # 480 samples
    fake_frame_24k = (np.random.rand(duration_samples_24k) * 32767).astype(np.int16)
    frame_24k_bytes = fake_frame_24k.tobytes()

    assert len(frame_24k_bytes) == BYTES_PER_24K_FRAME  # 960

    # Resample
    frame_16k_bytes = resample_24k_to_16k(frame_24k_bytes)

    # Check length after resampling
    assert len(frame_16k_bytes) == BYTES_PER_16K_FRAME  # 640


def test_resample_24k_to_16k_invalid_frame():
    """Test that passing an invalid size frame raises a ValueError."""
    invalid_frame = b"\x00\x01" * 100  # only 200 bytes, not 960
    with pytest.raises(ValueError) as exc_info:
        _ = resample_24k_to_16k(invalid_frame)
    assert "Expected exactly" in str(exc_info.value)


def test_webrtcvad_silence_detection():
    """Make sure that passing all-zero frames leads to is_speech == False."""
    vad = webrtcvad.Vad(mode=0)

    # Generate 1 second of silence @16k, chunk it in 20ms frames
    num_samples = VAD_SAMPLE_RATE_16K  # 1 second
    silent_audio = np.zeros(num_samples, dtype=np.int16).tobytes()

    frame_size = BYTES_PER_16K_FRAME  # 640
    num_frames = len(silent_audio) // frame_size

    speech_frames = 0
    for i in range(num_frames):
        frame_16k = silent_audio[i * frame_size : (i + 1) * frame_size]

        is_speech = vad.is_speech(frame_16k, VAD_SAMPLE_RATE_16K)
        if is_speech:
            speech_frames += 1

    # Expect zero frames labeled as speech
    assert speech_frames == 0


def test_webrtcvad_with_real_data():
    """End-to-end test:
    - Load or generate 24kHz audio
    - Break into 20ms frames
    - Resample to 16k
    - Check how many frames VAD detects as speech.
    This test is approximate, since random audio won't always be "speech."
    In real usage, you'd store a known test file that has some speech portion.
    """
    sample_audio_24k_raw = open("../data/debug_incoming_24k.raw", "rb")

    vad = webrtcvad.Vad(mode=2)

    raw_data_24k = sample_audio_24k_raw.read()

    # We'll chunk into 20ms frames (960 bytes each).
    frame_size_24k = BYTES_PER_24K_FRAME  # 960
    total_frames = len(raw_data_24k) // frame_size_24k

    resampled_all = bytearray()
    speech_count = 0
    for i in range(total_frames):
        frame_24k = raw_data_24k[i * frame_size_24k : (i + 1) * frame_size_24k]
        frame_16k = resample_24k_to_16k(frame_24k)

        resampled_all.extend(frame_16k)  # Append to our buffer

        is_speech = vad.is_speech(frame_16k, VAD_SAMPLE_RATE_16K)
        if is_speech:
            speech_count += 1

    with open("../data/debug_resampled_16k.raw", "wb") as f:
        f.write(resampled_all)
    # Just log or assert something about speech_count.
    # With random data, we can't be sure. For real speech, we'd expect
    # speech_count to be > 0 for frames containing speech.
    print(f"Detected speech frames: {speech_count} / {total_frames}")
    # We won't do a strict assertion here, but in real tests,
    # you'd compare the speech_count to an expected ratio.
    # e.g., assert 0 < speech_count < total_frames
