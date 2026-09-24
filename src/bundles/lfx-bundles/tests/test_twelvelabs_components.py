"""Unit tests for TwelveLabs components cloud validation."""

import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_bundles")

from lfx.schema import Data
from lfx.utils import file_path_security
from lfx.utils.file_path_security import LocalFileAccessError
from lfx_bundles.twelvelabs.pegasus_index import PegasusIndexVideo
from lfx_bundles.twelvelabs.split_video import SplitVideoComponent
from lfx_bundles.twelvelabs.twelvelabs_pegasus import TwelveLabsPegasus
from lfx_bundles.twelvelabs.video_embeddings import TwelveLabsVideoEmbeddingsComponent
from lfx_bundles.twelvelabs.video_file import VideoFileComponent


@pytest.mark.unit
class TestTwelveLabsCloudValidation:
    """Test TwelveLabs components cloud validation."""

    def test_video_file_process_disabled_in_astra_cloud(self):
        """Test that VideoFile process_files raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            component = VideoFileComponent(api_key="test-key", index_id="test-index")

            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.process_files([])

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg

    @pytest.mark.parametrize(
        "raw_path", [r"\\server\share\video.mp4", r"\/server/share/video.mp4", r"/\server/share/video.mp4"]
    )
    def test_video_file_rejects_unc_before_filesystem_access(self, monkeypatch, raw_path):
        monkeypatch.setattr(file_path_security, "is_local_file_access_restricted", lambda: False)
        component = VideoFileComponent(file_path=raw_path)
        video_file = component.BaseFile(data=[], path=Path(raw_path))

        def guard_network_path(method):
            def guarded(path, *args, **kwargs):
                if str(path).replace("\\", "/").startswith("//"):
                    msg = "filesystem access on a network path"
                    raise AssertionError(msg)
                return method(path, *args, **kwargs)

            return guarded

        with (
            patch.object(Path, "exists", guard_network_path(Path.exists)),
            patch.object(Path, "stat", guard_network_path(Path.stat)),
            patch.object(Path, "resolve", guard_network_path(Path.resolve)),
        ):
            with pytest.raises(LocalFileAccessError, match="UNC and device"):
                component.process_files([video_file])
            component.load_files()

    def test_split_video_process_disabled_in_astra_cloud(self):
        """Test that SplitVideo process raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            component = SplitVideoComponent(api_key="test-key", index_id="test-index")

            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.process()

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg


