"""Regression for the unenforced credential deny-list (dead code).

``filesystem.py`` defines ``_DENY_BASENAME_LITERALS`` / ``_PREFIXES`` /
``_SUFFIXES`` / ``_DENY_PATH_FRAGMENTS`` documented as the
"default-deny inside an allowed root" control, but no code referenced
them: any ``.env`` / private key / ``.ssh`` file inside the sandbox was
fully readable, writable, editable, glob-able and grep-able.

The deny check must be pure-string and run before any I/O, so the agent
cannot distinguish a denied-existing file from a denied-absent one.
"""

import json
from pathlib import Path

import pytest
from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

SENTINEL_VALUE = "sk-fake-secret-12345"


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    shared = tmp_path / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / ".env").write_text(f"API_KEY={SENTINEL_VALUE}\n", encoding="utf-8")
    (shared / "id_rsa").write_text(f"FAKE PRIVATE KEY {SENTINEL_VALUE}\n", encoding="utf-8")
    (shared / "secret.pem").write_text(f"-----BEGIN FAKE KEY----- {SENTINEL_VALUE}\n", encoding="utf-8")
    ssh_dir = shared / ".ssh"
    ssh_dir.mkdir()
    (ssh_dir / "config").write_text(f"Host fakehost {SENTINEL_VALUE}\n", encoding="utf-8")
    (shared / "notes.txt").write_text("plain allowed file\n", encoding="utf-8")
    return shared


@pytest.fixture
def component(sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> FileSystemToolComponent:  # noqa: ARG001
    c = FileSystemToolComponent(root_path="", read_only=False)
    monkeypatch.setattr(c, "_resolve_auto_login", lambda: True)
    return c


DENIED_PATHS = [
    pytest.param(".env", id="literal-dotenv"),
    pytest.param("id_rsa", id="prefix-id_rsa"),
    pytest.param("id_rsa.pub", id="prefix-id_rsa-pub"),
    pytest.param("secret.pem", id="suffix-pem"),
    pytest.param(".ssh/config", id="fragment-ssh"),
    pytest.param(".ENV", id="literal-case-insensitive"),
    pytest.param("ID_RSA", id="prefix-case-insensitive"),
    pytest.param("SECRET.PEM", id="suffix-case-insensitive"),
    pytest.param(".SSH/config", id="fragment-case-insensitive"),
    pytest.param("nested/.aws/credentials", id="fragment-nested-aws"),
]


class TestDenyListRead:
    @pytest.mark.parametrize("path", DENIED_PATHS)
    def test_should_deny_read_when_path_matches_credential_pattern(
        self, component: FileSystemToolComponent, path: str
    ) -> None:
        result = component._read_file(path)

        assert "error" in result, f"deny-list did not fire for {path!r}; result={result!r}"
        assert SENTINEL_VALUE not in json.dumps(result)

    def test_should_deny_before_io_when_denied_file_does_not_exist(self, component: FileSystemToolComponent) -> None:
        result = component._read_file(".netrc")

        assert "error" in result
        assert "not found" not in result["error"].lower(), (
            "deny must fire before existence is observed, error was: " + result["error"]
        )

    def test_should_still_read_allowed_file(self, component: FileSystemToolComponent) -> None:
        result = component._read_file("notes.txt")

        assert result.get("status") == "ok", f"allowed file was blocked: {result!r}"

    def test_should_not_deny_when_literal_is_only_a_name_prefix(self, component: FileSystemToolComponent) -> None:
        result = component._read_file(".env.local")

        assert "error" in result
        assert "denied" not in result["error"].lower(), ".env.local must not match the exact-literal rule"


class TestDenyListWrite:
    def test_should_deny_write_when_basename_matches_literal(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        result = component._write_file(".pgpass", "db:5432:*:user:hunter2")

        assert "error" in result
        assert not (sandbox / ".pgpass").exists()

    def test_should_deny_write_when_directory_matches_fragment(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        result = component._write_file(".kube/config", "apiVersion: v1")

        assert "error" in result
        assert not (sandbox / ".kube").exists()


class TestDenyListEdit:
    def test_should_deny_edit_when_path_matches_credential_pattern(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        result = component._edit_file(".env", old_string=SENTINEL_VALUE, new_string="changed")

        assert "error" in result
        assert SENTINEL_VALUE in (sandbox / ".env").read_text(encoding="utf-8")


class TestDenyListSymlinkAlias:
    """A symlink whose own name is innocuous must not alias a denied target.

    The deny check runs on the input string; ``.resolve()`` follows the link
    afterwards, so without a post-resolution check an ``alias -> .env`` symlink
    (which a shared-root workspace can acquire out-of-band) reads ``.env``.
    """

    def test_should_deny_read_when_symlink_aliases_a_denied_file(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        alias = sandbox / "alias"
        alias.symlink_to(sandbox / ".env")

        result = component._read_file("alias")

        assert "error" in result, f"symlink alias bypassed the deny-list; result={result!r}"
        assert SENTINEL_VALUE not in json.dumps(result)

    def test_should_still_read_allowed_symlink_target(self, component: FileSystemToolComponent, sandbox: Path) -> None:
        alias = sandbox / "notes_link"
        alias.symlink_to(sandbox / "notes.txt")

        result = component._read_file("notes_link")

        assert result.get("status") == "ok", f"allowed symlink target was blocked: {result!r}"


class TestDenyListGlob:
    def test_should_omit_denied_files_when_globbing_workspace(self, component: FileSystemToolComponent) -> None:
        result = component._glob_search("**/*")

        assert result.get("status") == "ok"
        denied_hits = [m for m in result["matches"] if Path(m).name in {".env", "id_rsa", "secret.pem", "config"}]
        assert denied_hits == [], f"glob leaked denied files: {denied_hits}"
        assert "notes.txt" in result["matches"]


class TestDenyListGrep:
    def test_should_not_leak_denied_content_when_grepping_parent_directory(
        self, component: FileSystemToolComponent
    ) -> None:
        result = component._grep_search(SENTINEL_VALUE, output_mode="content")

        assert result.get("status") == "ok"
        assert result["matches"] == [], f"grep leaked denied file content: {result['matches']!r}"

    def test_should_not_list_denied_files_when_grepping_parent_directory(
        self, component: FileSystemToolComponent
    ) -> None:
        result = component._grep_search(SENTINEL_VALUE, output_mode="files_with_matches")

        assert result.get("status") == "ok"
        assert result["matches"] == []

    def test_should_still_grep_allowed_files(self, component: FileSystemToolComponent) -> None:
        result = component._grep_search("plain allowed", output_mode="files_with_matches")

        assert result.get("status") == "ok"
        assert result["matches"] == ["notes.txt"]
