from __future__ import annotations

import re
import time
import uuid
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, FloatInput, IntInput, MultiselectInput, StrInput
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

# Deterministic PII patterns — no LLM, no external service
PII_PATTERNS: dict[str, re.Pattern] = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{13,19}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "api_key": re.compile(
        r"\b(?:sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xox[bpras]-[A-Za-z0-9-]{10,})\b"
        r"|"
        r"\b[Aa][Pp][Ii][-_]?[Kk][Ee][Yy]\s*[:=]\s*[A-Za-z0-9_\-]{16,}\b"
    ),
}

# Prompt injection heuristics — deterministic keyword/pattern match
INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+your\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
    re.compile(r"do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"reveal\s+your\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"disregard\s+.*instructions", re.IGNORECASE),
]


def _detect_pii(text: str, categories: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for cat in categories:
        pattern = PII_PATTERNS.get(cat)
        if pattern is None:
            continue
        findings.extend(
            {"category": cat, "match": m.group(), "start": m.start(), "end": m.end()} for m in pattern.finditer(text)
        )
    return findings


def _redact_pii(text: str, findings: list[dict[str, Any]]) -> str:
    result = text
    for f in sorted(findings, key=lambda x: x["start"], reverse=True):
        cat = f["category"]
        result = result[: f["start"]] + f"[REDACTED:{cat}]" + result[f["end"] :]
    return result


def _detect_injection(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pat in INJECTION_PATTERNS:
        findings.extend(
            {"category": "prompt_injection", "match": m.group(), "start": m.start(), "end": m.end()}
            for m in pat.finditer(text)
        )
    return findings


class GovernanceComponent(Component):
    display_name = "Governance"
    description = (
        "Deterministic policy enforcement: PII scanning, tool authorization, "
        "cost/iteration budgets, and prompt injection defense. Emits a structured audit record."
    )
    documentation: str = "https://docs.langflow.org/components/governance"
    icon = "shield-check"
    name = "Governance"

    inputs = [
        MessageTextInput(
            name="text",
            display_name="Text",
            info="Content to evaluate (passthrough if allowed).",
            tool_mode=True,
        ),
        StrInput(
            name="tool_name",
            display_name="Tool Name",
            info="Tool being called (for allowlist authorization). Leave empty if not a tool call.",
            advanced=True,
        ),
        DropdownInput(
            name="mode",
            display_name="Mode",
            options=["OBSERVE", "MONITOR", "ENFORCE"],
            value="ENFORCE",
            info="OBSERVE: log only. MONITOR: flag but passthrough. ENFORCE: block on violation.",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="pii_action",
            display_name="PII Action",
            options=["detect", "redact", "block"],
            value="block",
            info="How to handle detected PII.",
        ),
        MultiselectInput(
            name="pii_categories",
            display_name="PII Categories",
            options=["ssn", "credit_card", "email", "phone", "api_key"],
            value=["ssn", "credit_card", "email", "phone", "api_key"],
            info="Which PII categories to scan.",
        ),
        StrInput(
            name="tool_allowlist",
            display_name="Tool Allowlist",
            info="Comma-separated allowed tool names. Empty = allow all.",
            value="",
            advanced=True,
        ),
        FloatInput(
            name="cost_budget",
            display_name="Cost Budget (USD)",
            info="Max spend per session. 0 = no budget enforcement.",
            value=0.0,
            advanced=True,
        ),
        FloatInput(
            name="current_cost",
            display_name="Current Cost (USD)",
            info="Current session spend. Exceeding cost_budget triggers DENY.",
            value=0.0,
            advanced=True,
        ),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            info="Hard cap on loop iterations. 0 = no cap.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="current_iteration",
            display_name="Current Iteration",
            info="Current loop iteration count.",
            value=0,
            advanced=True,
        ),
        BoolInput(
            name="injection_defense",
            display_name="Injection Defense",
            info="Enable prompt injection detection.",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Text", name="filtered_text", method="check_governance"),
        Output(display_name="Decision", name="decision", method="get_decision"),
        Output(display_name="Blocked", name="blocked", method="is_blocked"),
    ]

    def _evaluate(self) -> dict[str, Any]:
        """Deterministic policy evaluation. Returns full result dict."""
        if hasattr(self, "_governance_result"):
            return self._governance_result  # type: ignore[attr-defined]

        start = time.perf_counter()
        if isinstance(self.text, Message):
            raw_text = self.text.text
        elif isinstance(self.text, Data):
            raw_text = str(self.text.data.get(self.text.text_key, "") or self.text.text or "")
        elif isinstance(self.text, str):
            raw_text = self.text
        else:
            raw_text = str(self.text or "")

        categories: list[str] = list(self.pii_categories or [])
        pii_findings = _detect_pii(raw_text, categories) if raw_text else []
        injection_findings: list[dict[str, Any]] = []
        if self.injection_defense and raw_text:
            injection_findings = _detect_injection(raw_text)

        tool_blocked = False
        tool_reason = ""
        allowlist_raw = (self.tool_allowlist or "").strip()
        tool_name_val = (self.tool_name or "").strip()
        if allowlist_raw and tool_name_val:
            allowed = [t.strip() for t in allowlist_raw.split(",") if t.strip()]
            if tool_name_val not in allowed:
                tool_blocked = True
                tool_reason = f"Tool '{tool_name_val}' not in allowlist"

        budget_blocked = bool(
            self.cost_budget and self.cost_budget > 0 and self.current_cost and self.current_cost > self.cost_budget
        )
        iteration_blocked = bool(
            self.max_iterations
            and self.max_iterations > 0
            and self.current_iteration
            and self.current_iteration > self.max_iterations
        )

        mode = (self.mode or "ENFORCE").upper()
        pii_action = (self.pii_action or "block").lower()

        blocked = False
        reason_parts: list[str] = []
        filtered_text = raw_text

        if pii_findings:
            if pii_action == "block":
                blocked = True
                reason_parts.append(f"PII detected: {', '.join(sorted({f['category'] for f in pii_findings}))}")
            elif pii_action == "redact":
                filtered_text = _redact_pii(raw_text, pii_findings)
                reason_parts.append(f"PII redacted: {', '.join(sorted({f['category'] for f in pii_findings}))}")
            else:
                reason_parts.append(f"PII detected: {', '.join(sorted({f['category'] for f in pii_findings}))}")

        if injection_findings:
            blocked = True
            reason_parts.append("Prompt injection detected")

        if tool_blocked:
            blocked = True
            reason_parts.append(tool_reason)

        if budget_blocked:
            blocked = True
            reason_parts.append(f"Cost budget exceeded: {self.current_cost} > {self.cost_budget}")

        if iteration_blocked:
            blocked = True
            reason_parts.append(f"Max iterations exceeded: {self.current_iteration} > {self.max_iterations}")

        if mode == "OBSERVE":
            action = "OBSERVE"
            blocked_out = False
            # In OBSERVE, keep passthrough (or redacted if configured)
            if pii_action == "redact" and pii_findings:
                filtered_text = _redact_pii(raw_text, pii_findings)
            else:
                filtered_text = raw_text if not (pii_action == "redact" and pii_findings) else filtered_text
        elif mode == "MONITOR":
            action = "DENY" if blocked else "ALLOW"
            blocked_out = blocked
            if pii_action == "block" and pii_findings:
                filtered_text = raw_text
            elif pii_action == "redact" and pii_findings:
                filtered_text = _redact_pii(raw_text, pii_findings)
        else:  # ENFORCE
            action = "DENY" if blocked else "ALLOW"
            blocked_out = blocked
            if blocked:
                if (
                    pii_action == "redact"
                    and pii_findings
                    and not (injection_findings or tool_blocked or budget_blocked or iteration_blocked)
                ):
                    # redact keeps sanitized text even in ENFORCE
                    filtered_text = _redact_pii(raw_text, pii_findings)
                elif (pii_findings and pii_action == "block") or (
                    injection_findings or tool_blocked or budget_blocked or iteration_blocked
                ):
                    filtered_text = ""
                elif pii_action == "redact":
                    pass  # already redacted
                else:
                    filtered_text = ""

        latency_ms = (time.perf_counter() - start) * 1000

        risk_score = 0.0
        if pii_findings:
            risk_score += min(0.5 + 0.1 * len(pii_findings), 0.9)
        if injection_findings:
            risk_score = max(risk_score, 0.95)
        if tool_blocked or budget_blocked or iteration_blocked:
            risk_score = max(risk_score, 0.8)
        risk_score = min(risk_score, 1.0)

        correlation_id = str(uuid.uuid4())
        all_findings = pii_findings + injection_findings
        if tool_blocked:
            all_findings.append({"category": "tool_authorization", "match": tool_name_val, "reason": tool_reason})
        if budget_blocked:
            all_findings.append({"category": "cost_budget", "match": str(self.current_cost)})
        if iteration_blocked:
            all_findings.append({"category": "max_iterations", "match": str(self.current_iteration)})

        result = {
            "correlation_id": correlation_id,
            "action": action,
            "mode": mode,
            "blocked": blocked_out,
            "filtered_text": filtered_text,
            "findings": all_findings,
            "pii_findings": pii_findings,
            "injection_findings": injection_findings,
            "risk_score": round(risk_score, 3),
            "latency_ms": round(latency_ms, 3),
            "reason": "; ".join(reason_parts) if reason_parts else "No policy violation",
            "tool_authorized": not tool_blocked,
        }

        self._governance_result = result  # type: ignore[attr-defined]
        self.status = f"{result['action']} — {result['reason']} ({result['latency_ms']}ms)"
        return result

    def check_governance(self) -> Message:
        result = self._evaluate()
        return Message(text=result["filtered_text"])

    def get_decision(self) -> Data:
        result = self._evaluate()
        return Data(
            data={
                "correlation_id": result["correlation_id"],
                "action": result["action"],
                "mode": result["mode"],
                "blocked": result["blocked"],
                "findings": result["findings"],
                "risk_score": result["risk_score"],
                "latency_ms": result["latency_ms"],
                "reason": result["reason"],
                "tool_authorized": result["tool_authorized"],
            }
        )

    def is_blocked(self) -> Data:
        result = self._evaluate()
        return Data(data={"blocked": result["blocked"]})
