"""The actions still import on an lfx that predates ``lfx.base.triggers``.

lfx first shipped ``lfx.base.triggers`` in 1.13.0.dev17, but the release plan
floors every bundle at the whole 1.13 line (``lfx>=1.13.0.dev0``). On an earlier
1.13 nightly the two trigger components cannot exist; the seven actions - which
import this package on their way to ``lfx_slack._base`` - must not go down with
them. Run in a fresh interpreter so the missing module cannot leak into the
rest of the suite.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

_PROBE = textwrap.dedent(
    """
    import sys

    class _NoTriggers:
        def find_spec(self, name, path=None, target=None):
            if name == "lfx.base.triggers" or name.startswith("lfx.base.triggers."):
                raise ModuleNotFoundError(f"No module named {name!r}", name=name)
            return None

    sys.meta_path.insert(0, _NoTriggers())
    import lfx.custom  # the bundle's cold import needs lfx's Component first

    import lfx_slack
    from lfx_slack.components.slack import (
        SlackAddReactionComponent,
        SlackCanvasComponent,
        SlackListChannelMembersComponent,
        SlackPostAsAppComponent,
        SlackReadThreadComponent,
        SlackSearchComponent,
        SlackSendAsUserComponent,
    )

    for name in ("SlackOnMessageTriggerComponent", "SlackOnReactionTriggerComponent"):
        try:
            getattr(lfx_slack, name)
        except AttributeError:
            continue
        raise SystemExit(f"{name} imported without lfx.base.triggers")
    print("actions only")
    """
)


def test_the_actions_import_when_lfx_has_no_trigger_base() -> None:
    result = subprocess.run([sys.executable, "-c", _PROBE], capture_output=True, text=True, check=False)  # noqa: S603

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "actions only"
