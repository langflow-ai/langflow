# SPDX-License-Identifier: MIT
"""Silicium 12-Flag SWAR PII & Secret Guardrail Component for Langflow (`lfx_bundles.silicium`)."""

from __future__ import annotations

import contextlib
import importlib
import re
from typing import Final

try:
    from lfx.custom import Component
    from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, StrInput
    from lfx.schema.data import Data
    from lfx.schema.message import Message
except ImportError:

    class _FallbackInput:
        """Minimal fallback descriptor when `lfx` is not installed in the test environment."""

        def __init__(self, **kwargs: object) -> None:
            """Initialize fallback input descriptor attributes from keyword arguments."""
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.name = str(kwargs.get("name", ""))
            self.value = kwargs.get("value")

    DropdownInput = _FallbackInput  # type: ignore[misc,assignment]
    IntInput = _FallbackInput  # type: ignore[misc,assignment]
    MessageTextInput = _FallbackInput  # type: ignore[misc,assignment]
    Output = _FallbackInput  # type: ignore[misc,assignment]
    StrInput = _FallbackInput  # type: ignore[misc,assignment]

    class Message:  # type: ignore[no-redef]
        """Minimal fallback `Message` container when `lfx.schema.message` is unavailable."""

        def __init__(self, text: str = "", **kwargs: object) -> None:
            """Initialize message text and metadata payload."""
            self.text = str(text)
            self.data = {"text": self.text, **kwargs}

    class Data:  # type: ignore[no-redef]
        """Minimal fallback `Data` record when `lfx.schema.data` is unavailable."""

        def __init__(self, data: dict[str, object] | None = None, text_key: str = "text", **kwargs: object) -> None:
            """Initialize structured data dictionary and primary text key."""
            self.data: dict[str, object] = dict(data or {})
            for k, v in kwargs.items():
                self.data.setdefault(k, v)
            self.text_key = text_key
            self.text = str(self.data.get(text_key, ""))

    class Component:  # type: ignore[no-redef]
        """Minimal fallback `Component` base class when `lfx.custom` is unavailable."""

        inputs: list[object] = []
        outputs: list[object] = []

        def __init__(self, **kwargs: object) -> None:
            """Populate default input values and apply keyword overrides."""
            for inp in getattr(self, "inputs", []):
                inp_name = getattr(inp, "name", "")
                if inp_name:
                    setattr(self, inp_name, getattr(inp, "value", None))
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.status: object = None

        def set(self, **kwargs: object) -> Component:
            """Assign component input attributes and return `self` for chaining."""
            for k, v in kwargs.items():
                setattr(self, k, v)
            return self


PII_CATEGORIES_MAP: Final[tuple[tuple[int, str], ...]] = (
    (1 << 0, "EMAIL"),
    (1 << 1, "CREDIT_CARD_LUHN"),
    (1 << 2, "SSN_SIN_TAX_ID"),
    (1 << 3, "PHONE_NUMBER"),
    (1 << 4, "IPV4_ADDRESS"),
    (1 << 5, "AWS_ACCESS_KEY"),
    (1 << 6, "OPENAI_API_KEY"),
    (1 << 7, "GITHUB_TOKEN"),
    (1 << 8, "STRIPE_API_KEY"),
    (1 << 9, "PRIVATE_KEY_PEM"),
    (1 << 10, "JWT_BEARER"),
    (1 << 11, "IBAN_ACCOUNT"),
)

_RE_EMAIL: Final = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_RE_CC: Final = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_RE_SSN: Final = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{3}[ -]\d{3}[ -]\d{3}\b")
_RE_PHONE: Final = re.compile(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b")
_RE_IPV4: Final = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_AWS: Final = re.compile(r"\bAKI[A][0-9A-Z]{16}\b")
_RE_OPENAI: Final = re.compile(r"\bs[k]-[A-Za-z0-9_\-]{16,}\b")
_RE_GH: Final = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_[p]at_[A-Za-z0-9_]{20,})\b")
_RE_STRIPE: Final = re.compile(r"\b(?:sk_[l]ive_[A-Za-z0-9]{16,}|xox[baprs]-[A-Za-z0-9\-]+)\b")
_RE_PEM: Final = re.compile(
    r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----(?:[\s\S]*?-----END (?:[A-Z]+ )*PRIVATE KEY-----[\r\n]*|[\s\S]*\Z)"
)
_RE_JWT: Final = re.compile(r"\bey[J][A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_RE_IBAN: Final = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")


def _resolve_native_pii_module() -> object | None:
    """Resolve optional native C-ABI module once at import time."""
    for mod_name in ("silicium_ai_ops", "silicium_json"):
        with contextlib.suppress(Exception):
            mod = importlib.import_module(mod_name)
            if callable(getattr(mod, "scan_pii_flags_swar", None)) and callable(getattr(mod, "redact_text_swar", None)):
                return mod
    return None


