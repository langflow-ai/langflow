"""One constrained grammar for compiled rules and canonical authorization requests."""

from itertools import product
from types import MappingProxyType
from typing import NamedTuple
from uuid import UUID

from langflow.services.authorization.actions import ShareAction
from langflow.services.authorization.policy import TEAM_ROLES, TeamOperation
from langflow.services.authorization.repository import supported_actions

TEAM_ACTIONS = MappingProxyType(
    {
        "admin": frozenset({"read", "update"})
        | {f"{operation}:{role}" for operation in ("add_member", "remove_member") for role in TEAM_ROLES}
        | {f"change_role:{old}:{new}" for old, new in product(TEAM_ROLES, repeat=2)},
        "maintainer": frozenset({"read", "add_member:user", "remove_member:user"}),
        "user": frozenset({"read"}),
    }
)
_TEAM_REQUEST_ACTIONS = frozenset().union(*TEAM_ACTIONS.values(), (operation.value for operation in TeamOperation))
_MAX_RULE_FIELD_LENGTH = 255


class PolicyFormatError(ValueError):
    """Malformed policy/request syntax; never a reason to load partial rules."""


class Rule(NamedTuple):
    """Semantic identity in the existing CasbinRule slot order, without its row ID."""

    ptype: str
    v0: str
    v1: str
    v2: str | None = None
    v3: str | None = None
    v4: str | None = None
    v5: str | None = None


def policy_actions(resource_type: str) -> frozenset[str]:
    """Reuse the application's finite vocabulary, including distinct share actions."""
    if resource_type == "share":
        return frozenset(action.value for action in ShareAction)
    return supported_actions(resource_type)


def canonical_uuid(value: str) -> str:
    """Reject ambiguous identifiers before they can reach keyMatch2."""
    msg = "A canonical UUID is required."
    if not isinstance(value, str):
        raise PolicyFormatError(msg)
    try:
        normalized = str(UUID(value))
    except ValueError as exc:
        raise PolicyFormatError(msg) from exc
    if normalized != value:
        raise PolicyFormatError(msg)
    return value


def validate_domain(domain: str) -> None:
    """A star is one literal unscoped domain, never a scope pattern."""
    if domain == "*":
        return
    if not isinstance(domain, str):
        msg = "Unsupported policy domain."
        raise PolicyFormatError(msg)
    kind, separator, identifier = domain.partition(":")
    if not separator or kind not in {"project", "workspace"}:
        msg = "Unsupported policy domain."
        raise PolicyFormatError(msg)
    canonical_uuid(identifier)


def _principal(principal: str) -> tuple[str, str, str | None]:
    if principal.startswith("user:"):
        return "user", canonical_uuid(principal[5:]), None
    parts = principal.split("/")
    match parts:
        case ["team", team_id]:
            return "team", canonical_uuid(team_id), None
        case ["team-role", team_id, role] if role in TEAM_ROLES:
            return "team-role", canonical_uuid(team_id), role
    msg = "Unsupported policy principal."
    raise PolicyFormatError(msg)


def _object(obj: str) -> tuple[str, str]:
    resource_type, separator, identifier = obj.partition("/")
    if not separator or not (policy_actions(resource_type) or resource_type == "team"):
        msg = "Unsupported policy object."
        raise PolicyFormatError(msg)
    if identifier != "*" or resource_type == "team":
        canonical_uuid(identifier)
    return resource_type, identifier


def validate_rule(rule: Rule) -> None:
    """Reject malformed derived tuples; never load a partial or broadened policy."""
    if any(not isinstance(value, str) for value in rule[:3]):
        msg = "Invalid required derived rule field."
        raise PolicyFormatError(msg)
    if any(
        value is not None and (not isinstance(value, str) or not value or len(value) > _MAX_RULE_FIELD_LENGTH)
        for value in rule
    ):
        msg = "Invalid derived rule field."
        raise PolicyFormatError(msg)
    kind, principal_id, role = _principal(rule.v0)
    if rule.ptype == "g":
        target_kind, _, _ = _principal(rule.v1)
        if kind != "user" or target_kind not in {"team", "team-role"} or any(v is not None for v in rule[3:]):
            msg = "Only direct user-to-team or user-to-team-role grouping is permitted."
            raise PolicyFormatError(msg)
        return
    if rule.ptype != "p" or rule.v2 is None or rule.v3 is None or rule.v4 is not None or rule.v5 is not None:
        msg = "Invalid policy slot layout."
        raise PolicyFormatError(msg)
    validate_domain(rule.v1)
    resource_type, object_id = _object(rule.v2)
    if resource_type == "team" or kind == "team-role":
        if (
            kind != "team-role"
            or resource_type != "team"
            or principal_id != object_id
            or rule.v1 != "*"
            or rule.v3 not in TEAM_ACTIONS.get(role or "", frozenset())
        ):
            msg = "Team management policy must target its exact team and finite role actions."
            raise PolicyFormatError(msg)
    elif rule.v3 not in policy_actions(resource_type):
        msg = "Unsupported policy action."
        raise PolicyFormatError(msg)


def normalize_request(
    user_id: UUID, domain: str, obj: str, action: str, *, collection_operation: bool = False
) -> tuple[str, str, str, str]:
    """Normalize a server-classified request for the policy engine.

    This validates syntax only. It is not a resource resolver or an application
    authorization boundary; the caller must already have resolved canonical
    identity, scope, destination, and any credential ceiling.
    """
    subject = f"user:{canonical_uuid(str(user_id))}"
    validate_domain(domain)
    if not isinstance(obj, str):
        msg = "A canonical colon-form application object is required."
        raise PolicyFormatError(msg)
    resource_type, separator, identifier = obj.partition(":")
    if not separator:
        msg = "A canonical colon-form application object is required."
        raise PolicyFormatError(msg)
    normalized = f"{resource_type}/{identifier}"
    _object(normalized)
    actions = _TEAM_REQUEST_ACTIONS if resource_type == "team" else policy_actions(resource_type)
    if action not in actions or (resource_type == "team" and domain != "*"):
        msg = "Unsupported request action or team domain."
        raise PolicyFormatError(msg)
    if identifier == "*" and (
        not collection_operation
        or not (
            action == "create"
            or resource_type == "share"
            or (resource_type == "voice" and action == "read")
            or (resource_type == "variable" and action in {"read", "write", "delete"})
        )
    ):
        msg = "A collection request requires an existing server-classified collection operation."
        raise PolicyFormatError(msg)
    return subject, domain, normalized, action
