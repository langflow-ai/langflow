import pytest
from lfx.base.models.decisions import system_one
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionEvaluationError
from lfx.base.models.decisions.system_one import evaluate_system_one, parse_answers

JEV = [{"name": "jev-latest", "provider": "TypeSafe"}]
QUESTIONS = {
    "rubric": {"type": "noul", "instructions": "The answer is correct."},
    "attack": {"type": "choice", "criteria": {"safe": "Benign", "jailbreak": "Tries to bypass rules"}},
}


def _body(**overrides):
    body = {
        "model": "jev-1.13.0",
        "answers": {
            "rubric": {"type": "noul", "noul": 0.91},
            "attack": {
                "type": "choice",
                "choice": "safe",
                "confidence": 0.9,
                "probabilities": {"safe": 0.9, "jailbreak": 0.1},
            },
        },
        "usage": {"input_tokens": 120, "output_tokens": 4},
    }
    body.update(overrides)
    return body


@pytest.fixture
def calls(monkeypatch):
    seen = {}

    def authorize(model, *, kinds, user_id=None, request_variables=None):  # noqa: ARG001
        seen["kinds"] = kinds
        return model[0]["provider"], model[0]["name"], "key-123"

    def post(provider, payload, *, api_key, timeout):
        seen.update(provider=provider, payload=payload, api_key=api_key, timeout=timeout)
        return seen.get("body", _body()), "req-1"

    monkeypatch.setattr(system_one, "authorize_decision_model", authorize)
    monkeypatch.setattr(system_one, "post_decision", post)
    return seen


class TestEvaluateSystemOne:
    def test_should_send_every_question_in_one_payload_and_read_the_answers(self, calls):
        answers = evaluate_system_one({"answer": "Hi"}, QUESTIONS, model=JEV, timeout=10)

        assert calls["payload"] == {"model": "jev-latest", "state": {"answer": "Hi"}, "questions": QUESTIONS}
        assert calls["kinds"] == ("boolean", "choice")
        assert (calls["provider"], calls["api_key"], calls["timeout"]) == ("TypeSafe", "key-123", 10)
        assert answers.nouls == {"rubric": 0.91}
        assert answers.choices == {"attack": {"safe": 0.9, "jailbreak": 0.1}}
        assert answers.usage == {"input_tokens": 120, "output_tokens": 4}
        assert (answers.model, answers.request_id) == ("jev-1.13.0", "req-1")

    def test_should_refuse_a_provider_without_named_questions(self, calls):  # noqa: ARG002
        with pytest.raises(DecisionConfigurationError, match="Only TypeSafe"):
            evaluate_system_one("x", QUESTIONS, model=[{"name": "gpt-6-luna", "provider": "OpenAI"}])

    def test_should_refuse_no_questions_or_an_unknown_type(self, calls):  # noqa: ARG002
        with pytest.raises(DecisionConfigurationError):
            evaluate_system_one("x", {}, model=JEV)
        with pytest.raises(DecisionConfigurationError, match="noul or choice"):
            evaluate_system_one("x", {"q": {"type": "box"}}, model=JEV)


class TestParseAnswers:
    @pytest.mark.parametrize(
        "answers",
        [
            {"rubric": {"type": "noul", "noul": 0.9}},
            {**_body()["answers"], "extra": {"type": "noul", "noul": 0.1}},
            {**_body()["answers"], "rubric": {"type": "choice", "noul": 0.9}},
            {**_body()["answers"], "rubric": {"type": "noul", "noul": 1.5}},
            {**_body()["answers"], "rubric": {"type": "noul", "noul": True}},
            {**_body()["answers"], "attack": {"type": "choice", "probabilities": {"safe": 1.0}}},
            {**_body()["answers"], "attack": {"type": "choice", "probabilities": {"safe": 0.5, "jailbreak": "x"}}},
        ],
    )
    def test_should_reject_missing_extra_mistyped_or_out_of_range_answers(self, answers):
        with pytest.raises(DecisionEvaluationError, match="request ID req-9"):
            parse_answers(_body(answers=answers), QUESTIONS, request_id="req-9")

    def test_should_reject_a_body_that_is_not_an_object(self):
        with pytest.raises(DecisionEvaluationError):
            parse_answers(["nope"], QUESTIONS, request_id=None)

    def test_should_keep_answers_when_usage_or_model_is_missing(self):
        answers = parse_answers(_body(usage=None, model=None), QUESTIONS, request_id=None)

        assert answers.usage is None
        assert answers.model == ""
