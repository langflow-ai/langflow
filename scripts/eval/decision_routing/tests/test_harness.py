"""The routing eval harness measures the real router's decisions and never claims a target it didn't meet."""

import json
from pathlib import Path

import pytest
from lfx.base.models.decisions.schema import DecisionEvaluationError, DecisionResult
from lfx.components.llm_operations import llm_conditional_router

from scripts.eval.decision_routing import run
from scripts.eval.decision_routing.dataset import SuiteError, load_suite
from scripts.eval.decision_routing.metrics import check_targets, percentile, summarize
from scripts.eval.decision_routing.runner import FatalTargetError, Target, route_case

SEED = Path(__file__).parents[1] / "suites/support_ticket_routing.json"
TYPESAFE = Target.parse("TypeSafe:jev-latest")
ROUTE_IDS = ("category_1_result", "category_2_result", "category_3_result")


def _write_suite(tmp_path, cases, **overrides):
    suite = {
        "name": "tiny",
        "kind": "choice",
        "question": "Which team?",
        "minimum_probability": 0.7,
        "routes": [{"name": "Billing"}, {"name": "Sales"}],
        "cases": "cases.jsonl",
        **overrides,
    }
    (tmp_path / "suite.json").write_text(json.dumps(suite))
    (tmp_path / "cases.jsonl").write_text("\n".join(json.dumps(case) for case in cases))
    return tmp_path / "suite.json"


@pytest.fixture
def answer(monkeypatch):
    """Answer the router's decision with probabilities in route order, or raise."""
    answers = {}

    def evaluate(request, **_kwargs):
        reply = answers["next"]
        if isinstance(reply, Exception):
            raise reply
        ids = [option.id for option in request.options]
        return DecisionResult(
            kind="choice", provider="TypeSafe", model="jev-1.13.0", probabilities=dict(zip(ids, reply, strict=True))
        )

    monkeypatch.setattr(llm_conditional_router, "evaluate_decision", evaluate)

    def set_answer(reply):
        answers["next"] = reply

    return set_answer


def test_the_seed_suite_loads():
    suite = load_suite(SEED)
    assert suite.kind == "choice"
    assert suite.outcomes == ("Billing", "Technical Support", "Sales", "Else")
    assert len(suite.cases) == len({case.id for case in suite.cases}) >= 40


@pytest.mark.parametrize(
    ("cases", "overrides", "message"),
    [
        ([{"id": "a", "text": "hi", "expected": "Support"}], {}, "isn't one of"),
        (
            [{"id": "a", "text": "hi", "expected": "Sales"}, {"id": "a", "text": "yo", "expected": "Sales"}],
            {},
            "repeats",
        ),
        ([{"id": "a", "text": "", "expected": "Sales"}], {}, "needs an id, text and expected"),
        ([{"id": "a", "text": "hi", "expected": "Sales"}], {"routes": [{"name": "Sales"}]}, "at least two"),
        ([{"id": "a", "text": "hi", "expected": "Sales"}], {"minimum_probability": 1.5}, "from 0 to 1"),
        ([{"id": "a", "text": "hi", "expected": "Sales"}], {"routes": [{"name": "Else"}, {"name": "Sales"}]}, "Else"),
        ([{"id": "a", "text": "hi", "expected": "Yes"}], {"kind": "boolean"}, "no routes"),
    ],
)
def test_a_bad_suite_says_what_to_fix(tmp_path, cases, overrides, message):
    with pytest.raises(SuiteError, match=message):
        load_suite(_write_suite(tmp_path, cases, **overrides))


