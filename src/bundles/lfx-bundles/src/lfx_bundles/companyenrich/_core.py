"""Ergonomic input mapping for the twelve core operations."""

from typing import Any

from lfx_bundles.companyenrich._validation import merge_filters


def core_arguments(operation: str, values: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Map explicit inputs to documented body/query fields without discarding filters."""
    query = {"expand": values["expand"]} if values.get("expand") is not None else {}
    if values.get("wait_for_enrichment") is not None:
        query["waitForEnrichment"] = values["wait_for_enrichment"]
    if operation == "get_companies_enrich":
        query["domain"] = values["domain"]
        return None, query
    if operation in {"get_companies", "get_people"}:
        query["id"] = values["company_id" if operation == "get_companies" else "person_id"]
        return None, query
    if operation == "get_companies_workforce":
        return None, {
            k: v for k, v in {"id": values.get("company_id"), "domain": values.get("domain")}.items() if v is not None
        }
    if operation == "post_companies_enrich":
        return values["properties"], query
    if operation == "post_companies_enrich_batch":
        return {"domains": values["domains"]}, query
    if operation == "post_people_lookup":
        return {"email": values["email"]}, query
    dedicated = {"semanticQuery": values.get("semantic_query"), "query": values.get("query")}
    if "similar" in operation:
        dedicated = {"domains": values.get("domains")}
    if operation == "post_people_search":
        dedicated = {}
    if not operation.endswith("_count"):
        dedicated.update(page=values.get("page", 1), pageSize=values.get("page_size", 5))
    return merge_filters(values.get("filters"), **dedicated), query
