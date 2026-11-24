"""Exercise publication reservation and candidate protection without publishing anything."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SHA = "1" * 40


def run_guard(scenario: dict) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the Actions publication guard")
    script = """
      const {assertCandidateReplaceable, reserveFinalPublication} =
        require('./scripts/ci/release_auth/publication.cjs');
      const scenario = JSON.parse(process.argv[1]);
      const repo = {owner: 'review', repo: 'fixture'};
      const tag = 'v1.13.0';
      const sha = '1'.repeat(40);
      let drafts = scenario.drafts || [];
      const created = [];
      const github = {rest: {repos: {
        getReleaseByTag: async () => {
          if (scenario.status) throw {status: scenario.status};
          if (scenario.published) return {data: scenario.published};
          throw {status: 404};
        },
        listReleases: () => {},
        getCommit: async () => ({data: {sha: scenario.currentSha || sha}}),
        createRelease: async (request) => {
          created.push(request);
          drafts.push(request);
          return {data: request};
        },
      }}, paginate: async () => {
        if (scenario.listStatus) throw {status: scenario.listStatus};
        return drafts;
      }};
      (async () => {
        let error = null;
        try {
          if (scenario.action === 'replace') {
            await assertCandidateReplaceable(github, repo, tag);
          } else {
            await reserveFinalPublication(github, repo, tag, scenario.requestedSha || sha);
            if (scenario.action === 'retry') {
              await reserveFinalPublication(github, repo, tag, sha);
            }
            if (scenario.action === 'replace-after-reserve') {
              await assertCandidateReplaceable(github, repo, tag);
            }
          }
        } catch (failure) { error = failure.message || String(failure.status); }
        console.log(JSON.stringify({error, created}));
      })();
    """
    result = subprocess.run(  # noqa: S603
        [node, "-e", script, json.dumps(scenario)], cwd=REPO_ROOT, text=True, capture_output=True, check=True
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("action", ["reserve", "retry"])
def test_final_publication_creates_one_unpublished_reservation(action: str) -> None:
    result = run_guard({"action": action})
    assert result["error"] is None
    assert len(result["created"]) == 1
    release = result["created"][0]
    assert release["tag_name"] == "v1.13.0"
    assert release["draft"] is True
    assert release["prerelease"] is False
    assert SHA in release["body"]
    assert "target_commitish" not in release


def test_partial_publication_keeps_the_candidate_tag_reserved() -> None:
    result = run_guard({"action": "replace-after-reserve"})
    assert "Final publication is reserved or complete" in result["error"]
    assert len(result["created"]) == 1


@pytest.mark.parametrize(
    "scenario",
    [
        {"action": "replace", "published": {"prerelease": False}},
        {"action": "replace", "drafts": [{"tag_name": "v1.13.0", "prerelease": False, "draft": True}]},
        {"action": "replace", "status": 403},
        {"action": "replace", "status": 500},
        {"action": "replace", "listStatus": 403},
        {"action": "replace", "listStatus": 500},
        {"action": "reserve", "currentSha": "2" * 40},
        {"action": "reserve", "requestedSha": "development"},
        {"action": "reserve", "published": {"prerelease": True}},
        {"action": "reserve", "listStatus": 500},
    ],
)
def test_unsafe_or_unverifiable_publication_state_is_rejected(scenario: dict) -> None:
    result = run_guard(scenario)
    assert result["error"] is not None
    assert result["created"] == []


@pytest.mark.parametrize(
    "scenario",
    [
        {"action": "replace"},
        {"action": "replace", "published": {"prerelease": True}},
        {"action": "replace", "drafts": [{"tag_name": "v9.9.9", "prerelease": False, "draft": True}]},
        {"action": "reserve", "published": {"prerelease": False}},
        {"action": "reserve", "drafts": [{"tag_name": "v1.13.0", "prerelease": False, "draft": True}]},
    ],
)
def test_unpublished_candidates_and_same_source_retries_are_allowed(scenario: dict) -> None:
    result = run_guard(scenario)
    assert result["error"] is None
    assert result["created"] == []
