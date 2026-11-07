"""Tests for check_ko.py."""

import json

import check_ko
import pytest

BACKEND_EN = check_ko.load(check_ko.BACKEND_DIR / "en.json")


def _name_key(component: str) -> str:
    return next(key for key in BACKEND_EN if key.startswith(f"components.{component}.display_name."))


def _check_backend(tmp_path, translations: dict[str, str]) -> int:
    path = tmp_path / "part.json"
    path.write_text(json.dumps(translations, ensure_ascii=False), encoding="utf-8")
    return check_ko.check_backend(path, partial=True, max_lines=0)


def _warnings(en_value: str, ko_value: str) -> list[str]:
    report = check_ko.Report("test")
    check_ko.check_value(report, "key", en_value, ko_value, markdown=False)
    return report.warnings


class TestBackendNameKeys:
    @pytest.mark.parametrize("component", ["inboundwebhooktrigger", "scheduletrigger"])
    def test_accepts_trigger_names_translated_in_every_locale(self, tmp_path, component):
        assert _check_backend(tmp_path, {_name_key(component): "이름"}) == 0

    def test_rejects_other_component_names(self, tmp_path):
        assert _check_backend(tmp_path, {_name_key("smartrouter"): "스마트 라우터"}) == 1

    def test_rejects_starter_flow_names(self, tmp_path):
        key = next(key for key in BACKEND_EN if key.startswith("starter_flows.") and key.endswith(".name"))
        assert _check_backend(tmp_path, {key: "템플릿"}) == 1


class TestParticleAfterVariable:
    @pytest.mark.parametrize(
        "ko_value",
        [
            "최소 확률 {{threshold}}을 충족했습니다.",
            "Score {{score}}는 {{level}} 레벨로 반올림됩니다.",
        ],
        ids=["threshold-eul", "score-neun"],
    )
    def test_warns_on_batchim_dependent_particle(self, ko_value):
        warnings = _warnings("{{option}} met {{threshold}}, {{score}} rounds to {{level}}.", ko_value)

        assert any("no batchim-dependent particle right after a variable" in w for w in warnings)

    @pytest.mark.parametrize(
        "ko_value",
        [
            "최소 확률 {{threshold}} 이상입니다.",
            "Score는 {{score}}이며, 반올림하면 {{level}} 레벨입니다.",
        ],
        ids=["noun-after-threshold", "copula-after-score"],
    )
    def test_accepts_a_copula_or_a_noun_after_the_variable(self, ko_value):
        warnings = _warnings("{{option}} met {{threshold}}, {{score}} rounds to {{level}}.", ko_value)

        assert not any("after a variable" in w for w in warnings)
