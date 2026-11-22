"""Cold imports must work when the optional Langflow backend is absent."""

import os
import subprocess
import sys
import textwrap


def test_cold_components_do_not_import_backend():
    script = textwrap.dedent("""\
        import importlib.abc
        import sys

        class NoBackend(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'langflow' or fullname.startswith('langflow.'):
                    raise ModuleNotFoundError('Backend unavailable', name=fullname)

        sys.meta_path.insert(0, NoBackend())
        from lfx_servicenow.components.servicenow import ServiceNowCreateRecordComponent
        from lfx_servicenow.manifest import manifest
        assert len(manifest().capabilities) == 6
        assert ServiceNowCreateRecordComponent().name == 'ServiceNowCreateRecord'
        assert not any(name == 'langflow' or name.startswith('langflow.') for name in sys.modules)
        print('backend-free-import-ok')
    """)
    process = subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", script], env=os.environ.copy(), capture_output=True, text=True, timeout=60, check=False
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert "backend-free-import-ok" in process.stdout
