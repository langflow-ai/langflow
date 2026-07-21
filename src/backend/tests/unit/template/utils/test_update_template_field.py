import pytest
from lfx.template import utils as template_utils


@pytest.mark.parametrize(
    ("rebuilt_load_from_db", "saved_load_from_db"),
    [(False, True), (True, False)],
)
def test_update_template_field_preserves_explicit_load_from_db_for_equal_values(
    *,
    rebuilt_load_from_db: bool,
    saved_load_from_db: bool,
) -> None:
    new_template = {
        "jwt_token": {
            "type": "str",
            "value": "JWT",
            "load_from_db": rebuilt_load_from_db,
        }
    }
    previous_value = {
        "type": "str",
        "value": "JWT",
        "load_from_db": saved_load_from_db,
    }

    template_utils.update_template_field(new_template, "jwt_token", previous_value)

    assert new_template["jwt_token"]["load_from_db"] is saved_load_from_db


@pytest.mark.parametrize("saved_load_from_db", [False, True])
def test_update_template_field_preserves_explicit_load_from_db_for_changed_values(
    *,
    saved_load_from_db: bool,
) -> None:
    new_template = {
        "jwt_token": {
            "type": "str",
            "value": "",
            "load_from_db": not saved_load_from_db,
        }
    }
    previous_value = {
        "type": "str",
        "value": "OPENSEARCH_JWT",
        "load_from_db": saved_load_from_db,
    }

    template_utils.update_template_field(new_template, "jwt_token", previous_value)

    assert new_template["jwt_token"]["value"] == "OPENSEARCH_JWT"
    assert new_template["jwt_token"]["load_from_db"] is saved_load_from_db


def test_update_template_field_keeps_rebuilt_load_from_db_when_saved_state_is_missing() -> None:
    new_template = {
        "jwt_token": {
            "type": "str",
            "value": "JWT",
            "load_from_db": True,
        }
    }
    previous_value = {"type": "str", "value": "JWT"}

    template_utils.update_template_field(new_template, "jwt_token", previous_value)

    assert new_template["jwt_token"]["load_from_db"] is True


def test_update_template_field_uses_false_for_changed_value_without_saved_load_from_db() -> None:
    new_template = {
        "jwt_token": {
            "type": "str",
            "value": "",
            "load_from_db": True,
        }
    }
    previous_value = {"type": "str", "value": "JWT"}

    template_utils.update_template_field(new_template, "jwt_token", previous_value)

    assert new_template["jwt_token"]["value"] == "JWT"
    assert new_template["jwt_token"]["load_from_db"] is False


def test_update_template_field_does_not_add_load_from_db_to_unsupported_field() -> None:
    new_template = {"jwt_token": {"type": "str", "value": "JWT"}}
    previous_value = {
        "type": "str",
        "value": "JWT",
        "load_from_db": True,
    }

    template_utils.update_template_field(new_template, "jwt_token", previous_value)

    assert "load_from_db" not in new_template["jwt_token"]


def test_update_template_field_ignores_mismatched_types() -> None:
    new_template = {
        "jwt_token": {
            "type": "str",
            "value": "",
            "load_from_db": False,
        }
    }
    previous_value = {
        "type": "int",
        "value": "JWT",
        "load_from_db": True,
    }

    template_utils.update_template_field(new_template, "jwt_token", previous_value)

    assert new_template["jwt_token"] == {
        "type": "str",
        "value": "",
        "load_from_db": False,
    }


def test_update_template_field_ignores_none_value() -> None:
    new_template = {
        "jwt_token": {
            "type": "str",
            "value": "",
            "load_from_db": False,
        }
    }
    previous_value = {
        "type": "str",
        "value": None,
        "load_from_db": True,
    }

    template_utils.update_template_field(new_template, "jwt_token", previous_value)

    assert new_template["jwt_token"] == {
        "type": "str",
        "value": "",
        "load_from_db": False,
    }
