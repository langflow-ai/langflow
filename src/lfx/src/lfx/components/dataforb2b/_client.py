"""Shared API client + filter helpers for the DataForB2B Langflow bundle.

DataForB2B is a B2B data API (https://api.dataforb2b.ai) for searching and
enriching companies and professional (LinkedIn) profiles. Auth is an API-key
header ``api_key``; get a key at https://app.dataforb2b.ai.

This module keeps the bundle in parity with the Dify / AutoGPT integrations:
the same six endpoints and the same ``{op, conditions:[{column,type,value}]}``
filter shape.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

import httpx

API_URL = "https://api.dataforb2b.ai"
TIMEOUT = 60.0


class DataForB2BClient:
    """Thin synchronous client for the DataForB2B API."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"api_key": self.api_key, "Content-Type": "application/json"}

    def _post(self, path: str, payload: dict[str, Any]) -> dict:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(f"{API_URL}{path}", headers=self._headers(), json=payload)
            resp.raise_for_status()
            return resp.json()

    def _get(self, path: str, params: dict[str, Any]) -> dict:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(f"{API_URL}{path}", headers=self._headers(), params=params)
            resp.raise_for_status()
            return resp.json()

    # --- Search -----------------------------------------------------------

    def search_people(self, payload: dict[str, Any]) -> dict:
        """POST /search/people — find professional profiles / leads by filters."""
        return self._post("/search/people", payload)

    def search_companies(self, payload: dict[str, Any]) -> dict:
        """POST /search/companies — find companies / accounts by filters."""
        return self._post("/search/companies", payload)

    def reasoning_search(self, payload: dict[str, Any]) -> dict:
        """POST /search/reasoning — natural-language (ICP) search.

        May return ``status == "needs_input"`` with clarifying questions; in
        that case re-call with ``session_id`` + ``answers``.
        """
        return self._post("/search/reasoning", payload)

    def typeahead(self, type_: str, q: str, limit: int = 20) -> dict:
        """GET /typeahead — resolve the exact stored value for a free-text filter."""
        return self._get("/typeahead", {"type": type_, "q": q, "limit": limit})

    def enrich_profile(self, payload: dict[str, Any]) -> dict:
        """POST /enrich/profile — enrich a profile; >=1 enrich_* flag required."""
        return self._post("/enrich/profile", payload)

    def enrich_company(self, company_identifier: str) -> dict:
        """POST /enrich/company — enrich a company by domain / name / LinkedIn URL."""
        return self._post("/enrich/company", {"company_identifier": company_identifier})


# --- Filter columns / operators (source of truth: the Dify integration) ----

OPERATORS = ["=", "!=", "like", "not_like", "in", "not_in", ">", ">=", "<", "<=", "between"]

PEOPLE_COLUMNS = [
    # Profile
    "first_name",
    "last_name",
    "profile_location",
    "profile_country",
    "profile_industry",
    "follower_count",
    "keyword",
    # Current job
    "current_company",
    "current_title",
    "current_job_location",
    "current_company_industry",
    "current_company_category",
    "current_company_size",
    "current_company_id",
    "current_employment_type",
    "years_in_current_position",
    "years_at_current_company",
    "current_company_has_funding",
    "current_company_funding_stage",
    "current_company_investor",
    # Past jobs
    "past_company",
    "past_title",
    "past_job_location",
    "past_company_industry",
    "past_company_size",
    "past_company_id",
    "past_employment_type",
    "years_at_past_company",
    # Skills / education / languages / certifications / experience
    "skill",
    "school",
    "degree",
    "degree_level",
    "field_of_study",
    "language",
    "language_iso",
    "language_proficiency",
    "certification",
    "certification_authority",
    "years_of_experience",
    "num_total_jobs",
    "is_currently_employed",
]

