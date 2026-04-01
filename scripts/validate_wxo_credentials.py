r"""Validate a Watsonx Orchestrate instance URL + API key.

Requires optional deps: uv sync --package langflow-base --extra ibm-watsonx

Steps (default):
  1) Exchange API key for a bearer token (IBM IAM for ``*.cloud.ibm.com``, MCSP for ``*.ibm.com``).
  2) Call the instance API (``GET .../v1/orchestrate/agents``) to confirm the token works for that URL.

**dev-wa (and similar AWS / MCSP dev stacks):** production MCSP token URLs often return 404. If the
hostname contains ``dev-wa``, this script defaults to the **MCSP test** token host unless you set
``WXO_MCSP_TOKEN_BASE_URL`` or ``--mcsp-base-url``. Use ``--dev-wa`` to force that default even when
the hostname does not match.

If you see **TLS/SSL handshake errors** to ``iam.platform.test...``, that is a network or trust issue
(VPN, firewall, proxy, or Python/OpenSSL), not a wrong API key. Try another network, update CA certs,
or set ``--mcsp-base-url`` to the host your team documents.

Examples:
  uv run python scripts/validate_wxo_credentials.py \
    --url 'https://api.dev-wa.watson-orchestrate.ibm.com/instances/YOUR_ID' \
    --api-key 'YOUR_KEY'

  uv run python scripts/validate_wxo_credentials.py --no-probe --url '...' --api-key '...'

  WXO_INSTANCE_URL='...' WXO_API_KEY='...' uv run python scripts/validate_wxo_credentials.py
"""

from __future__ import annotations

import argparse
import os
import ssl
import sys
from typing import Literal
from urllib.parse import urlparse

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import WxOAuthURL

# Public MCSP test token *base* (SDK appends /siusermgr/...). Not a secret; override via env/CLI if needed.
_MCSP_TEST_TOKEN_BASE_DEFAULT = "https://iam.platform.test.saas.ibm.com"  # noqa: S105


def _hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _looks_like_dev_wa_host(url: str) -> bool:
    return "dev-wa" in _hostname(url)


def _ibm_iam_base(cli: str | None) -> str:
    raw = (
        cli
        or os.environ.get("WXO_IBM_IAM_TOKEN_BASE_URL")
        or os.environ.get("LANGFLOW_WXO_IBM_IAM_TOKEN_BASE_URL")
        or ""
    ).strip()
    return raw.rstrip("/") if raw else WxOAuthURL.IBM_IAM.value


def _mcsp_base(cli: str | None, *, instance_url: str, force_dev_wa: bool) -> tuple[str, str]:
    """Return (base_url, note) where note explains defaulting."""
    raw = (
        cli or os.environ.get("WXO_MCSP_TOKEN_BASE_URL") or os.environ.get("LANGFLOW_WXO_MCSP_TOKEN_BASE_URL") or ""
    ).strip()
    if raw:
        return raw.rstrip("/"), "from env or --mcsp-base-url"
    if force_dev_wa or _looks_like_dev_wa_host(instance_url):
        return _MCSP_TEST_TOKEN_BASE_DEFAULT, "dev-wa style host: using MCSP test token base (override if wrong)"
    return WxOAuthURL.MCSP.value, "production MCSP token base"


def get_authenticator_for_url(instance_url: str, api_key: str, *, iam_base: str, mcsp_base: str):
    """Match langflow Watsonx adapter: IAM for cloud.ibm.com, MCSP for *.ibm.com."""
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator, MCSPAuthenticator

    if ".cloud.ibm.com" in instance_url:
        return IAMAuthenticator(apikey=api_key, url=iam_base)
    if ".ibm.com" in instance_url:
        return MCSPAuthenticator(apikey=api_key, url=mcsp_base)
    msg = f"Could not determine authentication scheme for instance URL: {instance_url}"
    raise ValueError(msg)


def authenticator_iam(api_key: str, *, iam_base: str):
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

    return IAMAuthenticator(apikey=api_key, url=iam_base)


def authenticator_mcsp(api_key: str, *, mcsp_base: str):
    from ibm_cloud_sdk_core.authenticators import MCSPAuthenticator

    return MCSPAuthenticator(apikey=api_key, url=mcsp_base)


def _is_ssl_or_tls_error(exc: BaseException) -> bool:
    e: BaseException | None = exc
    while e is not None:
        if isinstance(e, ssl.SSLError):
            return True
        e = e.__cause__ or e.__context__
    text = str(exc).lower()
    return "ssl" in text and ("handshake" in text or "tls" in text or "certificate" in text)


def _format_token_error(exc: BaseException) -> str:
    status = getattr(exc, "status_code", None)
    if status is not None:
        return f"token request failed (HTTP {status})"
    if _is_ssl_or_tls_error(exc):
        return "".join(
            [
                "TLS/SSL error before any HTTP response (not an API-key rejection).\n",
                f"  detail: {exc}\n",
                "  hint: VPN/firewall/proxy, corporate TLS inspection, or unreachable IBM endpoints. ",
                "Try another network, update certifi/OpenSSL, or set --mcsp-base-url per your runbook.",
            ]
        )
    return f"token request failed: {exc}"