@pytest.mark.unit
class TestSplitVideoLocalPaths:
    def test_remote_url_is_rejected_before_ffprobe(self):
        component = SplitVideoComponent(videodata=[Data(data={"text": "http://127.0.0.1:9999/video.mp4"})])

        with patch("lfx_bundles.twelvelabs.split_video.subprocess.run") as run:
            with pytest.raises(ValueError, match="expected a local file"):
                component.process()

            with pytest.raises(ValueError, match="expected a local file"):
                component.get_video_duration("http://127.0.0.1:9999/video.mp4")

        run.assert_not_called()

    def test_option_named_file_is_passed_as_absolute_path_to_both_tools(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(file_path_security, "is_local_file_access_restricted", lambda: False)
        video = tmp_path / "-version"
        video.write_bytes(b"video")
        component = SplitVideoComponent(last_clip_handling="Keep Short")
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="5.0", stderr="")

        with patch("lfx_bundles.twelvelabs.split_video.subprocess.run", return_value=completed) as run:
            component.process_video("-version", 10, include_original=False)

        assert run.call_count == 2
        assert run.call_args_list[0].args[0][-1] == str(video.resolve())
        ffmpeg_command = run.call_args_list[1].args[0]
        assert ffmpeg_command[ffmpeg_command.index("-i") + 1] == str(video.resolve())
        for call in run.call_args_list:
            command = call.args[0]
            assert command[command.index("-format_whitelist") + 1] == (
                "mov,matroska,webm,avi,flv,asf,mpeg,mpegts,mpegtsraw,mpegvideo,mxf,dv,ogg,rm,rawvideo,yuv4mpegpipe"
            )
            assert command[command.index("-protocol_whitelist") + 1] == "file"

    def test_restricted_mode_blocks_other_users_video(self, tmp_path, monkeypatch):
        monkeypatch.setattr(file_path_security, "is_local_file_access_restricted", lambda: True)
        monkeypatch.setattr(
            file_path_security,
            "get_settings_service",
            lambda: SimpleNamespace(settings=SimpleNamespace(config_dir=tmp_path, database_url=None)),
        )
        other_users_video = tmp_path / "other-user" / "video.mp4"
        other_users_video.parent.mkdir()
        other_users_video.write_bytes(b"video")
        component = SplitVideoComponent(_user_id="current-user")

        with (
            patch("lfx_bundles.twelvelabs.split_video.subprocess.run") as run,
            pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"),
        ):
            component.get_video_duration(str(other_users_video))

        run.assert_not_called()

    @pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg tools unavailable")
    @pytest.mark.parametrize("playlist_kind", ["hls", "concat"])
    def test_playlist_cannot_read_other_users_segment(self, tmp_path, monkeypatch, playlist_kind):
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        assert ffmpeg
        assert ffprobe
        current_user = tmp_path / "current-user"
        other_user = tmp_path / "other-user"
        current_user.mkdir()
        other_user.mkdir()
        segment = other_user / "segment.ts"
        subprocess.run(  # noqa: S603 - fixed test binary and temporary fixture path
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=2:size=128x128:rate=25",
                "-c:v",
                "mpeg2video",
                "-f",
                "mpegts",
                str(segment),
            ],
            check=True,
            capture_output=True,
        )
        if playlist_kind == "hls":
            playlist = current_user / "video.m3u8"
            playlist.write_text(
                f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:2\n#EXTINF:1.0,\n{segment}\n#EXT-X-ENDLIST\n",
                encoding="utf-8",
            )
        else:
            (current_user / "inside.ts").symlink_to(segment)
            playlist = current_user / "video.mp4"  # FFmpeg sniffs concat despite the media suffix.
            playlist.write_text("ffconcat version 1.0\nfile inside.ts\nduration 1.0\n", encoding="utf-8")
        # Confirm this fixture is a working cross-scope read without a demuxer guard.
        bare_probe = subprocess.run(  # noqa: S603 - fixed test binary and temporary fixture path
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(playlist)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert bare_probe.returncode == 0, bare_probe.stderr
        assert float(bare_probe.stdout.strip()) > 0

        monkeypatch.setattr(file_path_security, "is_local_file_access_restricted", lambda: True)
        monkeypatch.setattr(
            file_path_security,
            "get_settings_service",
            lambda: SimpleNamespace(settings=SimpleNamespace(config_dir=tmp_path, database_url=None)),
        )
        component = SplitVideoComponent(_user_id="current-user")
        own_video = current_user / "own-video.ts"
        shutil.copyfile(segment, own_video)
        assert component.get_video_duration(str(own_video)) > 0

        with pytest.raises(RuntimeError, match="not on whitelist"):
            component.get_video_duration(str(playlist))


@pytest.fixture
def other_users_video(tmp_path, monkeypatch):
    monkeypatch.setattr(file_path_security, "is_local_file_access_restricted", lambda: True)
    monkeypatch.setattr(
        file_path_security,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(config_dir=tmp_path, database_url=None)),
    )
    video = tmp_path / "other-user" / "video.mp4"
    video.parent.mkdir()
    video.write_bytes(b"other user's video")
    return video


