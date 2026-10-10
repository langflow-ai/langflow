"""Publication cannot silently use an absent or unprotected GitHub environment."""

import importlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def preflight(monkeypatch):
    root = Path(__file__).resolve().parents[6]
    monkeypatch.syspath_prepend(str(root / "tools" / "chroma_migration_helper"))
    return importlib.import_module("check_release_environment")


@pytest.mark.parametrize("kind", ["User", "Team"])
def test_requires_real_reviewers_from_github_schema(preflight, kind):
    preflight.require_reviewers(
        {
            "name": preflight.ENVIRONMENT,
            "can_admins_bypass": False,
            "protection_rules": [
                {"type": "wait_timer", "wait_timer": 5},
                {
                    "type": "required_reviewers",
                    "prevent_self_review": True,
                    "reviewers": [{"type": kind, "reviewer": {"id": 700235, "type": "User"}}],
                },
            ],
        }
    )


@pytest.mark.parametrize(
    "rules",
    [
        None,
        [],
        [{"type": "wait_timer", "wait_timer": 5}],
        [{"type": "required_reviewers"}],
        [{"type": "required_reviewers", "prevent_self_review": True, "reviewers": []}],
        [{"type": "required_reviewers", "prevent_self_review": True, "reviewers": [{"type": "User", "reviewer": {}}]}],
        [
            {
                "type": "required_reviewers",
                "prevent_self_review": True,
                "reviewers": [{"type": "User", "reviewer": {"id": True}}],
            }
        ],
        [
            {
                "type": "required_reviewers",
                "prevent_self_review": True,
                "reviewers": [{"type": "Bot", "reviewer": {"id": 1}}],
            }
        ],
        [
            {
                "type": "required_reviewers",
                "prevent_self_review": True,
                "reviewers": [{"type": "User", "reviewer": {"id": 1, "type": "Bot"}}],
            }
        ],
    ],
)
def test_missing_or_malformed_protection_fails_closed(preflight, rules):
    with pytest.raises(ValueError, match="publication is blocked"):
        preflight.require_reviewers(
            {"name": preflight.ENVIRONMENT, "can_admins_bypass": False, "protection_rules": rules}
        )


@pytest.mark.parametrize("response", [None, [], {"message": "Not Found"}, {"name": "unrelated-environment"}])
def test_unexpected_api_payload_fails_closed(preflight, response):
    with pytest.raises(ValueError, match="publication is blocked"):
        preflight.require_reviewers(response)


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_inaccessible_api_has_clear_setup_error_and_never_mutates(preflight, monkeypatch, status):
    calls = []

    def inaccessible(command, **kwargs):
        calls.append(command)
        assert command[command.index("--method") + 1] == "GET"
        assert command[-1] == preflight.ENDPOINT
        assert kwargs["timeout"] == 30
        raise subprocess.CalledProcessError(status, command)

    monkeypatch.setattr(preflight.subprocess, "run", inaccessible)
    with pytest.raises(ValueError, match="actions: read"):
        preflight.check_environment()
    assert len(calls) == 1


def test_read_only_preflight_accepts_protected_environment(preflight, monkeypatch):
    payload = {
        "name": preflight.ENVIRONMENT,
        "can_admins_bypass": False,
        "protection_rules": [
            {
                "type": "required_reviewers",
                "prevent_self_review": True,
                "reviewers": [{"type": "User", "reviewer": {"id": 700235, "type": "User"}}],
            }
        ],
    }
    monkeypatch.setattr(
        preflight.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout=json.dumps(payload))
    )
    preflight.check_environment()


@pytest.mark.parametrize("admin_bypass", [True, None])
def test_admin_bypass_is_rejected(preflight, admin_bypass):
    with pytest.raises(ValueError, match="publication is blocked"):
        preflight.require_reviewers(
            {
                "name": preflight.ENVIRONMENT,
                "can_admins_bypass": admin_bypass,
                "protection_rules": [
                    {
                        "type": "required_reviewers",
                        "prevent_self_review": True,
                        "reviewers": [{"type": "User", "reviewer": {"id": 1}}],
                    }
                ],
            }
        )


@pytest.mark.parametrize("self_review", [False, None])
def test_self_approval_is_rejected(preflight, self_review):
    with pytest.raises(ValueError, match="publication is blocked"):
        preflight.require_reviewers(
            {
                "name": preflight.ENVIRONMENT,
                "can_admins_bypass": False,
                "protection_rules": [
                    {
                        "type": "required_reviewers",
                        "prevent_self_review": self_review,
                        "reviewers": [{"type": "User", "reviewer": {"id": 1}}],
                    }
                ],
            }
        )
