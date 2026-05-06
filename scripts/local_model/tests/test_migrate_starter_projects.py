"""Tests for the starter-project migration script.

The script rewrites every LanguageModelComponent node's `model.value` field to
point at "qwen2.5:1.5b" (the curated Langflow Model default) so that fresh
installs of Langflow run the starter projects without any third-party API key.

Idempotency is mandatory: running the script twice MUST be a no-op on the
already-migrated tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.local_model.migrate_starter_projects import (
    LANGFLOW_LOCAL_DEFAULT_MODEL,
    migrate_directory,
    rewrite_flow,
)


def _make_flow_with_language_model(model_value: str = "") -> dict:
    return {
        "data": {
            "nodes": [
                {
                    "data": {
                        "type": "LanguageModelComponent",
                        "node": {"template": {"model": {"name": "model", "value": model_value, "type": "model"}}},
                    }
                }
            ]
        }
    }


class TestRewriteFlow:
    def test_should_set_model_value_for_language_model_components(self):
        flow = _make_flow_with_language_model("")
        changed = rewrite_flow(flow)
        assert changed is True
        assert flow["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"] == LANGFLOW_LOCAL_DEFAULT_MODEL

    def test_should_be_idempotent(self):
        flow = _make_flow_with_language_model(LANGFLOW_LOCAL_DEFAULT_MODEL)
        changed = rewrite_flow(flow)
        # Already at target — no change needed.
        assert changed is False

    def test_should_skip_non_language_model_components(self):
        flow = {
            "data": {
                "nodes": [
                    {
                        "data": {
                            "type": "ChatInput",
                            "node": {"template": {"input_value": {"value": "hi"}}},
                        }
                    }
                ]
            }
        }
        changed = rewrite_flow(flow)
        assert changed is False

    def test_should_handle_flow_without_data_field(self):
        # Why: defensive against malformed JSON. The script must never crash on
        # one bad file; it should leave the file alone and continue.
        flow = {"unrelated": "fields"}
        changed = rewrite_flow(flow)
        assert changed is False


class TestMigrateDirectory:
    def test_should_rewrite_only_language_model_flows(self, tmp_path: Path):
        json_file = tmp_path / "Sample.json"
        json_file.write_text(json.dumps(_make_flow_with_language_model("")))

        unrelated = tmp_path / "Other.json"
        unrelated.write_text(json.dumps({"data": {"nodes": []}}))

        modified = migrate_directory(tmp_path)

        assert json_file in modified
        assert unrelated not in modified

        rewritten = json.loads(json_file.read_text())
        assert (
            rewritten["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"]
            == LANGFLOW_LOCAL_DEFAULT_MODEL
        )

    def test_should_be_idempotent_on_second_run(self, tmp_path: Path):
        json_file = tmp_path / "Sample.json"
        json_file.write_text(json.dumps(_make_flow_with_language_model("")))

        first = migrate_directory(tmp_path)
        second = migrate_directory(tmp_path)

        assert json_file in first
        assert second == []

    def test_should_skip_non_json_files(self, tmp_path: Path):
        (tmp_path / "README.md").write_text("not json")
        (tmp_path / "ignore.txt").write_text("also not json")

        modified = migrate_directory(tmp_path)
        assert modified == []