def try_get_token(auth) -> tuple[bool, str]:
    """Return (success, message). Never includes token material."""
    try:
        auth.token_manager.get_token()
    except Exception as exc:  # noqa: BLE001
        return False, _format_token_error(exc)
    return True, "ok: obtained bearer token (not printed)"


def probe_instance_api(instance_url: str, auth) -> tuple[bool, str]:
    """Verify token against the WXO HTTP API (same path Langflow uses for listing agents)."""
    try:
        from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
        from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient
    except ImportError as exc:
        return False, f"cannot import WXO client (install ibm-watsonx extra): {exc}"

    try:
        client = WxOClient(instance_url=instance_url.rstrip("/"), authenticator=auth)
        client.get_agents_raw(params=None)
    except ClientAPIException as exc:
        code = getattr(exc.response, "status_code", None)
        if code is not None:
            return False, f"instance API rejected request (HTTP {code})"
        return False, f"instance API error: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"instance API error: {exc}"
    return True, "ok: instance API accepted the token (agents request succeeded)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.environ.get("WXO_INSTANCE_URL", ""),
        help="Instance base URL (or set WXO_INSTANCE_URL)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("WXO_API_KEY", ""),
        help="API key (or set WXO_API_KEY)",
    )
    parser.add_argument(
        "--ibm-iam-base-url",
        default=None,
        help="Override IBM Cloud IAM token base URL (or WXO_IBM_IAM_TOKEN_BASE_URL)",
    )
    parser.add_argument(
        "--mcsp-base-url",
        default=None,
        help="Override MCSP token base URL (or WXO_MCSP_TOKEN_BASE_URL)",
    )
    parser.add_argument(
        "--dev-wa",
        action="store_true",
        help="Force MCSP *test* token base (when not using --mcsp-base-url / env)",
    )
    parser.add_argument(
        "--auth",
        choices=("auto", "iam", "mcsp"),
        default="auto",
        help="auto: from URL like Langflow; iam/mcsp: force that token endpoint only",
    )
    parser.add_argument(
        "--try-all",
        action="store_true",
        help="Try both IBM IAM and MCSP with the same API key (diagnostic; no instance probe)",
    )
    parser.add_argument(
        "--probe",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="After a successful token exchange, call the instance agents API (default: true)",
    )
    args = parser.parse_args()

    url = (args.url or "").strip()
    api_key = (args.api_key or "").strip()
    if not url or not api_key:
        print(
            "error: provide both --url and --api-key (or WXO_INSTANCE_URL and WXO_API_KEY)",
            file=sys.stderr,
        )
        return 2

    iam_base = _ibm_iam_base(args.ibm_iam_base_url)
    mcsp_base, mcsp_note = _mcsp_base(args.mcsp_base_url, instance_url=url, force_dev_wa=args.dev_wa)

    print(f"instance_url: {url}")
    print(f"ibm_iam_token_base: {iam_base}")
    print(f"mcsp_token_base: {mcsp_base} ({mcsp_note})")

    if args.try_all:
        print("\n(try-all: testing the same API key against IAM and MCSP; instance host is not sent to token URLs)\n")
        print(f"--- IBM IAM ({iam_base}) ---")
        ok_iam, msg_iam = try_get_token(authenticator_iam(api_key, iam_base=iam_base))
        print(msg_iam if ok_iam else f"error: {msg_iam}", file=sys.stdout if ok_iam else sys.stderr)
        print(f"--- MCSP ({mcsp_base}) ---")
        ok_mcsp, msg_mcsp = try_get_token(authenticator_mcsp(api_key, mcsp_base=mcsp_base))
        print(msg_mcsp if ok_mcsp else f"error: {msg_mcsp}", file=sys.stdout if ok_mcsp else sys.stderr)
        if ok_iam or ok_mcsp:
            print("\nsummary: at least one token exchange succeeded (key is valid for that identity system).")
        else:
            print("\nsummary: both IAM and MCSP token exchange failed for this key.", file=sys.stderr)
        return 0 if (ok_iam or ok_mcsp) else 1

    auth_mode: Literal["auto", "iam", "mcsp"] = args.auth
    if auth_mode == "iam":
        print(f"auth scheme: IBM IAM ({iam_base}) [forced]")
        auth = authenticator_iam(api_key, iam_base=iam_base)
    elif auth_mode == "mcsp":
        print(f"auth scheme: MCSP ({mcsp_base}) [forced]")
        auth = authenticator_mcsp(api_key, mcsp_base=mcsp_base)
    else:
        try:
            auth = get_authenticator_for_url(instance_url=url, api_key=api_key, iam_base=iam_base, mcsp_base=mcsp_base)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        scheme = f"IBM IAM ({iam_base})" if ".cloud.ibm.com" in url else f"MCSP ({mcsp_base})"
        print(f"auth scheme: {scheme} [from URL]")

    try:
        auth.validate()
    except ValueError as exc:
        print(f"error: authenticator validation failed: {exc}", file=sys.stderr)
        return 1

    ok, msg = try_get_token(auth)
    if not ok:
        print(f"error: {msg}", file=sys.stderr)
        return 1
    print(msg)

    if args.probe:
        print("\n--- instance API ---")
        ok_api, msg_api = probe_instance_api(url, auth)
        if not ok_api:
            print(f"error: {msg_api}", file=sys.stderr)
            return 1
        print(msg_api)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
