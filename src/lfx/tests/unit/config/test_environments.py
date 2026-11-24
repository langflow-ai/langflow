"""Unit tests for lfx.config.environments — environment resolution.

All tests run entirely in-process; no real Langflow instance or SDK required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from lfx.config.environments import (
    ConfigError,
    LangflowEnvironment,
    _find_config_file,
    _load_config,
    _parse_env_block,
    _parse_toml,
    _parse_yaml,
    resolve_environment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_YAML = """\
environments:
  local:
    url: http://localhost:7860
    api_key_env: MY_LOCAL_KEY

  staging:
    url: https://staging.example.com
    api_key_env: MY_STAGING_KEY

defaults:
  environment: local
"""

_MINIMAL_TOML = """\
[environments.local]
url = "http://localhost:7860"
api_key_env = "MY_LOCAL_KEY"  # pragma: allowlist secret

[environments.staging]
url = "https://staging.example.com"
api_key_env = "MY_STAGING_KEY"  # pragma: allowlist secret

[defaults]
environment = "local"
"""

_NO_DEFAULT_YAML = """\
environments:
  staging:
    url: https://staging.example.com
    api_key_env: MY_STAGING_KEY
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# LangflowEnvironment
# ---------------------------------------------------------------------------


class TestLangflowEnvironment:
    def test_fields_stored(self):
        e = LangflowEnvironment(name="staging", url="https://x.com", api_key="key123")  # pragma: allowlist secret
        assert e.name == "staging"
        assert e.url == "https://x.com"
        assert e.api_key == "key123"  # pragma: allowlist secret

    def test_api_key_may_be_none(self):
        e = LangflowEnvironment(name="local", url="http://localhost:7860", api_key=None)
        assert e.api_key is None


# ---------------------------------------------------------------------------
# _parse_yaml
# ---------------------------------------------------------------------------


class TestParseYaml:
    def test_parses_valid_yaml(self, tmp_path):
        path = _write(tmp_path, "e.yaml", _MINIMAL_YAML)
        result = _parse_yaml(_MINIMAL_YAML, path)
        assert "environments" in result
        assert "local" in result["environments"]

    def test_raises_on_invalid_yaml(self, tmp_path):
        path = _write(tmp_path, "e.yaml", ":\n  - invalid: [")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            _parse_yaml(":\n  - invalid: [", path)

    def test_raises_when_top_level_not_mapping(self, tmp_path):
        path = _write(tmp_path, "e.yaml", "- item1\n- item2\n")
        with pytest.raises(ConfigError, match="mapping"):
            _parse_yaml("- item1\n- item2\n", path)

    def test_returns_dict(self, tmp_path):
        path = _write(tmp_path, "e.yaml", "key: value\n")
        result = _parse_yaml("key: value\n", path)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# _parse_toml
# ---------------------------------------------------------------------------


class TestParseToml:
    def test_parses_valid_toml(self, tmp_path):
        path = _write(tmp_path, "e.toml", _MINIMAL_TOML)
        result = _parse_toml(path)
        assert "environments" in result
        assert "local" in result["environments"]

    def test_raises_on_invalid_toml(self, tmp_path):
        path = _write(tmp_path, "e.toml", "not = valid = toml\n")
        with pytest.raises(ConfigError):
            _parse_toml(path)

    def test_raises_on_missing_file(self, tmp_path):
        path = tmp_path / "missing.toml"
        with pytest.raises(ConfigError, match="Cannot read"):
            _parse_toml(path)


# ---------------------------------------------------------------------------
# _parse_env_block
# ---------------------------------------------------------------------------