def test_records_follow_the_routers_own_policy(tmp_path, answer):
    suite = load_suite(
        _write_suite(
            tmp_path,
            [
                {"id": "right", "text": "charged twice", "expected": "Billing"},
                {"id": "wrong", "text": "pricing?", "expected": "Sales"},
                {"id": "unsure", "text": "hello", "expected": "Else"},
                {"id": "tie", "text": "both", "expected": "Billing"},
            ],
        )
    )
    replies = {"right": (0.9, 0.1), "wrong": (0.8, 0.2), "unsure": (0.6, 0.4), "tie": (0.5, 0.5)}
    records = {}
    for case in suite.cases:
        answer(replies[case.id])
        records[case.id] = route_case(suite, TYPESAFE, case)

    assert {k: (r["routed"], r["outcome"], r["reason"]) for k, r in records.items()} == {
        "right": ("Billing", "correct", "accepted"),
        "wrong": ("Billing", "wrong", "accepted"),
        "unsure": ("Else", "else", "below_minimum_probability"),
        "tie": ("Else", "else", "tied_top_probability"),
    }
    assert records["right"]["model"] == "jev-1.13.0"
    assert records["right"]["latency_ms"] >= 0


def test_an_operational_error_is_measured_not_fatal(tmp_path, answer):
    suite = load_suite(_write_suite(tmp_path, [{"id": "a", "text": "hi", "expected": "Sales"}]))
    answer(DecisionEvaluationError("slow", category="timeout"))

    record = route_case(suite, TYPESAFE, suite.cases[0])

    assert (record["outcome"], record["error_category"]) == ("error", "timeout")


def test_a_rejected_key_stops_the_target(tmp_path, answer):
    suite = load_suite(_write_suite(tmp_path, [{"id": "a", "text": "hi", "expected": "Sales"}]))
    answer(PermissionError("TypeSafe didn't accept the API key"))

    with pytest.raises(FatalTargetError, match="didn't accept the API key"):
        route_case(suite, TYPESAFE, suite.cases[0])


def test_a_replay_reproduces_the_live_record_and_sweeps_without_requests(tmp_path, answer):
    suite = load_suite(_write_suite(tmp_path, [{"id": "a", "text": "hi", "expected": "Billing"}]))
    answer((0.75, 0.25))
    live = route_case(suite, TYPESAFE, suite.cases[0])
    answer(AssertionError("a replay must not ask the provider"))

    same = route_case(suite, TYPESAFE, suite.cases[0], recorded=live["result"])
    stricter = route_case(suite, TYPESAFE, suite.cases[0], minimum_probability=0.8, recorded=live["result"])

    assert (same["routed"], same["outcome"]) == (live["routed"], live["outcome"]) == ("Billing", "correct")
    assert (stricter["routed"], stricter["reason"]) == ("Else", "below_minimum_probability")


def _record(outcome, expected="Billing", routed="Billing", latency=10.0, tokens=(100, 1), category=None):
    return {
        "target": "TypeSafe:jev-latest",
        "outcome": outcome,
        "expected": expected,
        "routed": routed,
        "latency_ms": latency,
        "input_tokens": tokens[0],
        "output_tokens": tokens[1],
        "error_category": category,
        "model": "jev-1.13.0",
        "model_source": "response",
    }


def test_rates_add_up_and_costs_come_only_from_given_prices():
    records = [
        *[_record("correct") for _ in range(6)],
        _record("wrong", routed="Sales"),
        _record("wrong", expected="Else", routed="Sales"),
        _record("else", routed="Else"),
        _record("error", routed="Else", category="timeout", tokens=(None, None), latency=None),
    ]

    unpriced = summarize(records)
    priced = summarize(records, {"TypeSafe:jev-latest": {"input_per_million": 2.0, "output_per_million": 8.0}})

    rates = ("wrong_route_rate", "else_rate", "error_rate")
    assert sum(unpriced[k] for k in rates) + unpriced["correct"] / unpriced["cases"] == pytest.approx(1)
    assert (unpriced["wrong_route_rate"], unpriced["coverage"], unpriced["error_rate"]) == (0.2, 0.8, 0.1)
    assert unpriced["false_accepts"] == 1
    assert unpriced["errors_by_category"] == {"timeout": 1}
    assert unpriced["cost"] is None
    # An answer without usage can't be priced, so the whole target stays unpriced rather than undercounted.
    assert priced["cost"] is None
    assert summarize(records[:-1], {"TypeSafe:jev-latest": {"input_per_million": 2.0}})["cost"] == pytest.approx(
        9 * 100 * 2.0 / 1_000_000
    )