COMPANY_COLUMNS = [
    # Basic
    "name",
    "tagline",
    "description",
    "domain",
    "universal_name",
    "keyword",
    "industry",
    # Size
    "employee_count",
    # HQ / offices
    "country_iso_code",
    "city",
    "region",
    "office_country",
    "office_city",
    "office_region",
    # Growth
    "employee_growth_1m",
    "employee_growth_6m",
    "employee_growth_12m",
    "recent_hires_count",
    # Metadata
    "founded_year",
    "company_type",
    "follower_count",
    "page_verified",
    "category",
    # Funding
    "last_funding_amount_usd",
    "last_funding_date",
    "funding_stage_normalized",
    "has_funding",
]

TYPEAHEAD_TYPES = [
    "company",
    "industry",
    "title",
    "skill",
    "school",
    "investor",
    "location",
    "category",
]


# --- Filter building (ported from the AutoGPT / Dify integrations) ----------


def _to_str(x: Any) -> str:
    if isinstance(x, Enum):
        return str(x.value)
    return str(x)


def coerce_scalar(value: Any) -> Any:
    """Coerce a filter value string into bool/number when it clearly is one."""
    if isinstance(value, (int, float, bool)):
        return value
    s = str(value).strip()
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        f = float(s)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return s


def build_slot_condition(column: Any, operator: Any, raw: Any) -> dict | None:
    """Build one filter condition from a (column, operator, value) slot.

    Returns None when the slot is empty.
    - ``in`` / ``not_in`` -> value is a comma-separated list
    - ``between``         -> value is "min,max"
    - ``like`` / ``not_like`` -> raw string kept as-is (text pattern)
    - others              -> single value, coerced to bool/number when applicable
    """
    if not column or raw is None or str(raw).strip() == "":
        return None
    column = _to_str(column)
    op = (_to_str(operator).strip() if operator else "=") or "="

    if op in ("in", "not_in"):
        items = [x.strip() for x in str(raw).split(",") if x.strip()]
        if not items:
            return None
        return {"column": column, "type": op, "value": [coerce_scalar(x) for x in items]}

    if op == "between":
        parts = [x.strip() for x in str(raw).split(",") if x.strip()]
        if len(parts) < 2:
            msg = f"Operator 'between' on '{column}' needs two comma-separated values, e.g. 3,7"
            raise ValueError(msg)
        return {
            "column": column,
            "type": "between",
            "value": coerce_scalar(parts[0]),
            "value2": coerce_scalar(parts[1]),
        }

    if op in ("like", "not_like"):
        return {"column": column, "type": op, "value": str(raw)}

    return {"column": column, "type": op, "value": coerce_scalar(raw)}


def finalize_filters(conditions: list, match: Any, advanced: Any) -> dict | None:
    """Combine slot conditions (with AND/OR) and optional advanced JSON filters."""
    op = str(match).strip().lower() if match else "and"
    if op not in ("and", "or"):
        op = "and"

    group = {"op": op, "conditions": conditions} if conditions else None

    if advanced:
        if isinstance(advanced, dict) and "conditions" in advanced:
            adv = advanced
        elif isinstance(advanced, list):
            adv = {"op": "and", "conditions": advanced}
        else:  # a single bare condition dict
            adv = {"op": "and", "conditions": [advanced]}
        return {"op": "and", "conditions": [group, adv]} if group else adv

    return group


def parse_json_filters(raw: Any) -> Any:
    """Accept a dict/list as-is, or parse a JSON string. Empty -> None."""
    if not raw:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except (TypeError, ValueError) as exc:
        msg = f"Advanced filters JSON is not valid JSON: {exc}"
        raise ValueError(msg) from exc


def build_filters(slots: list, match: Any, filters_json_raw: Any) -> dict:
    """Build the search ``filters`` object from (column, operator, value) slots
    and/or a raw advanced-JSON filter. Raises if nothing was provided.
    """
    conditions: list[dict] = []
    for column, operator, value in slots:
        cond = build_slot_condition(column, operator, value)
        if cond:
            conditions.append(cond)

    advanced = parse_json_filters(filters_json_raw)
    filters = finalize_filters(conditions, match, advanced)
    if not filters:
        msg = "Provide at least one filter slot (column + value) or advanced filters JSON."
        raise ValueError(msg)
    return filters
