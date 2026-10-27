from uuid import uuid4

from langflow.services.evaluations.failure_breaker import FailureBreaker, failure_detail
from langflow.services.evaluations.row_scoring import RowScores
from langflow.services.evaluations.scorers.llm_judge import UNREADABLE_VERDICT
from langflow.services.evaluations.scorers.types import ScoreResult

RETIRED = "Error code: 404 - The model `o4-mini` has been deprecated (request req_{n})"
JUDGE = [{"type": "llm_judge", "name": "judge"}, {"type": "exact_match", "name": "exact"}]


def test_should_trip_after_identical_failures_ignoring_volatile_ids():
    breaker = FailureBreaker(threshold=3)
    assert breaker.record(RETIRED.format(n="a1b2c3d4e5")) is False  # pragma: allowlist secret
    assert breaker.record(RETIRED.format(n="ffff0000aa")) is False  # pragma: allowlist secret
    assert breaker.record(RETIRED.format(n="1234567890")) is True
    assert breaker.tripped_with.startswith("Error code: 404")


def test_should_reset_on_a_success_or_a_different_error():
    breaker = FailureBreaker(threshold=3)
    breaker.record("boom")
    breaker.record("boom")
    breaker.record(None)
    breaker.record("boom")
    breaker.record("other failure")
    assert breaker.record("boom") is False
    assert breaker.tripped_with is None


def test_should_never_trip_when_disabled():
    breaker = FailureBreaker(threshold=0)
    assert not any(breaker.record("boom") for _ in range(10))


def test_should_read_a_failed_judge_from_the_row_scores():
    scored = RowScores(scores={"judge": ScoreResult(value=None, comment="Scorer failed: model retired")})
    assert failure_detail(None, scored, JUDGE) == "Scorer failed: model retired"
    ok = RowScores(scores={"judge": ScoreResult(value=0.4, comment="Partly right")})
    assert failure_detail(None, ok, JUDGE) is None
    assert failure_detail("flow broke", ok, JUDGE) == "flow broke"


def test_should_show_the_provider_sentence_instead_of_the_raw_body():
    raw = (
        "Scorer failed: Error code: 404 - {'error': {'message': 'The model `o4-mini` has been deprecated', "
        "'type': 'invalid_request_error'}}"
    )
    breaker = FailureBreaker(threshold=1)
    breaker.record(raw)
    assert breaker.tripped_with == "The model `o4-mini` has been deprecated"


def test_should_trip_on_errors_that_differ_only_by_a_uuid():
    breaker = FailureBreaker(threshold=3)
    tripped = [breaker.record(f"Request {uuid4()} failed: quota exceeded") for _ in range(3)]
    assert tripped == [False, False, True]


def test_should_ignore_the_case_of_hex_ids():
    breaker = FailureBreaker(threshold=2)
    breaker.record("trace ABCDEF0123 failed")
    assert breaker.record("trace 0123abcdef failed") is True


def test_should_count_an_unreadable_judge_verdict_as_a_failure():
    scored = RowScores(scores={"judge": ScoreResult(value=None, comment=UNREADABLE_VERDICT)})
    assert failure_detail(None, scored, JUDGE) == UNREADABLE_VERDICT