def test_percentile_is_nearest_rank():
    assert percentile([], 0.95) is None
    assert percentile([1, 2, 3, 4], 0.5) == 2
    assert percentile(list(range(1, 101)), 0.95) == 95


def test_targets_pass_only_when_measured_and_met():
    summary = {"wrong_route_rate": 0.03, "coverage": 0.85, "p95_latency_ms": None}

    checks = check_targets(summary, {"max_wrong_route_rate": 0.02, "min_coverage": 0.8, "max_p95_latency_ms": 900})

    assert [(c["target"], c["passed"]) for c in checks] == [
        ("max_wrong_route_rate", False),
        ("min_coverage", True),
        ("max_p95_latency_ms", False),
    ]
    with pytest.raises(ValueError, match="Unknown target"):
        check_targets(summary, {"max_accuracy": 1})


def test_a_live_run_needs_confirmation_and_respects_the_request_cap(capsys):
    assert run.main(["run", str(SEED)]) == 2
    assert "--yes" in capsys.readouterr().err
    assert run.main(["run", str(SEED), "--yes", "--max-requests", "10"]) == 2
    assert "--max-requests" in capsys.readouterr().err


def test_a_fake_run_writes_records_a_summary_and_a_report_without_claiming_targets(tmp_path):
    out = tmp_path / "run"
    real = llm_conditional_router.evaluate_decision

    status = run.main(["run", str(SEED), "--fake", "--target", "TypeSafe:jev-latest", "--out", str(out)])

    assert status == 0
    assert llm_conditional_router.evaluate_decision is real, "fake answers must not outlive the run"
    records = [json.loads(line) for line in (out / "records.jsonl").read_text().splitlines()]
    assert len(records) == len(load_suite(SEED).cases)
    report = (out / "report.md").read_text()
    assert "offline fake answers, not evidence" in report
    assert "No targets were given" in report
    assert "Minimum probability sweep" in report
    # Rebuilding the report with targets checks them against the stored records, without requests.
    targets = tmp_path / "targets.json"
    targets.write_text(json.dumps({"max_wrong_route_rate": 0.0}))
    assert run.main(["report", str(out), "--targets", str(targets)]) in {0, 1}
    assert "## Release targets" in (out / "report.md").read_text()


def test_the_language_model_baseline_routes_like_an_existing_flow(tmp_path, monkeypatch):
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    row = {"provider": "OpenAI", "name": "gpt-4o-mini", "metadata": {}}
    monkeypatch.setattr("lfx.base.models.unified_models.get_language_model_options", lambda *_a, **_k: [row])
    llm = FakeListChatModel(responses=['"Sales"', "NONE"])
    monkeypatch.setattr(llm_conditional_router, "get_llm", lambda **_kwargs: llm)
    decided = []
    monkeypatch.setattr(llm_conditional_router, "evaluate_decision", lambda *a, **_k: decided.append(a))
    suite = load_suite(
        _write_suite(
            tmp_path,
            [{"id": "a", "text": "pricing?", "expected": "Sales"}, {"id": "b", "text": "hello", "expected": "Else"}],
        )
    )
    baseline = Target.parse("OpenAI:gpt-4o-mini", mode="language")

    first, second = (route_case(suite, baseline, case) for case in suite.cases)

    assert (first["target"], first["routed"], first["outcome"]) == ("baseline OpenAI:gpt-4o-mini", "Sales", "correct")
    assert (second["routed"], second["outcome"], second["reason"]) == ("Else", "else", "no_match")
    assert decided == []


def test_an_unavailable_baseline_model_stops_its_target(tmp_path, monkeypatch):
    monkeypatch.setattr("lfx.base.models.unified_models.get_language_model_options", lambda *_a, **_k: [])
    suite = load_suite(_write_suite(tmp_path, [{"id": "a", "text": "hi", "expected": "Sales"}]))

    with pytest.raises(FatalTargetError, match="isn't an available language model"):
        route_case(suite, Target.parse("OpenAI:gpt-4o-mini", mode="language"), suite.cases[0])
