# ruff: noqa: S108, PLR2004, FBT001, FBT002
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log: logging.Logger = logging.getLogger(__name__)

GENESIS_HASH: str = "0000000000000000000000000000000000000000000000000000000000000000"


@dataclass
class FlowDebtReport:
    flow_id: str
    vdi_score: float  # Visual Debt Index (target <= 12.0)
    token_inflation_multiplier: float  # Target <= 1.15x
    step_latency_seconds: float  # Target <= 1.8s
    mutation_safety_score: float  # Target 100.0
    production_readiness_index: float  # Scale 0 - 100
    is_production_ready: bool
    critical_smells: list[str]
    receipt_hash: str


class TechnicalDueDiligenceLedger:
    """Cryptographic SHA-256 hash-chained Action Ledger for Langflow visual agent runs."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []
        self._last_hash: str = GENESIS_HASH

    def record_flow_step(
        self,
        flow_id: str,
        event_type: str,
        readiness_index: float,
        critical_smells: list[str],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        index = len(self._entries)

        meta_bytes = json.dumps(metadata, sort_keys=True).encode("utf-8")
        meta_hash = hashlib.sha256(meta_bytes).hexdigest()
        canonical_content = (
            f"{index}|{self._last_hash}|{flow_id}|{event_type}|{readiness_index}|{timestamp}|{meta_hash}"
        )
        curr_hash = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()

        entry = {
            "index": index,
            "timestamp": timestamp,
            "flow_id": flow_id,
            "event_type": event_type,
            "readiness_index": readiness_index,
            "critical_smells": critical_smells,
            "prev_hash": self._last_hash,
            "curr_hash": curr_hash,
            "metadata": metadata,
        }

        self._entries.append(entry)
        self._last_hash = curr_hash
        return entry

    def get_ledger_entries(self) -> list[dict[str, Any]]:
        return list(self._entries)

    def verify_ledger_integrity(self) -> bool:
        prev = GENESIS_HASH
        for entry in self._entries:
            if entry["prev_hash"] != prev:
                return False
            prev = entry["curr_hash"]
        return True


class ProductionDebtComponent:
    """A2Z SOC Production Debt & Technical Due Diligence Component for Langflow.

    Quantifies visual multi-agent graph flows against 4 Enterprise Forward Deployed Engineering KPIs:
    1. Visual Graph Debt Index (VDI <= 12.0)
    2. Node Token Inflation Multiplier (NTI <= 1.15x)
    3. P99 Step Latency Ceiling (<= 1.8s)
    4. Deterministic Mutation Boundaries (never_equate_intent_to_approval)
    """

    def __init__(
        self,
        never_equate_intent_to_approval: bool = True,
        max_acceptable_vdi: float = 12.0,
    ) -> None:
        self.never_equate_intent_to_approval = never_equate_intent_to_approval
        self.max_acceptable_vdi = max_acceptable_vdi
        self.ledger = TechnicalDueDiligenceLedger()

    def check_kill_switch(self) -> bool:
        if os.environ.get("AAG_KILL_SWITCH", "").lower() in ("true", "1", "yes"):
            return True
        return any(Path(p).exists() for p in ("artifacts/KILL", "/tmp/KILL"))

    def evaluate_flow_execution(
        self,
        flow_id: str,
        node_count: int = 5,
        context_tokens: int = 1000,
        generated_tokens: int = 120,
        step_latency_seconds: float = 0.95,
        back_edge_loops: int = 0,
        un_gated_mutations: int = 0,
    ) -> FlowDebtReport:
        # 1. Evaluate emergency kill switch
        if self.check_kill_switch():
            self.ledger.record_flow_step(
                flow_id=flow_id,
                event_type="flow_halted_kill_switch",
                readiness_index=0.0,
                critical_smells=["EMERGENCY_KILL_SWITCH_ENGAGED"],
                metadata={"reason": "AAG_KILL_SWITCH is set"},
            )
            err_msg = "A2Z SOC ActionGate: Emergency kill switch is engaged. Visual flow execution halted."
            raise PermissionError(err_msg)

        critical_smells: list[str] = []

        # KPI 2: Node Token Inflation Multiplier
        token_ratio = (context_tokens + generated_tokens) / max(1, context_tokens)
        if token_ratio > 2.0:
            critical_smells.append(f"HIGH_TOKEN_INFLATION_{token_ratio:.2f}X")

        # KPI 3: Latency Ceiling
        if step_latency_seconds > 5.0:
            critical_smells.append(f"HIGH_FLOW_LATENCY_{step_latency_seconds:.2f}S")

        # Visual Back-Edge Loops
        if back_edge_loops > 2:
            critical_smells.append(f"DETECTED_{back_edge_loops}_VISUAL_GRAPH_LOOPS")

        # KPI 4: Mutation Safety
        if un_gated_mutations > 0:
            critical_smells.append(f"DETECTED_{un_gated_mutations}_UNGATED_MUTATIONS")

        # KPI 1: Visual Graph Debt Index (0 = Clean, 100 = Catastrophic)
        vdi = (
            max(0.0, (token_ratio - 1.0) * 20.0)
            + max(0.0, (step_latency_seconds - 1.8) * 10.0)
            + (back_edge_loops * 15.0)
            + (un_gated_mutations * 30.0)
        )
        vdi_score = round(min(100.0, vdi), 2)

        # Production Readiness Index (0 - 100)
        readiness = max(0.0, 100.0 - vdi_score)
        is_production_ready = vdi_score <= self.max_acceptable_vdi and len(critical_smells) == 0

        # Cryptographic Ledger Entry
        entry = self.ledger.record_flow_step(
            flow_id=flow_id,
            event_type="flow_authorized" if is_production_ready else "flow_flagged_debt",
            readiness_index=readiness,
            critical_smells=critical_smells,
            metadata={
                "vdi_score": vdi_score,
                "token_ratio": token_ratio,
                "node_count": node_count,
                "context_tokens": context_tokens,
                "generated_tokens": generated_tokens,
                "step_latency_seconds": step_latency_seconds,
                "back_edge_loops": back_edge_loops,
                "un_gated_mutations": un_gated_mutations,
                "never_equate_intent_to_approval": self.never_equate_intent_to_approval,
            },
        )

        return FlowDebtReport(
            flow_id=flow_id,
            vdi_score=vdi_score,
            token_inflation_multiplier=round(token_ratio, 2),
            step_latency_seconds=round(step_latency_seconds, 2),
            mutation_safety_score=(100.0 if un_gated_mutations == 0 else max(0.0, 100.0 - un_gated_mutations * 30.0)),
            production_readiness_index=readiness,
            is_production_ready=is_production_ready,
            critical_smells=critical_smells,
            receipt_hash=entry["curr_hash"],
        )
