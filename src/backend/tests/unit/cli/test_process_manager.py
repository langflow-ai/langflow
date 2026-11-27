"""``langflow run`` waits for gunicorn as long as gunicorn waits for its workers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langflow.__main__ import ProcessManager


@pytest.mark.parametrize(("grace_s", "timeout"), [(0, 30), (20, 50)])
def test_shutdown_waits_for_the_grace_on_top_of_gunicorns_timeout(monkeypatch, grace_s, timeout):
    manager = ProcessManager()
    manager.shutdown_grace_s = grace_s
    webapp = MagicMock()
    webapp.is_alive.side_effect = [True, False]
    manager.webapp_process = webapp
    monkeypatch.setattr(manager, "print_farewell_message", lambda: None)

    with pytest.raises(SystemExit):
        manager.shutdown()

    webapp.join.assert_called_once_with(timeout=timeout)
    webapp.kill.assert_not_called()
