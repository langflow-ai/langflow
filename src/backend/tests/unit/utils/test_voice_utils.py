import base64
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import numpy as np
import pytest
from langflow.utils.voice_utils import (
    BYTES_PER_16K_FRAME,
    BYTES_PER_24K_FRAME,
    BYTES_PER_SAMPLE,
    FRAME_DURATION_MS,
    SAMPLE_RATE_24K,
    VAD_SAMPLE_RATE_16K,
    _write_bytes_to_file,
    resample_24k_to_16k,
    write_audio_to_file,
)


class TestConstants:
    """Test the audio constants."""

    def test_sample_rates(self):
        """Test sample rate constants."""
        assert SAMPLE_RATE_24K == 24000
        assert VAD_SAMPLE_RATE_16K == 16000

    def test_frame_duration(self):
        """Test frame duration constant."""
        assert FRAME_DURATION_MS == 20

    def test_bytes_per_sample(self):
        """Test bytes per sample constant."""
        assert BYTES_PER_SAMPLE == 2

    def test_bytes_per_frame_calculations(self):
        """Test frame size calculations."""
        # 24kHz: 24000 * 20 / 1000 * 2 = 960 bytes
        expected_24k = int(24000 * 20 / 1000) * 2
        assert expected_24k == BYTES_PER_24K_FRAME
        assert BYTES_PER_24K_FRAME == 960

        # 16kHz: 16000 * 20 / 1000 * 2 = 640 bytes
        expected_16k = int(16000 * 20 / 1000) * 2
        assert expected_16k == BYTES_PER_16K_FRAME
        assert BYTES_PER_16K_FRAME == 640


class TestResample24kTo16k:
    """Test cases for resample_24k_to_16k function."""

    def test_resample_correct_frame_size(self):
        """Test resampling with correct 960-byte frame."""
        # Create a 960-byte frame (480 samples of int16)
        rng = np.random.default_rng()
        samples_24k = rng.integers(-32768, 32767, 480, dtype=np.int16)
        frame_24k_bytes = samples_24k.tobytes()

        assert len(frame_24k_bytes) == BYTES_PER_24K_FRAME

        result = resample_24k_to_16k(frame_24k_bytes)

        # Should return 640 bytes (320 samples)
        assert len(result) == BYTES_PER_16K_FRAME
        assert isinstance(result, bytes)

        # Verify we can convert back to int16 array
        result_samples = np.frombuffer(result, dtype=np.int16)
        assert len(result_samples) == 320

    def test_resample_with_zero_audio(self):
        """Test resampling with silent audio (all zeros)."""
        # Create silent 24kHz frame
        samples_24k = np.zeros(480, dtype=np.int16)
        frame_24k_bytes = samples_24k.tobytes()

        result = resample_24k_to_16k(frame_24k_bytes)
        result_samples = np.frombuffer(result, dtype=np.int16)

        # Result should also be mostly zeros (allowing for minor resampling artifacts)
        assert np.max(np.abs(result_samples)) <= 1  # Very small values allowed

    def test_resample_with_sine_wave(self):
        """Test resampling with a known sine wave."""
        # Create a 1kHz sine wave at 24kHz sample rate
        t = np.linspace(0, 0.02, 480, endpoint=False)  # 20ms
        sine_wave = np.sin(2 * np.pi * 1000 * t)

        # Convert to int16 range
        samples_24k = (sine_wave * 16384).astype(np.int16)
        frame_24k_bytes = samples_24k.tobytes()

        result = resample_24k_to_16k(frame_24k_bytes)
        result_samples = np.frombuffer(result, dtype=np.int16)

        # Verify the resampled wave maintains similar characteristics
        assert len(result_samples) == 320
        # The amplitude should be preserved roughly
        assert np.max(result_samples) > 10000  # Should maintain significant amplitude
        assert np.min(result_samples) < -10000

    def test_resample_invalid_frame_size_too_small(self):
        """Test error handling for frame too small."""
        invalid_frame = b"\x00" * 959  # 959 bytes instead of 960

        with pytest.raises(ValueError, match=f"Expected exactly {BYTES_PER_24K_FRAME} bytes"):
            resample_24k_to_16k(invalid_frame)

    def test_resample_invalid_frame_size_too_large(self):
        """Test error handling for frame too large."""
        invalid_frame = b"\x00" * 961  # 961 bytes instead of 960

        with pytest.raises(ValueError, match=f"Expected exactly {BYTES_PER_24K_FRAME} bytes"):
            resample_24k_to_16k(invalid_frame)

    def test_resample_empty_frame(self):
        """Test error handling for empty frame."""
        with pytest.raises(ValueError, match=f"Expected exactly {BYTES_PER_24K_FRAME} bytes"):
            resample_24k_to_16k(b"")

    def test_resample_very_large_frame(self):
        """Test error handling for very large frame."""
        huge_frame = b"\x00" * 10000

        with pytest.raises(ValueError, match=f"Expected exactly {BYTES_PER_24K_FRAME} bytes"):
            resample_24k_to_16k(huge_frame)

    def test_resample_preserves_data_type(self):
        """Test that resampling preserves int16 data type."""
        # Create frame with extreme values
        samples_24k = np.array([32767, -32768] * 240, dtype=np.int16)  # 480 samples
        frame_24k_bytes = samples_24k.tobytes()

        result = resample_24k_to_16k(frame_24k_bytes)
        result_samples = np.frombuffer(result, dtype=np.int16)

        # Verify data type is preserved
        assert result_samples.dtype == np.int16
        # Values should still be in int16 range
        assert np.all(result_samples >= -32768)
        assert np.all(result_samples <= 32767)

    def test_resample_ratio_verification(self):
        """Test that the resampling ratio is approximately 2/3."""
        # Create a simple pattern
        samples_24k = np.tile(np.array([1000, -1000], dtype=np.int16), 240)  # 480 samples
        frame_24k_bytes = samples_24k.tobytes()

        result = resample_24k_to_16k(frame_24k_bytes)
        result_samples = np.frombuffer(result, dtype=np.int16)

        # Input: 480 samples, Output: 320 samples
        # Ratio: 320/480 = 2/3 ≈ 0.667
        ratio = len(result_samples) / len(samples_24k)
        assert abs(ratio - 2 / 3) < 0.001

    @patch("langflow.utils.voice_utils.resample")
    def test_resample_function_called(self, mock_resample):
        """Test that scipy.signal.resample is called correctly."""
        mock_resample.return_value = np.zeros(320, dtype=np.int16)

        samples_24k = np.zeros(480, dtype=np.int16)
        frame_24k_bytes = samples_24k.tobytes()

        resample_24k_to_16k(frame_24k_bytes)

        # Verify resample was called with correct parameters
        mock_resample.assert_called_once()
        args, _ = mock_resample.call_args
        input_array, target_samples = args

        assert len(input_array) == 480
        assert target_samples == 320  # int(480 * 2 / 3)


