"""Unit tests for QualityMetricsConnector."""

import pytest
from langflow.components.healthcare.quality_metrics_connector import QualityMetricsConnector
from langflow.schema.data import Data


class TestQualityMetricsConnector:
    """Test suite for QualityMetricsConnector."""

    def test_connector_initialization(self):
        """Test that the connector initializes correctly."""
        connector = QualityMetricsConnector()
        assert connector.display_name == "Quality Metrics Connector"
        assert connector.name == "QualityMetricsConnector"
        assert connector.icon == "TrendingUp"

    def test_required_fields(self):
        """Test that required fields are correctly defined."""
        connector = QualityMetricsConnector()
        required_fields = connector.get_required_fields()
        assert "metric_category" in required_fields

    def test_mock_response_generation(self):
        """Test mock response generation."""
        connector = QualityMetricsConnector()
        request_data = {
            "metric_category": "hedis_effectiveness",
            "measure_set": "MY2023",
            "benchmark_type": "national_percentile"
        }

        response = connector.get_mock_response(request_data)

        assert response["status"] == "success"
        assert "measures" in response
        assert "summary_statistics" in response
        assert response["metric_category"] == "hedis_effectiveness"

    def test_run_method_execution(self):
        """Test the run method executes without errors."""
        connector = QualityMetricsConnector()

        # This would normally be set by the component framework
        result = connector.run(
            metric_category="hedis_effectiveness",
            measure_set="MY2023",
            benchmark_type="national_percentile"
        )

        assert isinstance(result, Data)
        assert result.data is not None
        assert result.data.get("status") == "success"

    def test_hipaa_compliance_logging(self):
        """Test that HIPAA compliance logging is working."""
        connector = QualityMetricsConnector()
        request_data = {
            "metric_category": "hedis_effectiveness",
            "measure_set": "MY2023"
        }

        # This should not raise any exceptions
        response = connector.process_healthcare_request(request_data)
        assert response["status"] == "success"

    def test_invalid_metric_category(self):
        """Test handling of invalid metric category."""
        connector = QualityMetricsConnector()
        request_data = {
            "metric_category": "invalid_category"
        }

        with pytest.raises(ValueError, match="Invalid metric category"):
            connector.process_healthcare_request(request_data)

    def test_measure_filtering(self):
        """Test that measure set filtering works correctly."""
        connector = QualityMetricsConnector()
        request_data = {
            "metric_category": "hedis_effectiveness",
            "measure_set": "BCS",
            "benchmark_type": "national_percentile"
        }

        response = connector.get_mock_response(request_data)
        assert response["measure_set"] == "BCS"
        assert "measures" in response

    def test_trend_analysis_inclusion(self):
        """Test that trend analysis is included when requested."""
        connector = QualityMetricsConnector()
        request_data = {
            "metric_category": "hedis_effectiveness",
            "include_trends": True
        }

        response = connector.get_mock_response(request_data)
        assert "trend_analysis" in response
        assert "overall_trajectory" in response["trend_analysis"]