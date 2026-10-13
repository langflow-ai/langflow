"""The stable codes of the rules a flow graph follows, and who fixes each one.

Every rule has one code, shared by strict validation's 422, the engine's
errors and ``repair_flow_data``'s list of fixes. A violation is either
``auto``, with exactly one fix that ``repair_flow_data`` applies, or
``manual``: fixing it means choosing what the person meant, such as which of
two edges into an input that takes one connection stays, so the person fixes
it in the client.
"""

from __future__ import annotations

from enum import Enum


class GraphViolationCode(str, Enum):
    FLOW_DATA_NOT_OBJECT = "FLOW_DATA_NOT_OBJECT"
    COLLECTION_NOT_LIST = "COLLECTION_NOT_LIST"
    NODE_NOT_OBJECT = "NODE_NOT_OBJECT"
    EDGE_NOT_OBJECT = "EDGE_NOT_OBJECT"
    NODE_ID_MISSING = "NODE_ID_MISSING"
    NODE_ID_DUPLICATE = "NODE_ID_DUPLICATE"
    EDGE_ID_MISSING = "EDGE_ID_MISSING"
    EDGE_ID_DUPLICATE = "EDGE_ID_DUPLICATE"
    EDGE_ENDPOINT_INVALID = "EDGE_ENDPOINT_INVALID"
    NODE_DATA_NOT_OBJECT = "NODE_DATA_NOT_OBJECT"
    NON_FINITE_NUMBER = "NON_FINITE_NUMBER"
    TABLE_ROW_NOT_OBJECT = "TABLE_ROW_NOT_OBJECT"
    TABLE_ROW_ID_MISSING = "TABLE_ROW_ID_MISSING"
    TABLE_ROW_ID_DUPLICATE = "TABLE_ROW_ID_DUPLICATE"
    TABLE_ROW_POS_INVALID = "TABLE_ROW_POS_INVALID"
    # A handle has one of its two forms, and the other is valid.
    EDGE_HANDLE_FORM_MISSING = "EDGE_HANDLE_FORM_MISSING"
    # A handle is missing, is not an object, does not parse, or its forms disagree.
    EDGE_HANDLE_INVALID = "EDGE_HANDLE_INVALID"
    # A handle names an output or field its node does not have.
    EDGE_HANDLE_NOT_FOUND = "EDGE_HANDLE_NOT_FOUND"
    # A field that takes one connection, or a loop output, already has one.
    EDGE_TARGET_OCCUPIED = "EDGE_TARGET_OCCUPIED"
    # An edge has a note at one end.
    EDGE_TOUCHES_NOTE = "EDGE_TOUCHES_NOTE"


class Resolution(str, Enum):
    """How a violation is fixed: by ``repair_flow_data``, or by the person in the client."""

    AUTO = "auto"
    MANUAL = "manual"


MANUAL_CODES = frozenset(
    {
        GraphViolationCode.EDGE_HANDLE_INVALID,
        GraphViolationCode.EDGE_HANDLE_NOT_FOUND,
        GraphViolationCode.EDGE_TARGET_OCCUPIED,
    }
)


def resolution_of(code: GraphViolationCode) -> Resolution:
    return Resolution.MANUAL if code in MANUAL_CODES else Resolution.AUTO
