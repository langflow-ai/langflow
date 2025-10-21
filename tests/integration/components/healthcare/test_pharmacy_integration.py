"""Integration tests for PharmacyConnector with end-to-end workflows."""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from langflow.components.healthcare.pharmacy_connector import PharmacyConnector
from langflow.schema.data import Data


class TestPharmacyConnectorIntegration:
    """Integration tests for PharmacyConnector end-to-end workflows."""

    @pytest.fixture
    def pharmacy_connector(self):
        """Create a configured PharmacyConnector for integration testing."""
        connector = PharmacyConnector()
        connector.pharmacy_network = "surescripts"
        connector.prescriber_npi = "1234567890"
        connector.dea_number = "AB1234567"
        connector.drug_database = "first_databank"
        connector.interaction_checking = True
        connector.formulary_checking = True
        connector.prior_auth_checking = True
        connector.test_mode = True
        connector.mock_mode = True
        connector.audit_logging = True
        connector.timeout_seconds = "30"
        return connector

    def test_complete_e_prescribing_workflow(self, pharmacy_connector):
        """Test complete e-prescribing workflow from prescription to confirmation."""
        # Step 1: Check drug interactions
        medications = ["Lisinopril 10mg", "Metformin 500mg"]
        interaction_result = pharmacy_connector.check_drug_interactions(medications)

        assert "interactions" in interaction_result
        assert "total_interactions" in interaction_result

        # Step 2: Verify formulary status
        formulary_result = pharmacy_connector.verify_formulary("0093-7663-01", "HP123456")

        assert "formulary_status" in formulary_result
        assert "coverage_determination" in formulary_result

        # Step 3: Check prior authorization if needed
        if formulary_result.get("prior_authorization_required"):
            pa_result = pharmacy_connector.check_prior_auth_requirements("0093-7663-01", "HP123456")
            assert "pa_required" in pa_result

        # Step 4: Send prescription
        prescription_data = {
            "patient_id": "PAT123456",
            "medication": "Lisinopril 10mg",
            "quantity": 30,
            "refills": 5,
            "directions": "Take one tablet daily"
        }

        prescription_result = pharmacy_connector.send_prescription(prescription_data)

        assert "prescription_id" in prescription_result
        assert "status" in prescription_result
        assert prescription_result["status"] == "transmitted"

    def test_medication_therapy_management_workflow(self, pharmacy_connector):
        """Test complete MTM workflow with medication reconciliation and optimization."""
        # Step 1: Get current medications for reconciliation
        current_medications = [
            {
                "medication": "Lisinopril 10mg",
                "patient_id": "PAT123456",
                "prescriber": "Dr. Smith",
                "start_date": "2024-01-15"
            },
            {
                "medication": "Metformin 500mg",
                "patient_id": "PAT123456",
                "prescriber": "Dr. Johnson",
                "start_date": "2023-06-20"
            }
        ]

        # Step 2: Perform medication reconciliation
        reconciliation_result = pharmacy_connector.reconcile_medications(current_medications)

        assert "current_medications" in reconciliation_result
        assert "reconciliation_summary" in reconciliation_result
        assert "clinical_alerts" in reconciliation_result

        # Step 3: Perform MTM review
        mtm_result = pharmacy_connector.perform_mtm_review("PAT123456", current_medications)

        assert "mtm_eligible" in mtm_result
        assert "therapy_review" in mtm_result
        assert "recommendations" in mtm_result
        assert "adherence_data" in mtm_result
        assert "cost_analysis" in mtm_result

        # Verify MTM results structure
        therapy_review = mtm_result["therapy_review"]
        assert "overall_score" in therapy_review
        assert "adherence_rate" in therapy_review

    def test_multi_patient_workflow(self, pharmacy_connector):
        """Test workflow handling multiple patients simultaneously."""
        patients = [
            {"patient_id": "PAT001", "medication": "Lisinopril 10mg"},
            {"patient_id": "PAT002", "medication": "Metformin 500mg"},
            {"patient_id": "PAT003", "medication": "Atorvastatin 20mg"}
        ]

        results = []
        for patient in patients:
            result = pharmacy_connector.send_prescription(patient)
            results.append(result)

        # Verify each patient got a unique response
        prescription_ids = [result["prescription_id"] for result in results]
        assert len(set(prescription_ids)) == 3  # All unique

        # Verify all prescriptions were successful
        for result in results:
            assert result["status"] == "transmitted"

    def test_error_recovery_workflow(self, pharmacy_connector):
        """Test error handling and recovery in healthcare workflows."""
        # Test with invalid data that should trigger error handling
        invalid_prescription = {
            "patient_id": "",  # Invalid empty patient ID
            "medication": "Invalid Drug Name",
            "quantity": -5  # Invalid negative quantity
        }

        result = pharmacy_connector.execute_pharmacy_workflow()
        pharmacy_connector.prescription_data = json.dumps(invalid_prescription)

        workflow_result = pharmacy_connector.execute_pharmacy_workflow()

        # Should handle gracefully and return structured error response
        assert isinstance(workflow_result, Data)
        assert workflow_result.metadata["hipaa_compliant"] is True

    def test_audit_trail_completeness(self, pharmacy_connector):
        """Test that complete audit trail is maintained throughout workflow."""
        audit_logs = []

        # Mock audit logger to capture all log entries
        def capture_audit_log(log_entry):
            audit_logs.append(json.loads(log_entry))

        with patch.object(pharmacy_connector._audit_logger, 'info', side_effect=capture_audit_log):
            # Perform a complete workflow
            prescription_data = {
                "patient_id": "PAT123456",
                "medication": "Lisinopril 10mg"
            }

            pharmacy_connector.prescription_data = json.dumps(prescription_data)
            result = pharmacy_connector.execute_pharmacy_workflow()

            # Verify audit trail contains all required entries
            assert len(audit_logs) >= 2  # At minimum: workflow_start and workflow_complete

            workflow_start = next((log for log in audit_logs if log["action"] == "workflow_start"), None)
            workflow_complete = next((log for log in audit_logs if log["action"] == "workflow_complete"), None)

            assert workflow_start is not None
            assert workflow_complete is not None
            assert workflow_start["request_id"] == workflow_complete["request_id"]

    def test_performance_benchmarks(self, pharmacy_connector):
        """Test performance benchmarks for real-time healthcare interactions."""
        import time

        start_time = time.time()

        # Perform multiple operations to test performance
        operations = [
            {"operation": "e_prescribe", "patient_id": "PAT001"},
            {"operation": "drug_interaction", "patient_id": "PAT002"},
            {"operation": "formulary_check", "patient_id": "PAT003"},
            {"operation": "prior_authorization", "patient_id": "PAT004"},
            {"operation": "medication_reconciliation", "patient_id": "PAT005"}
        ]

        results = []
        for operation in operations:
            pharmacy_connector.prescription_data = json.dumps(operation)
            result = pharmacy_connector.execute_pharmacy_workflow()
            results.append(result)

        total_time = time.time() - start_time

        # Verify performance meets requirements (should process 5 operations in under 10 seconds)
        assert total_time < 10.0

        # Verify all operations completed successfully
        for result in results:
            assert isinstance(result, Data)
            assert result.metadata["processing_time_seconds"] is not None

    def test_network_configuration_switching(self, pharmacy_connector):
        """Test switching between different pharmacy networks."""
        networks = ["surescripts", "ncpdp", "relay_health"]

        for network in networks:
            pharmacy_connector.pharmacy_network = network

            prescription_data = {
                "operation": "e_prescribe",
                "patient_id": "PAT123456",
                "medication": "Lisinopril 10mg"
            }

            pharmacy_connector.prescription_data = json.dumps(prescription_data)
            result = pharmacy_connector.execute_pharmacy_workflow()

            assert result.data["network"] == network
            assert result.metadata["hipaa_compliant"] is True

    def test_drug_database_switching(self, pharmacy_connector):
        """Test switching between different drug databases."""
        databases = ["first_databank", "medi_span", "lexicomp"]

        for database in databases:
            pharmacy_connector.drug_database = database

            interaction_data = {
                "operation": "drug_interaction",
                "medications": ["Drug A", "Drug B"]
            }

            pharmacy_connector.prescription_data = json.dumps(interaction_data)
            result = pharmacy_connector.execute_pharmacy_workflow()

            assert isinstance(result, Data)
            assert result.metadata["hipaa_compliant"] is True

    def test_compliance_features_integration(self, pharmacy_connector):
        """Test integration of all HIPAA compliance features."""
        # Test with PHI-containing data
        phi_prescription = {
            "patient_id": "PAT123456",
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "dob": "1980-01-01",
            "medication": "Lisinopril 10mg"
        }

        pharmacy_connector.prescription_data = json.dumps(phi_prescription)

        with patch.object(pharmacy_connector._audit_logger, 'info') as mock_audit:
            result = pharmacy_connector.execute_pharmacy_workflow()

            # Verify audit logging occurred
            assert mock_audit.call_count >= 2

            # Verify response metadata includes compliance information
            assert result.metadata["hipaa_compliant"] is True
            assert result.metadata["phi_protected"] is True
            assert result.metadata["audit_logged"] is True

    def test_mock_to_live_mode_transition(self, pharmacy_connector):
        """Test transition from mock mode to live mode."""
        # Start in mock mode
        pharmacy_connector.mock_mode = True
        pharmacy_connector.test_mode = True

        prescription_data = {
            "operation": "e_prescribe",
            "patient_id": "PAT123456"
        }

        pharmacy_connector.prescription_data = json.dumps(prescription_data)

        # Test mock mode
        mock_result = pharmacy_connector.execute_pharmacy_workflow()
        assert mock_result.metadata["transaction_type"] == "mock_response"

        # Switch to live mode (but keep test_mode=True to avoid real API calls)
        pharmacy_connector.mock_mode = False

        live_result = pharmacy_connector.execute_pharmacy_workflow()
        assert live_result.metadata["transaction_type"] == "live_response"

    def test_data_consistency_across_operations(self, pharmacy_connector):
        """Test data consistency across different pharmacy operations."""
        patient_id = "PAT123456"
        medication = "Lisinopril 10mg"

        # Test different operations with same patient data
        operations = [
            {"operation": "e_prescribe", "patient_id": patient_id, "medication": medication},
            {"operation": "drug_interaction", "patient_id": patient_id, "medications": [medication]},
            {"operation": "formulary_check", "patient_id": patient_id, "medication": medication},
            {"operation": "medication_reconciliation", "patient_id": patient_id}
        ]

        results = []
        for operation in operations:
            pharmacy_connector.prescription_data = json.dumps(operation)
            result = pharmacy_connector.execute_pharmacy_workflow()
            results.append(result)

        # Verify patient_id consistency across all operations
        for result in results:
            assert result.data["patient_id"] == patient_id

        # Verify metadata consistency
        for result in results:
            assert result.metadata["component"] == "PharmacyConnector"
            assert result.metadata["hipaa_compliant"] is True

    def test_concurrent_request_handling(self, pharmacy_connector):
        """Test handling of concurrent requests with unique identifiers."""
        import threading
        import time

        results = []
        request_ids = []

        def process_prescription(patient_num):
            local_connector = PharmacyConnector()
            local_connector.pharmacy_network = "surescripts"
            local_connector.test_mode = True
            local_connector.mock_mode = True
            local_connector.audit_logging = True

            prescription_data = {
                "operation": "e_prescribe",
                "patient_id": f"PAT{patient_num:06d}",
                "medication": "Lisinopril 10mg"
            }

            local_connector.prescription_data = json.dumps(prescription_data)
            result = local_connector.execute_pharmacy_workflow()
            results.append(result)
            request_ids.append(result.metadata["request_id"])

        # Create and start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=process_prescription, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all requests completed
        assert len(results) == 5
        assert len(request_ids) == 5

        # Verify all request IDs are unique
        assert len(set(request_ids)) == 5

    def test_comprehensive_workflow_validation(self, pharmacy_connector):
        """Test comprehensive workflow that exercises all major features."""
        # Complete patient scenario
        patient_data = {
            "patient_id": "PAT123456",
            "medications": ["Lisinopril 10mg", "Metformin 500mg"],
            "allergies": ["Penicillin", "Sulfa"],
            "insurance_plan": "HP123456"
        }

        workflow_steps = []

        # Step 1: Check drug interactions
        interaction_check = pharmacy_connector.check_drug_interactions(
            patient_data["medications"],
            patient_data["allergies"]
        )
        workflow_steps.append(("interaction_check", interaction_check))

        # Step 2: Verify formulary for each medication
        for medication in patient_data["medications"]:
            formulary_check = pharmacy_connector.verify_formulary(
                "0093-7663-01",  # Mock NDC
                patient_data["insurance_plan"]
            )
            workflow_steps.append(("formulary_check", formulary_check))

        # Step 3: Medication reconciliation
        current_meds = [
            {"medication": med, "patient_id": patient_data["patient_id"]}
            for med in patient_data["medications"]
        ]
        reconciliation = pharmacy_connector.reconcile_medications(current_meds)
        workflow_steps.append(("reconciliation", reconciliation))

        # Step 4: MTM review
        mtm_review = pharmacy_connector.perform_mtm_review(
            patient_data["patient_id"],
            current_meds
        )
        workflow_steps.append(("mtm_review", mtm_review))

        # Step 5: Send prescription
        prescription = pharmacy_connector.send_prescription({
            "patient_id": patient_data["patient_id"],
            "medication": patient_data["medications"][0],
            "quantity": 30,
            "refills": 5
        })
        workflow_steps.append(("prescription", prescription))

        # Verify all steps completed successfully
        assert len(workflow_steps) >= 5

        for step_name, step_result in workflow_steps:
            assert isinstance(step_result, dict)
            assert step_result is not None

        # Verify workflow maintains data consistency
        patient_ids = []
        for step_name, step_result in workflow_steps:
            if "patient_id" in step_result:
                patient_ids.append(step_result["patient_id"])

        # All patient IDs should be consistent
        unique_patient_ids = set(patient_ids)
        assert len(unique_patient_ids) <= 1  # Should be 0 or 1 unique patient ID
        if unique_patient_ids:
            assert patient_data["patient_id"] in unique_patient_ids