class TestParseEnvBlock:
    def test_minimal_block_with_url(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_KEY", "secret123")  # pragma: allowlist secret
        block = {"url": "http://localhost:7860", "api_key_env": "MY_KEY"}  # pragma: allowlist secret
        path = tmp_path / "e.yaml"
        result = _parse_env_block("local", block, path)
        assert result.url == "http://localhost:7860"
        assert result.api_key == "secret123"  # pragma: allowlist secret
        assert result.name == "local"

    def test_missing_url_raises(self, tmp_path):
        path = tmp_path / "e.yaml"
        with pytest.raises(ConfigError, match=r"missing.*'url'"):
            _parse_env_block("local", {"api_key_env": "FOO"}, path)  # pragma: allowlist secret

    def test_not_a_dict_raises(self, tmp_path):
        path = tmp_path / "e.yaml"
        with pytest.raises(ConfigError, match="mapping"):
            _parse_env_block("local", "not a dict", path)

    def test_missing_env_var_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MISSING_KEY", raising=False)
        path = tmp_path / "e.yaml"
        result = _parse_env_block("local", {"url": "http://x", "api_key_env": "MISSING_KEY"}, path)
        assert result.api_key is None

    def test_literal_api_key_in_block(self, tmp_path):
        path = tmp_path / "e.yaml"
        block = {"url": "http://x", "api_key": "direct-key"}  # pragma: allowlist secret
        result = _parse_env_block("local", block, path)
        assert result.api_key == "direct-key"  # pragma: allowlist secret

    def test_no_key_field_api_key_is_none(self, tmp_path):
        path = tmp_path / "e.yaml"
        result = _parse_env_block("local", {"url": "http://x"}, path)
        assert result.api_key is None


# ---------------------------------------------------------------------------
# _find_config_file
# ---------------------------------------------------------------------------


class TestFindConfigFile:
    def test_override_file_returned_when_it_exists(self, tmp_path):
        p = _write(tmp_path, "my.yaml", _MINIMAL_YAML)
        assert _find_config_file(p) == p

    def test_override_missing_raises(self, tmp_path):
        missing = tmp_path / "missing.yaml"
        with pytest.raises(ConfigError, match="not found"):
            _find_config_file(missing)

    def test_finds_lfx_yaml_in_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        p = _write(tmp_path, ".lfx/environments.yaml", _MINIMAL_YAML)
        assert _find_config_file(None) == p

    def test_finds_lfx_yml_in_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        p = _write(tmp_path, ".lfx/environments.yml", _MINIMAL_YAML)
        assert _find_config_file(None) == p

    def test_walks_up_to_parent(self, tmp_path, monkeypatch):
        parent_yaml = _write(tmp_path, ".lfx/environments.yaml", _MINIMAL_YAML)
        child = tmp_path / "subdir"
        child.mkdir()
        monkeypatch.chdir(child)
        # No .git boundary, so should walk up to tmp_path
        result = _find_config_file(None)
        assert result == parent_yaml

    def test_stops_at_git_boundary(self, tmp_path, monkeypatch):
        # Create .git in cwd so the walk stops there
        cwd = tmp_path / "project"
        cwd.mkdir()
        (cwd / ".git").mkdir()
        # Parent has a YAML config — should NOT be found (stopped by .git boundary)
        _write(tmp_path, ".lfx/environments.yaml", _MINIMAL_YAML)
        monkeypatch.chdir(cwd)
        # Also check no TOML fallback
        result = _find_config_file(None)
        assert result is None

    def test_toml_fallback_when_no_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        p = _write(tmp_path, "langflow-environments.toml", _MINIMAL_TOML)
        assert _find_config_file(None) == p

    def test_returns_none_when_nothing_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Create a git boundary so it doesn't walk up further
        (tmp_path / ".git").mkdir()
        assert _find_config_file(None) is None


# ---------------------------------------------------------------------------
# _load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_loads_yaml_environments(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_LOCAL_KEY", "local-key")  # pragma: allowlist secret
        monkeypatch.setenv("MY_STAGING_KEY", "staging-key")  # pragma: allowlist secret
        p = _write(tmp_path, "e.yaml", _MINIMAL_YAML)
        envs, default = _load_config(p)
        assert "local" in envs
        assert "staging" in envs
        assert default == "local"
        assert envs["local"].url == "http://localhost:7860"
        assert envs["local"].api_key == "local-key"  # pragma: allowlist secret

    def test_loads_toml_environments(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_LOCAL_KEY", "local-key")  # pragma: allowlist secret
        p = _write(tmp_path, "e.toml", _MINIMAL_TOML)
        envs, default = _load_config(p)
        assert "local" in envs
        assert default == "local"

    def test_no_defaults_returns_none(self, tmp_path):
        p = _write(tmp_path, "e.yaml", _NO_DEFAULT_YAML)
        _, default = _load_config(p)
        assert default is None

    def test_missing_env_var_does_not_raise_in_load(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MY_LOCAL_KEY", raising=False)
        p = _write(tmp_path, "e.yaml", _MINIMAL_YAML)
        # _load_config does NOT raise for missing env vars — just returns None for api_key
        envs, _ = _load_config(p)
        assert envs["local"].api_key is None

    def test_malformed_environments_key_raises(self, tmp_path):
        bad_yaml = "environments: not_a_mapping_but_a_string\n"
        p = _write(tmp_path, "e.yaml", bad_yaml)
        with pytest.raises(ConfigError, match="mapping"):
            _load_config(p)


# ---------------------------------------------------------------------------
# resolve_environment — inline mode
# ---------------------------------------------------------------------------


class TestResolveInlineMode:
    def test_target_returns_inline_env(self):
        result = resolve_environment(None, target="http://localhost:7860")
        assert result.url == "http://localhost:7860"
        assert result.name == "__inline__"
        assert result.api_key is None

    def test_target_with_api_key(self):
        result = resolve_environment(None, target="http://localhost:7860", api_key="mykey")  # pragma: allowlist secret
        assert result.api_key == "mykey"  # pragma: allowlist secret

    def test_target_with_env_name_uses_env_name_as_label(self):
        result = resolve_environment("staging", target="http://localhost:7860", api_key="k")  # pragma: allowlist secret
        assert result.name == "staging"
        assert result.url == "http://localhost:7860"

    def test_target_ignores_environments_file(self, tmp_path):
        # Even if environments_file is given, --target bypasses it entirely
        result = resolve_environment(
            None,
            target="http://localhost:7860",
            environments_file=str(tmp_path / "missing.yaml"),
        )
        assert result.url == "http://localhost:7860"


# ---------------------------------------------------------------------------
# resolve_environment — config file mode
# ---------------------------------------------------------------------------


class TestResolveConfigMode:
    def test_named_env_resolved(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("MY_STAGING_KEY", "staging-secret")  # pragma: allowlist secret
        _write(tmp_path, ".lfx/environments.yaml", _MINIMAL_YAML)
        result = resolve_environment("staging")
        assert result.url == "https://staging.example.com"
        assert result.api_key == "staging-secret"  # pragma: allowlist secret
        assert result.name == "staging"

    def test_default_env_used_when_no_env_given(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("MY_LOCAL_KEY", "local-secret")  # pragma: allowlist secret
        _write(tmp_path, ".lfx/environments.yaml", _MINIMAL_YAML)
        result = resolve_environment(None)
        assert result.url == "http://localhost:7860"
        assert result.api_key == "local-secret"  # pragma: allowlist secret

    def test_explicit_environments_file_used(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_LOCAL_KEY", "local-key")  # pragma: allowlist secret
        p = _write(tmp_path, "custom/env.yaml", _MINIMAL_YAML)
        result = resolve_environment("local", environments_file=str(p))
        assert result.url == "http://localhost:7860"

    def test_api_key_override_applied(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("MY_LOCAL_KEY", "config-key")  # pragma: allowlist secret
        _write(tmp_path, ".lfx/environments.yaml", _MINIMAL_YAML)
        result = resolve_environment("local", api_key="override-key")  # pragma: allowlist secret
        assert result.api_key == "override-key"  # pragma: allowlist secret

    def test_missing_env_var_returns_none_api_key(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("MY_LOCAL_KEY", raising=False)
        _write(tmp_path, ".lfx/environments.yaml", _MINIMAL_YAML)
        result = resolve_environment("local")
        # Missing env var yields None — caller decides whether to treat this as error
        assert result.api_key is None

    def test_unknown_env_name_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path, ".lfx/environments.yaml", _MINIMAL_YAML)
        with pytest.raises(ConfigError, match=r"'production'.*not found"):
            resolve_environment("production")

    def test_no_default_and_no_env_name_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path, ".lfx/environments.yaml", _NO_DEFAULT_YAML)
        with pytest.raises(ConfigError, match="No --env given"):
            resolve_environment(None)

    def test_toml_file_also_works(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("MY_LOCAL_KEY", "local-secret")  # pragma: allowlist secret
        _write(tmp_path, "langflow-environments.toml", _MINIMAL_TOML)
        result = resolve_environment("local")
        assert result.url == "http://localhost:7860"
        assert result.api_key == "local-secret"  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# resolve_environment — no config file fallbacks
# ---------------------------------------------------------------------------


class TestResolveNoConfigFallbacks:
    def test_langflow_url_env_var_used_as_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()  # stop file walk here
        monkeypatch.setenv("LANGFLOW_URL", "http://fallback:7860")
        monkeypatch.setenv("LANGFLOW_API_KEY", "fallback-key")  # pragma: allowlist secret
        result = resolve_environment(None)
        assert result.url == "http://fallback:7860"
        assert result.api_key == "fallback-key"  # pragma: allowlist secret
        assert result.name == "__env__"

    def test_lfx_url_env_var_used_as_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        monkeypatch.delenv("LANGFLOW_URL", raising=False)
        monkeypatch.setenv("LFX_URL", "http://lfx-fallback:7860")
        monkeypatch.setenv("LFX_API_KEY", "lfx-key")  # pragma: allowlist secret
        result = resolve_environment(None)
        assert result.url == "http://lfx-fallback:7860"
        assert result.api_key == "lfx-key"  # pragma: allowlist secret

    def test_named_env_without_config_raises_clear_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        monkeypatch.delenv("LANGFLOW_URL", raising=False)
        monkeypatch.delenv("LFX_URL", raising=False)
        with pytest.raises(ConfigError, match=r"'staging'.*no config file"):
            resolve_environment("staging")

    def test_no_env_no_config_no_env_vars_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        monkeypatch.delenv("LANGFLOW_URL", raising=False)
        monkeypatch.delenv("LFX_URL", raising=False)
        with pytest.raises(ConfigError, match="No --env"):
            resolve_environment(None)

    def test_missing_explicit_environments_file_raises(self, tmp_path):
        missing = tmp_path / "missing.yaml"
        with pytest.raises(ConfigError, match="not found"):
            resolve_environment("staging", environments_file=str(missing))

    def test_inline_api_key_override_with_env_var_url(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        monkeypatch.setenv("LANGFLOW_URL", "http://fallback:7860")
        monkeypatch.delenv("LANGFLOW_API_KEY", raising=False)
        # api_key arg should override the env-var based key
        result = resolve_environment(None, api_key="override-key")  # pragma: allowlist secret
        # In fallback mode, api_key_inline takes precedence
        assert result.api_key == "override-key"  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Error message quality
# ---------------------------------------------------------------------------


class TestErrorMessages:
    def test_unknown_env_message_lists_available(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path, ".lfx/environments.yaml", _MINIMAL_YAML)
        with pytest.raises(ConfigError, match="local") as exc_info:
            resolve_environment("typo-env")
        assert "staging" in str(exc_info.value)

    def test_no_config_message_suggests_init(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        monkeypatch.delenv("LANGFLOW_URL", raising=False)
        monkeypatch.delenv("LFX_URL", raising=False)
        with pytest.raises(ConfigError, match="lfx init"):
            resolve_environment("staging")

    def test_no_default_message_shows_available(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path, ".lfx/environments.yaml", _NO_DEFAULT_YAML)
        with pytest.raises(ConfigError, match="staging"):
            resolve_environment(None)
