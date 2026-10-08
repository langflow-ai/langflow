import json
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, HandleInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output

SEVERITIES = ("info", "low", "medium", "high", "critical")
SEVERITY_RANK = {name: rank for rank, name in enumerate(SEVERITIES)}
PROOF_ANY = "any"
PROOF_CONFIRMED = "confirmed or exploited"
PROOF_EXPLOITED = "exploited"
PROOF_STATUSES = {
    PROOF_ANY: None,
    PROOF_CONFIRMED: frozenset({"confirmed", "exploited"}),
    PROOF_EXPLOITED: frozenset({"exploited"}),
}
GATE_OFF = "none"
TABLE_COLUMNS = ("severity", "title", "cvss_score", "status", "category", "endpoint", "cve")


def _decode(value: Any) -> Any:
    """Turn the supported input types into plain Python (JSON text, Message, Data, Table, lists)."""
    if isinstance(value, Message):
        return _decode(value.text)
    if isinstance(value, Data):
        return _decode(value.data)
    if isinstance(value, DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            msg = "The findings input is empty."
            raise ValueError(msg)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            msg = f"The findings input is not valid JSON: {e}"
            raise ValueError(msg) from e
    if isinstance(value, list):
        return [_decode(item) if isinstance(item, Message | Data | str) else item for item in value]
    return value


def _extract_findings(document: Any) -> list[dict]:
    """Return the finding objects of a Darkmoon findings document.

    Accepted shapes: a bare array of findings, an object with a ``findings`` or ``data`` array,
    or a ``Data`` object that wraps a single finding (it has a ``title`` and a ``severity``).
    """
    if isinstance(document, dict):
        for key in ("findings", "data"):
            if isinstance(document.get(key), list):
                return _extract_findings(document[key])
        if "title" in document or "severity" in document:
            return [document]
        msg = "Expected a Darkmoon findings document: a JSON array, or an object with a 'findings' or 'data' array."
        raise ValueError(msg)
    if isinstance(document, list):
        findings = []
        for index, item in enumerate(document):
            if not isinstance(item, dict):
                msg = f"Finding {index} is not a JSON object."
                raise ValueError(msg)  # noqa: TRY004 - invalid input value, not a type misuse
            findings.append(item)
        return findings
    msg = "Expected a Darkmoon findings document: a JSON array, or an object with a 'findings' or 'data' array."
    raise ValueError(msg)


def _severity(finding: dict) -> str:
    """Normalized severity; a missing or unknown value counts as ``info`` so no finding is dropped."""
    value = str(finding.get("severity") or "").strip().lower()
    return value if value in SEVERITY_RANK else "info"


def _cvss(finding: dict) -> float:
    try:
        return float(finding.get("cvss_score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _choice(value: Any, allowed: Any, label: str) -> str:
    """Validate a dropdown value so a stale or mistyped option fails loudly instead of widening a filter."""
    if value not in allowed:
        msg = f"Unknown {label} {value!r}. Expected one of: {', '.join(allowed)}."
        raise ValueError(msg)
    return value


def _cell(value: Any) -> str:
    """Make a value safe for a Markdown table cell."""
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ").strip()


class DarkmoonFindingsParserComponent(Component):
    """Parse, filter and summarize the findings JSON of a Darkmoon scan."""

    display_name = "Darkmoon Findings Parser"
    description = "Filter, sort and summarize the findings JSON of a Darkmoon scan, and optionally gate on severity."
    documentation = "https://github.com/ASCIT31/Dark-Moon"
    icon = "shield-check"
    name = "DarkmoonFindingsParser"

    inputs = [
        HandleInput(
            name="findings",
            display_name="Findings",
            info=(
                "The findings JSON of a Darkmoon scan: JSON text, a Message, a JSON object, or a Table. "
                "A bare array, or an object with a 'findings' or 'data' array, is accepted."
            ),
            required=True,
            input_types=["Message", "Data", "JSON", "DataFrame", "Table"],
        ),
        DropdownInput(
            name="min_severity",
            display_name="Minimum Severity",
            options=list(SEVERITIES),
            value="info",
            info="Keep only findings at or above this severity.",
        ),
        DropdownInput(
            name="proof_status",
            display_name="Proof Status",
            options=list(PROOF_STATUSES),
            value=PROOF_ANY,
            info="Keep only findings Darkmoon proved: 'exploited', or 'confirmed or exploited'.",
            advanced=True,
        ),
        DropdownInput(
            name="fail_on",
            display_name="Fail On Severity",
            options=[GATE_OFF, *SEVERITIES[1:]],
            value=GATE_OFF,
            info="Set the 'gate_failed' summary flag when a kept finding is at or above this severity.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Findings Table", name="findings_table", method="build_findings_table"),
        Output(display_name="Summary", name="summary", method="build_summary"),
        Output(display_name="Report", name="report", method="build_report"),
    ]

    def _kept_findings(self) -> list[dict]:
        """Parse the input, apply the filters and order the findings most severe first."""
        if self.findings is None:
            msg = "Connect the findings JSON of a Darkmoon scan to the Findings input."
            raise ValueError(msg)
        findings = _extract_findings(_decode(self.findings))
        minimum = SEVERITY_RANK[_choice(self.min_severity or "info", SEVERITIES, "minimum severity")]
        proofs = PROOF_STATUSES[_choice(self.proof_status or PROOF_ANY, PROOF_STATUSES, "proof status")]
        kept = [
            finding
            for finding in findings
            if SEVERITY_RANK[_severity(finding)] >= minimum
            and (proofs is None or str(finding.get("status") or "").strip().lower() in proofs)
        ]
        kept.sort(key=lambda f: (-SEVERITY_RANK[_severity(f)], -_cvss(f), str(f.get("title") or "")))
        return kept

    def _summarize(self, kept: list[dict]) -> dict:
        counts = dict.fromkeys(reversed(SEVERITIES), 0)
        for finding in kept:
            counts[_severity(finding)] += 1
        highest = next((name for name, count in counts.items() if count), None)
        threshold = _choice(self.fail_on or GATE_OFF, (GATE_OFF, *SEVERITIES[1:]), "fail on severity")
        gate_failed = threshold != GATE_OFF and any(
            SEVERITY_RANK[_severity(finding)] >= SEVERITY_RANK[threshold] for finding in kept
        )
        return {
            "total": len(kept),
            "severity_counts": counts,
            "highest_severity": highest,
            "gate_failed": gate_failed,
        }

    def build_findings_table(self) -> DataFrame:
        """Return the kept findings as a table, most severe first, with every original field."""
        rows = [{**finding, "severity": _severity(finding)} for finding in self._kept_findings()]
        table = DataFrame(rows)
        leading = [column for column in TABLE_COLUMNS if column in table.columns]
        trailing = [column for column in table.columns if column not in leading]
        self.status = f"{len(rows)} finding(s)"
        return DataFrame(table[[*leading, *trailing]]) if rows else table

    def build_summary(self) -> Data:
        """Return the total, the count per severity, the highest severity and the gate flag."""
        summary = self._summarize(self._kept_findings())
        self.status = f"{summary['total']} finding(s), highest: {summary['highest_severity'] or 'none'}"
        return Data(data=summary)

    def build_report(self) -> Message:
        """Return a Markdown table of the kept findings, suitable for a chat message or a ticket."""
        kept = self._kept_findings()
        summary = self._summarize(kept)
        if not kept:
            return Message(text="No Darkmoon findings match the filters.")
        lines = [
            f"**{summary['total']} Darkmoon finding(s)**, highest severity: {summary['highest_severity']}",
            "",
            "| Severity | Title | CVSS | Status | Endpoint |",
            "|---|---|---|---|---|",
        ]
        lines.extend(
            f"| {_severity(f)} | {_cell(f.get('title'))} | {_cell(f.get('cvss_score'))} "
            f"| {_cell(f.get('status'))} | {_cell(f.get('endpoint'))} |"
            for f in kept
        )
        return Message(text="\n".join(lines))