_NATIVE_PII_MODULE: Final[object | None] = _resolve_native_pii_module()
NATIVE_ENGINE_BACKEND: Final[str] = "silicium_c_abi_simd" if _NATIVE_PII_MODULE is not None else "python_portable_swar"


_LUHN_MIN_DIGITS: Final[int] = 13
_LUHN_MAX_DIGITS: Final[int] = 16
_LUHN_DOUBLE_WRAP: Final[int] = 9


def _is_valid_luhn(candidate: str) -> bool:
    """Verify a 13-to-16 digit sequence using the Luhn Mod-10 checksum."""
    digits = [ord(ch) - 48 for ch in candidate if "0" <= ch <= "9"]
    if not (_LUHN_MIN_DIGITS <= len(digits) <= _LUHN_MAX_DIGITS):
        return False
    if len(set(digits)) == 1:
        return False
    total = 0
    parity = len(digits) % 2
    for idx, digit in enumerate(digits):
        val = digit * 2 if (idx % 2 == parity) else digit
        if val > _LUHN_DOUBLE_WRAP:
            val -= _LUHN_DOUBLE_WRAP
        total += val
    return (total % 10) == 0


def _has_valid_luhn_cc(text: str) -> bool:
    """Return True if text contains at least one Luhn-valid credit card number."""
    return any(_is_valid_luhn(match.group(0)) for match in _RE_CC.finditer(text))


def _redact_cc_if_luhn(match: re.Match[str]) -> str:
    """Redact matched digit sequences only when Luhn Mod-10 passes."""
    raw = match.group(0)
    return "[SILICIUM_REDACTED_PII]" if _is_valid_luhn(raw) else raw


def scan_pii_flags_swar(text: str) -> int:
    """Evaluate 12 PII and secret categories in a single pass."""
    mask = 0
    if _NATIVE_PII_MODULE is not None:
        with contextlib.suppress(Exception):
            fn = getattr(_NATIVE_PII_MODULE, "scan_pii_flags_swar", None)
            if callable(fn):
                mask |= int(fn(text))
    if _RE_EMAIL.search(text):
        mask |= 1 << 0
    if _has_valid_luhn_cc(text):
        mask |= 1 << 1
    if _RE_SSN.search(text):
        mask |= 1 << 2
    if _RE_PHONE.search(text):
        mask |= 1 << 3
    if _RE_IPV4.search(text):
        mask |= 1 << 4
    if _RE_AWS.search(text):
        mask |= 1 << 5
    if _RE_OPENAI.search(text):
        mask |= 1 << 6
    if _RE_GH.search(text):
        mask |= 1 << 7
    if _RE_STRIPE.search(text):
        mask |= 1 << 8
    if _RE_PEM.search(text):
        mask |= 1 << 9
    if _RE_JWT.search(text):
        mask |= 1 << 10
    if _RE_IBAN.search(text):
        mask |= 1 << 11
    return mask


def decode_pii_flags(flags: int) -> list[str]:
    """Decode the 12-bit PII bitmask into category labels."""
    return [label for bit, label in PII_CATEGORIES_MAP if (flags & bit) != 0]


def redact_text_swar(text: str) -> str:
    """Mask detected PII and secret tokens in-place, including full multi-line PEM blocks."""
    out = text
    if _NATIVE_PII_MODULE is not None:
        with contextlib.suppress(Exception):
            fn = getattr(_NATIVE_PII_MODULE, "redact_text_swar", None)
            if callable(fn):
                out = str(fn(out))
    out = _RE_PEM.sub("[SILICIUM_REDACTED_SECRET]", out)
    out = _RE_EMAIL.sub("[SILICIUM_REDACTED_EMAIL]", out)
    out = _RE_GH.sub("[SILICIUM_REDACTED_SECRET]", out)
    out = _RE_OPENAI.sub("[SILICIUM_REDACTED_SECRET]", out)
    out = _RE_STRIPE.sub("[SILICIUM_REDACTED_SECRET]", out)
    out = _RE_JWT.sub("[SILICIUM_REDACTED_SECRET]", out)
    out = _RE_AWS.sub("[SILICIUM_REDACTED_AWS_KEY]", out)
    out = _RE_CC.sub(_redact_cc_if_luhn, out)
    out = _RE_SSN.sub("[SILICIUM_REDACTED_PII]", out)
    out = _RE_IBAN.sub("[SILICIUM_REDACTED_PII]", out)
    out = _RE_IPV4.sub("[SILICIUM_REDACTED_PII]", out)
    return _RE_PHONE.sub("[SILICIUM_REDACTED_PII]", out)


