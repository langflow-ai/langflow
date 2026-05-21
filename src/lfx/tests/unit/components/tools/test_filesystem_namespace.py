"""Unit tests for namespace derivation helpers used by FileSystemToolComponent."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestComputeUserNamespace:
    """Slice A1 — derive a stable, opaque per-user directory name."""

    def test_should_return_relative_users_path_when_user_id_is_provided(self) -> None:
        # Arrange
        from lfx.components.files_and_knowledge._filesystem_namespace import compute_user_namespace

        # Act
        namespace = compute_user_namespace("user-abc", pepper=b"pepper-bytes-32-len-aaaaaaaaaaaa")

        # Assert
        assert namespace.parts[0] == "users"
        assert len(namespace.parts) == 2
        assert not namespace.is_absolute()

    def test_should_be_deterministic_when_called_with_same_inputs(self) -> None:
        from lfx.components.files_and_knowledge._filesystem_namespace import compute_user_namespace

        pepper = b"pepper-bytes-32-len-aaaaaaaaaaaa"
        first = compute_user_namespace("user-abc", pepper=pepper)
        second = compute_user_namespace("user-abc", pepper=pepper)

        assert first == second

    def test_should_produce_different_hash_when_user_id_differs(self) -> None:
        from lfx.components.files_and_knowledge._filesystem_namespace import compute_user_namespace

        pepper = b"pepper-bytes-32-len-aaaaaaaaaaaa"
        a = compute_user_namespace("user-A", pepper=pepper)
        b = compute_user_namespace("user-B", pepper=pepper)

        assert a != b

    def test_should_produce_different_hash_when_pepper_differs(self) -> None:
        from lfx.components.files_and_knowledge._filesystem_namespace import compute_user_namespace

        a = compute_user_namespace("user-abc", pepper=b"pepper-AAAAAAAAAAAAAAAAAAAAAAAA")
        b = compute_user_namespace("user-abc", pepper=b"pepper-BBBBBBBBBBBBBBBBBBBBBBBB")

        assert a != b

    def test_should_return_empty_path_when_user_id_is_empty(self) -> None:
        from lfx.components.files_and_knowledge._filesystem_namespace import compute_user_namespace

        namespace = compute_user_namespace("", pepper=b"pepper-bytes-32-len-aaaaaaaaaaaa")

        assert namespace == Path()

    def test_should_produce_hash_segment_with_expected_length(self) -> None:
        from lfx.components.files_and_knowledge._filesystem_namespace import compute_user_namespace

        namespace = compute_user_namespace("user-abc", pepper=b"pepper-bytes-32-len-aaaaaaaaaaaa")

        hash_segment = namespace.parts[1]
        # 32 hex chars = 128 bits — collision-free in practice, opaque to listing.
        assert len(hash_segment) == 32
        assert all(c in "0123456789abcdef" for c in hash_segment)

    def test_should_reject_when_pepper_is_empty(self) -> None:
        from lfx.components.files_and_knowledge._filesystem_namespace import compute_user_namespace

        with pytest.raises(ValueError, match="pepper"):
            compute_user_namespace("user-abc", pepper=b"")


class TestLoadOrCreatePepper:
    """Slice A2 — pepper is auto-generated and persisted on first use."""

    def test_should_create_file_with_pepper_when_path_does_not_exist(self, tmp_path: Path) -> None:
        # Arrange
        from lfx.components.files_and_knowledge._filesystem_namespace import load_or_create_pepper

        pepper_path = tmp_path / ".fs_pepper"

        # Act
        pepper = load_or_create_pepper(pepper_path)

        # Assert
        assert pepper_path.exists()
        assert isinstance(pepper, bytes)
        assert len(pepper) >= 32

    def test_should_return_same_pepper_when_called_twice(self, tmp_path: Path) -> None:
        from lfx.components.files_and_knowledge._filesystem_namespace import load_or_create_pepper

        pepper_path = tmp_path / ".fs_pepper"

        first = load_or_create_pepper(pepper_path)
        second = load_or_create_pepper(pepper_path)

        assert first == second

    def test_should_create_parent_directories_when_missing(self, tmp_path: Path) -> None:
        from lfx.components.files_and_knowledge._filesystem_namespace import load_or_create_pepper

        pepper_path = tmp_path / "nested" / "deeper" / ".fs_pepper"

        pepper = load_or_create_pepper(pepper_path)

        assert pepper_path.exists()
        assert len(pepper) >= 32

    def test_should_set_restrictive_mode_when_creating_new_pepper(self, tmp_path: Path) -> None:
        # Why this test: the pepper is the secret that anonymizes user_id
        # values across the filesystem. It MUST NOT be world-readable on POSIX
        # systems — even when the operator forgets to set up correct umask.
        import sys

        if sys.platform == "win32":
            pytest.skip("POSIX-only file mode check; Windows ACLs tested separately.")

        from lfx.components.files_and_knowledge._filesystem_namespace import load_or_create_pepper

        pepper_path = tmp_path / ".fs_pepper"
        load_or_create_pepper(pepper_path)

        mode = pepper_path.stat().st_mode & 0o777
        # Only the owner may read/write the pepper.
        assert mode == 0o600, f"Expected mode 0o600, got {oct(mode)}"

    def test_should_reject_when_existing_pepper_is_too_short(self, tmp_path: Path) -> None:
        from lfx.components.files_and_knowledge._filesystem_namespace import load_or_create_pepper

        pepper_path = tmp_path / ".fs_pepper"
        pepper_path.write_bytes(b"short")  # Tampered/corrupted

        with pytest.raises(ValueError, match="pepper"):
            load_or_create_pepper(pepper_path)
