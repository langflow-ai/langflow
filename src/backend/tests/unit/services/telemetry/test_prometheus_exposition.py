"""Process-isolated proof that OTel metrics reach the Prometheus exposition.

The OTel global meter provider and the OpenTelemetry singleton are process-wide,
so this test spawns a clean subprocess to avoid polluting (or being polluted by)
other tests. It builds the real telemetry service, emits a background-execution
counter and sets a gauge, then asserts the metric names appear in the real
prometheus_client exposition. No mocking: this is the real reader.
"""

import os
import subprocess
import sys
import textwrap


def test_otel_metrics_reach_prometheus_exposition():
    script = textwrap.dedent(
        """
        import asyncio
        from langflow.services.deps import get_telemetry_service

        async def main():
            ts = get_telemetry_service()
            ts.ot.set_observable_counter("langflow_bg_jobs_started_total", 1, {"backend": "scaled"})
            ts.ot.update_gauge("langflow_bg_workers_online", 2, {"backend": "scaled"})
            from prometheus_client import generate_latest
            out = generate_latest().decode()
            assert "langflow_bg_jobs_started_total" in out, "counter missing from exposition"
            assert "langflow_bg_workers_online" in out, "gauge missing from exposition"
            print("EXPOSITION_OK")

        asyncio.run(main())
        """
    )
    res = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "LANGFLOW_PROMETHEUS_ENABLED": "true"},
        check=False,
    )
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "EXPOSITION_OK" in res.stdout