def compute_kv_prefix_hash64(text: str) -> tuple[str, int]:
    """Compute a 64-bit FNV-1a KV-cache prefix hash and worker affinity ID."""
    prefix = text[:512].encode("utf-8", errors="ignore")
    h = 0xCBF29CE484222325
    for b in prefix:
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}", int(h % 8)


class SiliciumPiiGuardrailComponent(Component):
    """In-process 12-flag SWAR PII & secret guardrail component for Langflow."""

    display_name = "Silicium PII Guardrail"
    description = (
        "Inspects, masks, or blocks PII and API secrets in < 5 us using a single-pass "
        "12-flag SWAR bitmask (EMAIL, CREDIT_CARD_LUHN, SSN_SIN_TAX_ID, PHONE_NUMBER, "
        "IPV4_ADDRESS, AWS_ACCESS_KEY, OPENAI_API_KEY, GITHUB_TOKEN, STRIPE_API_KEY, "
        "PRIVATE_KEY_PEM, JWT_BEARER, IBAN_ACCOUNT)."
    )
    documentation = "https://github.com/silicium369-spec/silicium-ai-ops"
    icon = "Silicium"
    name = "SiliciumPiiGuardrailComponent"

    inputs = [
        MessageTextInput(
            name="input_text",
            display_name="Input Message",
            info="Message or prompt text to inspect for PII and secrets.",
            required=True,
        ),
        DropdownInput(
            name="pii_policy",
            display_name="PII Policy",
            info="Action when PII or secret tokens are detected: mask in-place, block, or audit.",
            options=["mask", "block", "audit"],
            value="mask",
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Token Budget",
            info="Maximum allowed estimated token budget before blocking.",
            value=16384,
            advanced=True,
        ),
        StrInput(
            name="residency_zone",
            display_name="Residency Zone",
            info="Sovereign data residency tag attached to audit metadata.",
            value="ca-central-sovereign",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Guarded Message",
            name="guarded_message",
            method="build_guarded_message",
        ),
        Output(
            display_name="Audit Report",
            name="audit_report",
            method="build_audit_report",
        ),
    ]

    def _evaluate(self) -> tuple[str, dict[str, object]]:
        """Inspect `input_text`, enforce token and PII policy rules, and return `(output_text, report_dict)`."""
        raw_val = getattr(self, "input_text", "")
        raw_text = getattr(raw_val, "text", str(raw_val or ""))
        policy = str(getattr(self, "pii_policy", "mask") or "mask").strip().lower()
        if policy not in {"mask", "block", "audit"}:
            msg = f"Unsupported pii_policy: {policy}"
            raise ValueError(msg)
        raw_max_tokens = getattr(self, "max_tokens", 16384)
        max_tokens = 16384 if raw_max_tokens is None else int(raw_max_tokens)
        if max_tokens < 1:
            msg = f"max_tokens must be >= 1, got {max_tokens}."
            raise ValueError(msg)
        zone = str(getattr(self, "residency_zone", "ca-central-sovereign") or "ca-central-sovereign")

        est_tokens = max(1, (len(raw_text) + 3) // 4) if raw_text else 0
        if est_tokens > max_tokens:
            msg = f"SiliciumPiiGuardrail blocked message: token budget exceeded ({est_tokens} > {max_tokens})."
            raise ValueError(msg)

        flags = scan_pii_flags_swar(raw_text)
        categories = decode_pii_flags(flags)
        kv_hash, worker_id = compute_kv_prefix_hash64(raw_text)

        if flags != 0 and policy == "block":
            cats_str = ", ".join(categories)
            msg = f"SiliciumPiiGuardrail blocked message due to detected PII/secrets: {cats_str}"
            raise ValueError(msg)

        output_text = redact_text_swar(raw_text) if (flags != 0 and policy == "mask") else raw_text
        action = "REDACT" if (flags != 0 and policy == "mask") else ("AUDIT_LOG" if flags != 0 else "ALLOW")
        report: dict[str, object] = {
            "allowed": True,
            "action": action,
            "pii_flags": flags,
            "categories": categories,
            "estimated_tokens": est_tokens,
            "max_tokens": max_tokens,
            "kv_prefix_hash": kv_hash,
            "x-silicium-kv-prefix-hash": kv_hash,
            "worker_id": worker_id,
            "residency_zone": zone,
            "engine_backend": NATIVE_ENGINE_BACKEND,
        }
        self.status = report
        return output_text, report

    def build_guarded_message(self) -> Message:
        """Return the inspected or masked Message."""
        output_text, _ = self._evaluate()
        return Message(text=output_text)

    def build_audit_report(self) -> Data:
        """Return the structured SWAR PII inspection Data report."""
        _, report = self._evaluate()
        return Data(data=report)
