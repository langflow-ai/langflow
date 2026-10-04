"""lfx-darkmoon-findings: Darkmoon Findings Parser bundle.

This package is the distribution unit ``lfx-darkmoon-findings``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers ``DarkmoonFindingsParserComponent`` under the
namespaced ID ``ext:darkmoon_findings:DarkmoonFindingsParserComponent@official``.

Darkmoon (https://github.com/ASCIT31/Dark-Moon) is an open source (GPL-3.0)
autonomous AI penetration testing platform.  The component only reads the
findings JSON that a Darkmoon scan already produced: it makes no network
calls and needs no credentials.
"""

from lfx_darkmoon_findings.components.darkmoon_findings.darkmoon_findings_parser import (
    DarkmoonFindingsParserComponent,
)

__all__ = ["DarkmoonFindingsParserComponent"]
