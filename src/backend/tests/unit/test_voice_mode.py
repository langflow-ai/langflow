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
    # Use the newer numpy random Generator
    rng = np.random.default_rng()
    fake_frame_24k = (rng.random(duration_samples_24k) * 32767).astype(np.int16)
    frame_24k_bytes = fake_frame_24k.tobytes()

    assert len(frame_24k_bytes) == BYTES_PER_24K_FRAME  # 960

    # Resample
    frame_16k_bytes = resample_24k_to_16k(frame_24k_bytes)

    # Check length after resampling
    assert len(frame_16k_bytes) == BYTES_PER_16K_FRAME  # 640


def test_resample_24k_to_16k_invalid_frame():
    """Test that passing an invalid size frame raises a ValueError."""
    invalid_frame = b"\x00\x01" * 100  # only 200 bytes, not 960
    with pytest.raises(ValueError, match="Expected exactly"):
        _ = resample_24k_to_16k(invalid_frame)


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
    """End-to-end test.

    - Generate synthetic 24kHz audio
    - Break into 20ms frames
    - Resample to 16k
    - Check how many frames VAD detects as speech.
    This test is approximate, since random audio won't always be "speech."
    """
    # Instead of reading from a file, generate synthetic audio
    # Create 1 second of random audio data at 24kHz
    num_samples = SAMPLE_RATE_24K  # 1 second
    rng = np.random.default_rng(seed=42)  # Use a fixed seed for reproducibility

    # Generate random audio (this won't be detected as speech, but that's fine for testing)
    raw_data_24k = (rng.random(num_samples) * 32767).astype(np.int16).tobytes()

    # We'll chunk into 20ms frames (960 bytes each)
    frame_size_24k = BYTES_PER_24K_FRAME  # 960
    total_frames = len(raw_data_24k) // frame_size_24k

    vad = webrtcvad.Vad(mode=2)

    resampled_all = bytearray()
    speech_count = 0
    for i in range(total_frames):
        frame_24k = raw_data_24k[i * frame_size_24k : (i + 1) * frame_size_24k]
        frame_16k = resample_24k_to_16k(frame_24k)

        resampled_all.extend(frame_16k)  # Append to our buffer

        is_speech = vad.is_speech(frame_16k, VAD_SAMPLE_RATE_16K)
        if is_speech:
            speech_count += 1

    # For random noise, we expect very few frames to be detected as speech
    # We're not making a strict assertion, just verifying the process works
    assert len(resampled_all) == (total_frames * BYTES_PER_16K_FRAME)

    # Log the speech detection rate
    speech_count / total_frames if total_frames > 0 else 0