@pytest.mark.unit
class TestTwelveLabsUploadScopes:
    def test_video_file_accepts_current_users_video(self, other_users_video):
        own_video = other_users_video.parent.parent / "current-user" / "video.mp4"
        own_video.parent.mkdir()
        own_video.write_bytes(b"current user's video")
        component = VideoFileComponent(_user_id="current-user", file_path=str(own_video))
        video_file = component.BaseFile(data=[], path=own_video)

        processed = component.process_files([video_file])

        assert processed == [video_file]
        assert processed[0].data[0].data["text"] == str(own_video)

    def test_pegasus_does_not_upload_other_users_video(self, other_users_video):
        component = TwelveLabsPegasus(
            _user_id="current-user",
            videodata=[Data(data={"text": str(other_users_video)})],
            api_key="test-key",
        )

        with patch("lfx_bundles.twelvelabs.twelvelabs_pegasus.TwelveLabs") as client:
            response = component.process_video()

        assert "outside the authenticated user's storage scope" in response.text
        client.assert_not_called()

    def test_pegasus_uploads_current_users_video(self, other_users_video):
        own_video = other_users_video.parent.parent / "current-user" / "video.mp4"
        own_video.parent.mkdir()
        own_video.write_bytes(b"current user's video")
        component = TwelveLabsPegasus(
            _user_id="current-user",
            videodata=[Data(data={"text": str(own_video)})],
            api_key="test-key",
        )

        with (
            patch("lfx_bundles.twelvelabs.twelvelabs_pegasus.TwelveLabs") as client,
            patch.object(component, "_get_or_create_index", return_value=("test-index", "test-index")),
        ):
            client.return_value.task.create.return_value = SimpleNamespace(
                id="task-id", status="ready", video_id="video-id", wait_for_done=lambda **_kwargs: None
            )
            response = component.process_video()

        assert "Video processed successfully" in response.text
        assert client.return_value.task.create.call_args.kwargs["file"].name == str(own_video)

    def test_pegasus_index_does_not_upload_other_users_video(self, other_users_video):
        component = PegasusIndexVideo(
            _user_id="current-user",
            videodata=[Data(data={"text": str(other_users_video)})],
            api_key="test-key",
            index_id="test-index",
        )

        with (
            patch("lfx_bundles.twelvelabs.pegasus_index.TwelveLabs") as client,
            patch.object(component, "_get_or_create_index", return_value=("test-index", "test-index")),
        ):
            assert component.index_videos() == []

        client.return_value.task.create.assert_not_called()

    def test_pegasus_index_upload_helper_guards_other_users_video(self, other_users_video):
        component = PegasusIndexVideo(_user_id="current-user")
        client = MagicMock()

        with pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"):
            component._upload_video(client, str(other_users_video), "test-index")

        client.task.create.assert_not_called()

    def test_pegasus_index_upload_helper_accepts_current_users_video(self, other_users_video):
        own_video = other_users_video.parent.parent / "current-user" / "video.mp4"
        own_video.parent.mkdir()
        own_video.write_bytes(b"current user's video")
        component = PegasusIndexVideo(_user_id="current-user")
        client = MagicMock()
        client.task.create.return_value.id = "task-id"

        assert component._upload_video(client, str(own_video), "test-index") == "task-id"
        assert client.task.create.call_args.kwargs["file"].name == str(own_video)

    def test_video_embeddings_do_not_upload_other_users_video(self, other_users_video):
        component = TwelveLabsVideoEmbeddingsComponent(_user_id="current-user", api_key="test-key")

        with patch("lfx_bundles.twelvelabs.video_embeddings.TwelveLabs") as client:
            embeddings = component.build_embeddings()
            with pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"):
                embeddings.embed_video(str(other_users_video))

        client.return_value.embed.task.create.assert_not_called()

    def test_video_embeddings_upload_current_users_video(self, other_users_video):
        own_video = other_users_video.parent.parent / "current-user" / "video.mp4"
        own_video.parent.mkdir()
        own_video.write_bytes(b"current user's video")
        component = TwelveLabsVideoEmbeddingsComponent(_user_id="current-user", api_key="test-key")

        with patch("lfx_bundles.twelvelabs.video_embeddings.TwelveLabs") as client:
            embeddings = component.build_embeddings()
            client.return_value.embed.task.create.return_value.id = "task-id"
            with patch.object(
                embeddings,
                "_wait_for_task_completion",
                return_value=SimpleNamespace(video_embedding=SimpleNamespace(segments=[])),
            ):
                embeddings.embed_video(str(own_video))

        assert client.return_value.embed.task.create.call_args.kwargs["video_file"].name == str(own_video)
