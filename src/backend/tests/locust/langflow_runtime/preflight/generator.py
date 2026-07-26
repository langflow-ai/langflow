"""Generator headroom checks for Locust preflight."""

from __future__ import annotations

from tests.locust.langflow_runtime.preflight.health import CheckResult


def check_generator_headroom(*, max_cpu_pct: float = 90.0) -> CheckResult:
    """Stub headroom probe using psutil when available; otherwise skip."""
    try:
        import psutil
    except ImportError:
        return CheckResult(name="generator_headroom", ok=True, detail="skipped (psutil unavailable)")

    cpu = float(psutil.cpu_percent(interval=0.2))
    mem = psutil.virtual_memory()
    detail = f"cpu={cpu:.1f}% mem_available={mem.available}"
    if cpu > max_cpu_pct:
        return CheckResult(name="generator_headroom", ok=False, detail=detail)
    return CheckResult(name="generator_headroom", ok=True, detail=detail)
