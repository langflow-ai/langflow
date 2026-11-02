"""Installed metadata must work in a fresh standalone listener process."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import textwrap

import pytest

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("valid_catalog", [True, False])
async def test_fresh_listener_boot_loads_only_validated_installed_trigger_owners(tmp_path, valid_catalog):
    package = tmp_path / "listener_pilot"
    components = package / "components"
    components.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (components / "source.py").write_text(
        "from lfx.custom.custom_component.component import Component\n"
        "class PilotOnItemTriggerComponent(Component):\n"
        "    display_name = 'Pilot On Item'\n"
    )
    (package / "extension.json").write_text(
        json.dumps(
            {
                "id": "lfx-listener-pilot",
                "version": "0.1.0",
                "name": "Pilot",
                "lfx": {"compat": ["1"]},
                "bundles": [{"name": "pilot", "path": "components"}],
                "integrations": [{"provider_id": "pilot", "bundle": "pilot", "path": "capabilities.v1.json"}],
            }
        )
    )
    (components / "capabilities.v1.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "provider_id": "pilot" if valid_catalog else "wrong",
                "display_name": "Pilot",
                "auth_profiles": [
                    {
                        "id": "pilot-token",
                        "kind": "api_key",
                        "identity": "service",
                        "client_type_by_context": {"self_managed": "external"},
                    }
                ],
                "capabilities": [
                    {
                        "id": "pilot.trigger.item",
                        "display_name": "Pilot On Item",
                        "auth_profile_id": "pilot-token",
                        "identity": "service",
                        "policy_keys": ["integrations.pilot.trigger.item"],
                        "substrate": "rest",
                        "maturity": "preview",
                        "deployment_contexts": ["self_managed"],
                        "risk": "read",
                        "component_ref": "PilotOnItemTriggerComponent",
                    }
                ],
            }
        )
    )
    (package / "runtime.py").write_text(
        textwrap.dedent(
            """\
            from langflow.services.connection.oauth.adapter import OAuthAdapter
            from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider

            async def collect(trigger, lease):
                raise AssertionError('Startup must not poll')

            async def parse(registration, body, *, refresh):
                return body, None

            PROVIDER = TriggerProvider(
                provider_id='pilot', bundle='pilot', normalize_config=lambda kind, raw: raw,
                kinds=(TriggerKind(kind='pilot.item', component='PilotOnItemTriggerComponent',
                    display_name='Pilot On Item', config_fields=('connection',), identity='service',
                    poll_mechanism='pilot.poll'),),
                collect=collect,
                oauth=OAuthAdapter(
                    endpoints=lambda registration: ('https://pilot.example/authorize', 'https://pilot.example/token'),
                    allowed_origins=('https://pilot.example',), validate_registration=lambda registration: None,
                    parse_token=parse),
            )
            """
        )
    )
    dist = tmp_path / "lfx_listener_pilot-0.1.0.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text("Metadata-Version: 2.1\nName: lfx-listener-pilot\nVersion: 0.1.0\n")
    (dist / "entry_points.txt").write_text("[langflow.trigger_providers]\npilot = listener_pilot.runtime:PROVIDER\n")
    (dist / "RECORD").write_text("listener_pilot/extension.json,,\n")

    # An installed non-trigger extension must never be imported by this boot.
    unrelated = tmp_path / "unrelated"
    (unrelated / "components").mkdir(parents=True)
    unrelated_manifest = json.loads((package / "extension.json").read_text())
    unrelated_manifest.update(
        id="lfx-unrelated", bundles=[{"name": "unrelated", "path": "components"}], integrations=[]
    )
    (unrelated / "extension.json").write_text(json.dumps(unrelated_manifest))
    (unrelated / "components" / "source.py").write_text(
        "from pathlib import Path\nPath(__file__).with_name('was-imported').touch()\n"
        "raise AssertionError('Unrelated bundle imported')\n"
    )
    unrelated_dist = tmp_path / "lfx_unrelated-0.1.0.dist-info"
    unrelated_dist.mkdir()
    (unrelated_dist / "METADATA").write_text("Metadata-Version: 2.1\nName: lfx-unrelated\nVersion: 0.1.0\n")
    (unrelated_dist / "RECORD").write_text("unrelated/extension.json,,\n")

    script = textwrap.dedent(
        """\
        import asyncio
        import sys
        from lfx.extension.bundle_registry import get_default_registry
        from langflow.services.connection.oauth.adapter import provider_adapter
        from langflow.services.triggers.listeners import runtime
        from langflow.services.triggers.listeners.adapters import registered_adapter_keys
        from langflow.services.triggers.providers.registry import get_provider

        assert get_default_registry().snapshot() == {}
        assert get_provider('pilot') is None
        async def verify_schema():
            assert ('pilot.item', 'pilot.poll') in registered_adapter_keys() if VALID else get_provider('pilot') is None
        runtime.verify_schema = verify_schema
        asyncio.run(runtime.boot_services())
        assert (get_provider('pilot') is not None) == VALID
        assert (provider_adapter('pilot') is not None) == VALID
        assert (('pilot.item', 'pilot.poll') in registered_adapter_keys()) == VALID
        assert 'unrelated' not in sys.modules
        assert 'langflow.main' not in sys.modules
        print('fresh-listener-ok')
        """
    ).replace("VALID", repr(valid_catalog))
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        script,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([str(tmp_path), os.environ.get("PYTHONPATH", "")])},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    assert process.returncode == 0, (stdout + stderr).decode()
    assert b"fresh-listener-ok" in stdout
    assert not (unrelated / "components" / "was-imported").exists()
