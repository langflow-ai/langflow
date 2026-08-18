import importlib.util
import sys
from pathlib import Path

# Load module directly
file_path = (
    Path(__file__).parent.parent.parent / "base/langflow/helpers/production_debt.py"
).resolve()
spec = importlib.util.spec_from_file_location("langflow_production_debt", file_path)
production_debt_mod = importlib.util.module_from_spec(spec)
sys.modules["langflow_production_debt"] = production_debt_mod
spec.loader.exec_module(production_debt_mod)

ProductionDebtComponent = production_debt_mod.ProductionDebtComponent
TechnicalDueDiligenceLedger = production_debt_mod.TechnicalDueDiligenceLedger
GENESIS_HASH = production_debt_mod.GENESIS_HASH


def test_clean_visual_flow_passes_readiness() -> None:
    component = ProductionDebtComponent(
        never_equate_intent_to_approval=True,
        max_acceptable_vdi=12.0,
    )
    report = component.evaluate_flow_execution(
        flow_id="flow_prod_01",
        node_count=6,
        context_tokens=1000,
        generated_tokens=100,
        step_latency_seconds=0.85,
        back_edge_loops=0,
        un_gated_mutations=0,
    )
    assert report.is_production_ready
    assert report.vdi_score <= 12.0
    assert len(report.critical_smells) == 0
    assert bool(report.receipt_hash)


def test_degraded_visual_flow_fails_debt() -> None:
    component = ProductionDebtComponent(
        never_equate_intent_to_approval=True,
        max_acceptable_vdi=12.0,
    )
    report = component.evaluate_flow_execution(
        flow_id="flow_runaway_loop",
        node_count=12,
        context_tokens=1000,
        generated_tokens=3000,  # High token inflation (4.0x)
        step_latency_seconds=7.5,  # High latency
        back_edge_loops=4,  # 4 visual loop cycles
        un_gated_mutations=2,  # 2 un-gated mutations
    )
    assert not report.is_production_ready
    assert report.vdi_score > 50.0
    assert "HIGH_TOKEN_INFLATION_4.00X" in report.critical_smells
    assert "HIGH_FLOW_LATENCY_7.50S" in report.critical_smells
    assert "DETECTED_4_VISUAL_GRAPH_LOOPS" in report.critical_smells
    assert "DETECTED_2_UNGATED_MUTATIONS" in report.critical_smells


def test_cryptographic_ledger_integrity() -> None:
    component = ProductionDebtComponent(
        never_equate_intent_to_approval=True,
        max_acceptable_vdi=12.0,
    )
    component.evaluate_flow_execution("flow-1")
    component.evaluate_flow_execution("flow-2")
    component.evaluate_flow_execution("flow-3")

    entries = component.ledger.get_ledger_entries()
    assert len(entries) == 3
    assert entries[0]["prev_hash"] == GENESIS_HASH
    assert entries[1]["prev_hash"] == entries[0]["curr_hash"]
    assert entries[2]["prev_hash"] == entries[1]["curr_hash"]
    assert component.ledger.verify_ledger_integrity()
