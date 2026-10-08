"""Unit tests for the Darkmoon Findings Parser extension bundle (``lfx-darkmoon-findings``).

The component is pure computation over a findings document, so the tests need
no network access and no mocks.
"""

from __future__ import annotations

import json

import pytest
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx_darkmoon_findings import DarkmoonFindingsParserComponent

FINDINGS = [
    {
        "title": "Reflected XSS in search",
        "severity": "medium",
        "cvss_score": 6.1,
        "category": "xss_reflected",
        "status": "confirmed",
        "description": "The q parameter is reflected without encoding.",
        "endpoint": "https://staging.example.com/search",
        "discovered_by_agent": "nodejs",
        "cve": None,
        "mitre_attack_id": "T1189",
    },
    {
        "title": "SQL injection in login",
        "severity": "critical",
        "cvss_score": 9.8,
        "category": "sql_injection",
        "status": "exploited",
        "description": "The username field is concatenated into a query.",
        "endpoint": "https://staging.example.com/login",
        "discovered_by_agent": "php",
        "remediation": "Use parameterized queries.",
        "evidence_commands": ["sqlmap -u https://staging.example.com/login"],
    },
    {
        "title": "Server header discloses version",
        "severity": "low",
        "cvss_score": 3.7,
        "category": "information_disclosure",
        "status": "unconfirmed",
        "description": "The Server header reveals the exact version.",
        "endpoint": "https://staging.example.com/",
        "discovered_by_agent": "nginx",
    },
    {
        "title": "Stored XSS in profile | bio",
        "severity": "HIGH",
        "cvss_score": 8.1,
        "category": "xss_stored",
        "status": "exploited",
        "description": "The bio field is stored and rendered unescaped.",
        "endpoint": "https://staging.example.com/profile",
        "discovered_by_agent": "nodejs",
    },
]


def make_component(findings=None, **overrides) -> DarkmoonFindingsParserComponent:
    c = DarkmoonFindingsParserComponent()
    c.findings = json.dumps(FINDINGS) if findings is None else findings
    c.min_severity = "info"
    c.proof_status = "any"
    c.fail_on = "none"
    for key, value in overrides.items():
        setattr(c, key, value)
    return c


def titles(table: DataFrame) -> list[str]:
    return list(table["title"])


def test_component_metadata():
    """Class name must stay stable for saved flows."""
    assert DarkmoonFindingsParserComponent.__name__ == "DarkmoonFindingsParserComponent"


def test_table_is_sorted_most_severe_first_and_keeps_all_fields():
    table = make_component().build_findings_table()
    assert titles(table) == [
        "SQL injection in login",
        "Stored XSS in profile | bio",
        "Reflected XSS in search",
        "Server header discloses version",
    ]
    assert list(table["severity"]) == ["critical", "high", "medium", "low"]
    assert list(table.columns[:3]) == ["severity", "title", "cvss_score"]
    assert "remediation" in table.columns
    assert "mitre_attack_id" in table.columns


@pytest.mark.parametrize(
    "document",
    [
        json.dumps(FINDINGS),
        json.dumps({"findings": FINDINGS}),
        json.dumps({"data": FINDINGS}),
    ],
)
def test_accepts_bare_array_and_both_envelopes(document):
    assert make_component(document).build_summary().data["total"] == 4


def test_accepts_message_data_and_table_inputs():
    assert make_component(Message(text=json.dumps(FINDINGS))).build_summary().data["total"] == 4
    assert make_component(Data(data={"findings": FINDINGS})).build_summary().data["total"] == 4
    assert make_component(DataFrame(FINDINGS)).build_summary().data["total"] == 4


def test_accepts_a_list_of_data_objects_and_a_single_finding():
    assert make_component([Data(data=f) for f in FINDINGS]).build_summary().data["total"] == 4
    assert make_component(Data(data=FINDINGS[1])).build_summary().data["total"] == 1


def test_min_severity_filter():
    summary = make_component(min_severity="high").build_summary().data
    assert summary["total"] == 2
    assert summary["severity_counts"] == {"critical": 1, "high": 1, "medium": 0, "low": 0, "info": 0}
    assert summary["highest_severity"] == "critical"


def test_proof_status_filters():
    exploited = make_component(proof_status="exploited").build_findings_table()
    assert titles(exploited) == ["SQL injection in login", "Stored XSS in profile | bio"]
    proved = make_component(proof_status="confirmed or exploited").build_summary().data
    assert proved["total"] == 3


