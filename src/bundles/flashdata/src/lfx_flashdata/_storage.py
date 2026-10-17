"""Customer storage validation. Never include credentials in errors."""

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from jsonschema import Draft7Validator

from lfx_flashdata._client import FlashDataError

MAX_PREFIX_LENGTH = 512
MAX_SAS_LENGTH = 4096

STORAGE_SCHEMA = json.loads(Path(__file__).with_name("storage.schema.json").read_text())


def storage_config(raw: str) -> dict[str, Any]:
    try:
        storage = json.loads(raw)
    except (ValueError, TypeError):
        msg = "Download storage must contain a JSON object."
        raise FlashDataError(msg) from None
    if not isinstance(storage, dict) or not Draft7Validator(STORAGE_SCHEMA).is_valid(storage):
        msg = "Invalid download storage credential. Check its fields and types."
        raise FlashDataError(msg)
    kind = storage["storage_type"]
    bucket = storage["storage_url"].strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket) or ".." in bucket:
        msg = "storage_url must be a bucket/container name; put folders in object_prefix."
        raise FlashDataError(msg)
    if kind == "s3" and (re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", bucket) or ".-" in bucket or "-." in bucket):
        msg = "storage_url must be a valid AWS S3 bucket name."
        raise FlashDataError(msg)
    storage["storage_url"] = bucket
    provider_fields = (
        ["service_account"]
        if kind == "gcs"
        else ["account_name", "sas_token"]
        if kind == "azure"
        else ["access_key", "secret_key", "region"]
        if kind == "cos"
        else ["access_key", "secret_key", "region", "endpoint_url"]
    )
    if set(storage) - {
        "storage_type",
        "storage_url",
        "object_prefix",
        *provider_fields,
    }:
        msg = "The storage credential contains fields for a different provider."
        raise FlashDataError(msg)
    if "object_prefix" in storage:
        prefix = storage["object_prefix"].strip().removesuffix("/")
        if (
            not prefix
            or len(prefix) > MAX_PREFIX_LENGTH
            or any(part in (".", "..") or not re.fullmatch(r"[A-Za-z0-9._-]+", part) for part in prefix.split("/"))
        ):
            msg = "object_prefix must use safe folder names, up to 512 characters."
            raise FlashDataError(msg)
        storage["object_prefix"] = prefix
    if kind == "gcs":
        account = storage.get("service_account", {})
        if (
            not all(account.get(k) for k in ("project_id", "client_email", "private_key"))
            or not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.gserviceaccount\.com",
                account.get("client_email", ""),
            )
            or "BEGIN PRIVATE KEY" not in account.get("private_key", "")
        ):
            msg = "GCS requires project_id, service-account client_email and a PEM private_key."
            raise FlashDataError(msg)
        storage["service_account"] = {key: account[key] for key in ("project_id", "client_email", "private_key")}
    elif kind == "azure":
        sas = storage.get("sas_token", "").removeprefix("?")
        fields = parse_qs(sas)
        if (
            not storage.get("account_name")
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", bucket)
            or not all(fields.get(k) for k in ("sig", "se", "sv"))
            or "w" not in fields.get("sp", [""])[0]
            or fields.get("sr") != ["c"]
            or "\n" in sas
            or "\r" in sas
            or len(sas) > MAX_SAS_LENGTH
        ):
            msg = "Azure requires an account name and container SAS with write permission and expiry."
            raise FlashDataError(msg)
        storage["sas_token"] = sas
    else:
        if not all(storage.get(k, "").strip() for k in ("access_key", "secret_key")):
            msg = "Download storage requires access_key and secret_key in the provider credential."
            raise FlashDataError(msg)
        if kind == "s3_compatible" and not storage.get("endpoint_url"):
            msg = "S3-compatible storage requires endpoint_url."
            raise FlashDataError(msg)
        region = storage.get("region", "")
        if (
            (kind in ("cos", "bos", "tos") and "." in bucket)
            or (kind == "cos" and (not re.fullmatch(r"ap-[a-z0-9-]+", region) or not re.search(r"-\d{5,}$", bucket)))
            or (kind == "bos" and region not in ("bj", "su", "hkg"))
            or (kind == "tos" and not re.fullmatch(r"(?:cn|ap|eu|us)-[a-z0-9-]+", region))
        ):
            msg = "Check the storage provider region and bucket name."
            raise FlashDataError(msg)
    return storage