class TestWriteAudioToFile:
    """Test cases for write_audio_to_file function."""

    @pytest.mark.asyncio
    async def test_write_audio_to_file_success(self):
        """Test successful audio file writing."""
        audio_data = b"\x01\x02\x03\x04"
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        with (
            patch("langflow.utils.voice_utils.asyncio.to_thread") as mock_to_thread,
            patch("langflow.utils.voice_utils.logger") as mock_logger,
        ):
            mock_to_thread.return_value = None
            mock_logger.ainfo = AsyncMock()

            await write_audio_to_file(audio_base64, "test.raw")

            # Verify asyncio.to_thread was called correctly
            mock_to_thread.assert_called_once()
            args = mock_to_thread.call_args[0]
            assert args[0] == _write_bytes_to_file
            assert args[1] == audio_data
            assert args[2] == "test.raw"

            # Verify logging
            mock_logger.ainfo.assert_called_once_with(f"Wrote {len(audio_data)} bytes to test.raw")

    @pytest.mark.asyncio
    async def test_write_audio_to_file_default_filename(self):
        """Test writing with default filename."""
        audio_data = b"\x05\x06\x07\x08"
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        with patch("langflow.utils.voice_utils.asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = None

            await write_audio_to_file(audio_base64)

            # Should use default filename
            args = mock_to_thread.call_args[0]
            assert args[2] == "output_audio.raw"

    @pytest.mark.asyncio
    async def test_write_audio_to_file_base64_decode_error(self):
        """Test error handling for invalid base64."""
        invalid_base64 = "invalid base64 string!!!"

        with patch("langflow.utils.voice_utils.logger") as mock_logger:
            mock_logger.aerror = AsyncMock()
            await write_audio_to_file(invalid_base64, "test.raw")

            # Should log error
            mock_logger.aerror.assert_called_once()
            error_msg = mock_logger.aerror.call_args[0][0]
            assert "Error writing audio to file:" in error_msg

    @pytest.mark.asyncio
    async def test_write_audio_to_file_os_error(self):
        """Test error handling for OS errors during file writing."""
        audio_data = b"\x01\x02\x03\x04"
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        with (
            patch("langflow.utils.voice_utils.asyncio.to_thread") as mock_to_thread,
            patch("langflow.utils.voice_utils.logger") as mock_logger,
        ):
            mock_to_thread.side_effect = OSError("File write error")
            # Mock the async logger methods
            mock_logger.aerror = AsyncMock()

            await write_audio_to_file(audio_base64, "test.raw")

            # Should log error
            mock_logger.aerror.assert_called_once()
            error_msg = mock_logger.aerror.call_args[0][0]
            assert "Error writing audio to file:" in error_msg

    @pytest.mark.asyncio
    async def test_write_audio_to_file_empty_audio(self):
        """Test writing empty audio data."""
        empty_audio = b""
        audio_base64 = base64.b64encode(empty_audio).decode("utf-8")

        with (
            patch("langflow.utils.voice_utils.asyncio.to_thread") as mock_to_thread,
            patch("langflow.utils.voice_utils.logger") as mock_logger,
        ):
            mock_to_thread.return_value = None
            mock_logger.ainfo = AsyncMock()

            await write_audio_to_file(audio_base64, "empty.raw")

            # Should still work and log
            mock_to_thread.assert_called_once()
            mock_logger.ainfo.assert_called_once_with("Wrote 0 bytes to empty.raw")

    @pytest.mark.asyncio
    async def test_write_audio_to_file_large_audio(self):
        """Test writing large audio data."""
        large_audio = b"\x01" * 10000
        audio_base64 = base64.b64encode(large_audio).decode("utf-8")

        with (
            patch("langflow.utils.voice_utils.asyncio.to_thread") as mock_to_thread,
            patch("langflow.utils.voice_utils.logger") as mock_logger,
        ):
            mock_to_thread.return_value = None
            mock_logger.ainfo = AsyncMock()

            await write_audio_to_file(audio_base64, "large.raw")

            # Should handle large data correctly
            args = mock_to_thread.call_args[0]
            assert args[1] == large_audio
            mock_logger.ainfo.assert_called_once_with("Wrote 10000 bytes to large.raw")


class TestWriteBytesToFile:
    """Test cases for _write_bytes_to_file function."""

    def test_write_bytes_to_file_success(self):
        """Test successful bytes writing to file."""
        test_data = b"\x01\x02\x03\x04\x05"
        filename = "test_output.raw"

        mock_file = mock_open()
        with patch("langflow.utils.voice_utils.Path.open", mock_file):
            _write_bytes_to_file(test_data, filename)

            # Verify file was opened in append binary mode
            mock_file.assert_called_once_with("ab")
            # Verify data was written
            mock_file().write.assert_called_once_with(test_data)

    def test_write_bytes_to_file_path_construction(self):
        """Test that Path is constructed correctly."""
        test_data = b"\x06\x07\x08"
        filename = "test/path/file.raw"

        with patch("langflow.utils.voice_utils.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path.return_value = mock_path_instance

            _write_bytes_to_file(test_data, filename)

            # Verify Path was constructed with filename
            mock_path.assert_called_once_with(filename)
            # Verify open was called in append binary mode
            mock_path_instance.open.assert_called_once_with("ab")

    def test_write_bytes_to_file_empty_data(self):
        """Test writing empty bytes."""
        empty_data = b""
        filename = "empty.raw"

        mock_file = mock_open()
        with patch("langflow.utils.voice_utils.Path.open", mock_file):
            _write_bytes_to_file(empty_data, filename)

            # Should still attempt to write empty data
            mock_file().write.assert_called_once_with(empty_data)

    def test_write_bytes_to_file_large_data(self):
        """Test writing large bytes."""
        large_data = b"\xff" * 50000
        filename = "large.raw"

        mock_file = mock_open()
        with patch("langflow.utils.voice_utils.Path.open", mock_file):
            _write_bytes_to_file(large_data, filename)

            # Should write all data
            mock_file().write.assert_called_once_with(large_data)

    def test_write_bytes_to_file_append_mode(self):
        """Test that file is opened in append mode."""
        test_data = b"\x10\x11\x12"
        filename = "append_test.raw"

        mock_file = mock_open()
        with patch("langflow.utils.voice_utils.Path.open", mock_file):
            _write_bytes_to_file(test_data, filename)

            # Verify append binary mode
            mock_file.assert_called_once_with("ab")

    def test_write_bytes_to_file_context_manager(self):
        """Test that file is properly closed using context manager."""
        test_data = b"\x13\x14\x15"
        filename = "context_test.raw"

        mock_file = mock_open()
        with patch("langflow.utils.voice_utils.Path.open", mock_file):
            _write_bytes_to_file(test_data, filename)

            # Verify context manager was used (enter and exit called)
            mock_file().__enter__.assert_called_once()
            mock_file().__exit__.assert_called_once()

    def test_write_bytes_to_file_multiple_calls(self):
        """Test multiple calls to write_bytes_to_file."""
        data1 = b"\x20\x21"
        data2 = b"\x22\x23"
        filename = "multi_test.raw"

        mock_file = mock_open()
        with patch("langflow.utils.voice_utils.Path.open", mock_file):
            _write_bytes_to_file(data1, filename)
            _write_bytes_to_file(data2, filename)

            # Should have been called twice
            assert mock_file.call_count == 2
            # Both calls should use append mode
            assert all(call[0] == ("ab",) for call in mock_file.call_args_list)