def test_filters_combine():
    table = make_component(min_severity="high", proof_status="exploited").build_findings_table()
    assert titles(table) == ["SQL injection in login", "Stored XSS in profile | bio"]
    assert make_component(min_severity="critical", proof_status="exploited").build_summary().data["total"] == 1
    assert make_component(min_severity="high", proof_status="confirmed or exploited").build_summary().data["total"] == 2


@pytest.mark.parametrize(
    ("fail_on", "expected"),
    [("none", False), ("low", True), ("medium", True), ("high", True), ("critical", True)],
)
def test_gate_trips_when_a_finding_reaches_the_threshold(fail_on, expected):
    assert make_component(fail_on=fail_on).build_summary().data["gate_failed"] is expected


def test_gate_ignores_findings_removed_by_the_filters():
    document = json.dumps(
        [
            {"title": "Unproven critical", "severity": "critical", "status": "unconfirmed"},
            {"title": "Proven low", "severity": "low", "status": "exploited"},
        ]
    )
    summary = make_component(document, fail_on="critical", proof_status="exploited").build_summary().data
    assert summary["total"] == 1
    assert summary["gate_failed"] is False
    assert make_component(document, fail_on="critical").build_summary().data["gate_failed"] is True


def test_gate_does_not_trip_below_threshold():
    only_low = json.dumps([FINDINGS[2]])
    assert make_component(only_low, fail_on="medium").build_summary().data["gate_failed"] is False


def test_unrated_findings_are_kept_as_info_and_never_trip_the_gate():
    document = json.dumps([{"title": "No severity"}, {"title": "Odd", "severity": "catastrophic"}])
    component = make_component(document, fail_on="low")
    summary = component.build_summary().data
    assert summary["total"] == 2
    assert summary["severity_counts"]["info"] == 2
    assert summary["highest_severity"] == "info"
    assert summary["gate_failed"] is False
    assert list(component.build_findings_table()["severity"]) == ["info", "info"]


def test_empty_findings_array():
    component = make_component("[]", fail_on="low")
    assert component.build_summary().data == {
        "total": 0,
        "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        "highest_severity": None,
        "gate_failed": False,
    }
    assert len(component.build_findings_table()) == 0
    assert component.build_report().text == "No Darkmoon findings match the filters."


def test_report_is_a_markdown_table_with_escaped_cells():
    text = make_component(min_severity="high").build_report().text
    lines = text.splitlines()
    assert lines[0] == "**2 Darkmoon finding(s)**, highest severity: critical"
    assert lines[2] == "| Severity | Title | CVSS | Status | Endpoint |"
    assert lines[4] == "| critical | SQL injection in login | 9.8 | exploited | https://staging.example.com/login |"
    assert lines[5] == (
        "| high | Stored XSS in profile \\| bio | 8.1 | exploited | https://staging.example.com/profile |"
    )


def test_ties_on_severity_are_broken_by_cvss_then_title():
    document = json.dumps(
        [
            {"title": "B", "severity": "high", "cvss_score": 7.0},
            {"title": "A", "severity": "high", "cvss_score": 7.0},
            {"title": "C", "severity": "high", "cvss_score": "8.5"},
            {"title": "D", "severity": "high", "cvss_score": "n/a"},
        ]
    )
    assert titles(make_component(document).build_findings_table()) == ["C", "A", "B", "D"]


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ("", "empty"),
        ("   ", "empty"),
        ("not json", "not valid JSON"),
        ('{"unrelated": 1}', "Expected a Darkmoon findings document"),
        ("42", "Expected a Darkmoon findings document"),
        ('[{"title": "ok"}, "oops"]', "Finding 1 is not a JSON object"),
    ],
)
def test_invalid_documents_raise_a_clear_error(document, message):
    with pytest.raises(ValueError, match=message):
        make_component(document).build_summary()


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("min_severity", "urgent", "Unknown minimum severity"),
        ("proof_status", "confirmed", "Unknown proof status"),
        ("fail_on", "info", "Unknown fail on severity"),
    ],
)
def test_unknown_dropdown_values_raise_instead_of_widening_a_filter(option, value, message):
    with pytest.raises(ValueError, match=message):
        make_component(**{option: value}).build_summary()


def test_missing_input_raises_a_clear_error():
    component = make_component()
    component.findings = None
    with pytest.raises(ValueError, match="Connect the findings JSON"):
        component.build_summary()
