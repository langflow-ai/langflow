import importlib.util
import os
import sys
import unittest

# Load module directly
file_path = os.path.join(
    os.path.dirname(__file__),
    "../../base/langflow/helpers/production_debt.py",
)
spec = importlib.util.spec_from_file_location("langflow_production_debt", file_path)
production_debt_mod = importlib.util.module_from_spec(spec)
sys.modules["langflow_production_debt"] = production_debt_mod
spec.loader.exec_module(production_debt_mod)

ProductionDebtComponent = production_debt_mod.ProductionDebtComponent
TechnicalDueDiligenceLedger = production_debt_mod.TechnicalDueDiligenceLedger
GENESIS_HASH = production_debt_mod.GENESIS_HASH


class TestProductionDebtComponent(unittest.TestCase):
    def setUp(self) -> None:
        self.component = ProductionDebtComponent(
            never_equate_intent_to_approval=True,
            max_acceptable_vdi=12.0,
        )

    def test_clean_visual_flow_passes_readiness(self) -> None:
        report = self.component.evaluate_flow_execution(
            flow_id="flow_prod_01",
            node_count=6,
            context_tokens=1000,
            generated_tokens=100,
            step_latency_seconds=0.85,
            back_edge_loops=0,
            un_gated_mutations=0,
        )
        self.assertTrue(report.is_production_ready)
        self.assertLessEqual(report.vdi_score, 12.0)
        self.assertEqual(len(report.critical_smells), 0)
        self.assertTrue(bool(report.receipt_hash))

    def test_degraded_visual_flow_fails_debt(self) -> None:
        report = self.component.evaluate_flow_execution(
            flow_id="flow_runaway_loop",
            node_count=12,
            context_tokens=1000,
            generated_tokens=3000,  # High token inflation (4.0x)
            step_latency_seconds=7.5,  # High latency
            back_edge_loops=4,  # 4 visual loop cycles
            un_gated_mutations=2,  # 2 un-gated mutations
        )
        self.assertFalse(report.is_production_ready)
        self.assertGreater(report.vdi_score, 50.0)
        self.assertIn("HIGH_TOKEN_INFLATION_4.00X", report.critical_smells)
        self.assertIn("HIGH_FLOW_LATENCY_7.50S", report.critical_smells)
        self.assertIn("DETECTED_4_VISUAL_GRAPH_LOOPS", report.critical_smells)
        self.assertIn("DETECTED_2_UNGATED_MUTATIONS", report.critical_smells)

    def test_cryptographic_ledger_integrity(self) -> None:
        self.component.evaluate_flow_execution("flow-1")
        self.component.evaluate_flow_execution("flow-2")
        self.component.evaluate_flow_execution("flow-3")

        entries = self.component.ledger.get_ledger_entries()
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["prev_hash"], GENESIS_HASH)
        self.assertEqual(entries[1]["prev_hash"], entries[0]["curr_hash"])
        self.assertEqual(entries[2]["prev_hash"], entries[1]["curr_hash"])
        self.assertTrue(self.component.ledger.verify_ledger_integrity())


if __name__ == "__main__":
    unittest.main()
