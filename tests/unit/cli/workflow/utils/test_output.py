"""Unit tests for the output utility functions."""

import pytest
from unittest.mock import patch, Mock
from rich.console import Console

from langflow.cli.workflow.utils.output import (
    success_message,
    error_message,
    warning_message,
    info_message,
    format_table,
    format_panel,
    format_validation_report,
    format_flow_stats
)


class TestOutputMessages:
    """Test the message output functions."""

    @patch('click.echo')
    def test_success_message(self, mock_echo):
        """Test success message output."""
        success_message("Operation completed")
        mock_echo.assert_called_once()
        args = mock_echo.call_args[0]
        assert "Operation completed" in str(args[0])
        assert "✅" in str(args[0])

    @patch('click.echo')
    def test_error_message(self, mock_echo):
        """Test error message output."""
        error_message("Something went wrong")
        mock_echo.assert_called_once()
        args = mock_echo.call_args[0]
        assert "Something went wrong" in str(args[0])
        assert "❌" in str(args[0])
        # Check that err=True is passed
        assert mock_echo.call_args[1]['err'] is True

    @patch('click.echo')
    def test_warning_message(self, mock_echo):
        """Test warning message output."""
        warning_message("This is a warning")
        mock_echo.assert_called_once()
        args = mock_echo.call_args[0]
        assert "This is a warning" in str(args[0])
        assert "⚠️" in str(args[0])

    @patch('click.echo')
    def test_info_message(self, mock_echo):
        """Test info message output."""
        info_message("Information message")
        mock_echo.assert_called_once()
        args = mock_echo.call_args[0]
        assert "Information message" in str(args[0])
        assert "ℹ️" in str(args[0])


class TestFormatTable:
    """Test the format_table function."""

    def test_format_table_basic(self):
        """Test basic table formatting."""
        headers = ["Name", "Value"]
        rows = [["item1", "value1"], ["item2", "value2"]]

        result = format_table(headers, rows)

        assert "Name" in result
        assert "Value" in result
        assert "item1" in result
        assert "value1" in result
        assert "item2" in result
        assert "value2" in result

    def test_format_table_with_title(self):
        """Test table formatting with title."""
        headers = ["ID", "Status"]
        rows = [["1", "Active"], ["2", "Inactive"]]
        title = "Test Table"

        result = format_table(headers, rows, title)

        assert title in result
        assert "ID" in result
        assert "Status" in result

    def test_format_table_empty_rows(self):
        """Test table formatting with empty rows."""
        headers = ["Header1", "Header2"]
        rows = []

        result = format_table(headers, rows)

        assert "Header1" in result
        assert "Header2" in result

    def test_format_table_single_row(self):
        """Test table formatting with single row."""
        headers = ["Column"]
        rows = [["Single Value"]]

        result = format_table(headers, rows)

        assert "Column" in result
        assert "Single Value" in result


class TestFormatPanel:
    """Test the format_panel function."""

    def test_format_panel_basic(self):
        """Test basic panel formatting."""
        content = "This is panel content"

        result = format_panel(content)

        assert content in result

    def test_format_panel_with_title(self):
        """Test panel formatting with title."""
        content = "Panel content"
        title = "Panel Title"

        result = format_panel(content, title)

        assert content in result
        # Title might be styled differently, so just check it's present
        assert title in result or title.upper() in result

    def test_format_panel_with_style(self):
        """Test panel formatting with custom style."""
        content = "Styled content"
        title = "Styled Panel"
        style = "red"

        result = format_panel(content, title, style)

        assert content in result


class TestFormatValidationReport:
    """Test the format_validation_report function."""

    def test_format_validation_report_valid(self):
        """Test validation report for valid specification."""
        result_data = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "summary": {
                "error_count": 0,
                "warning_count": 0,
                "suggestion_count": 0
            },
            "validation_phases": {
                "schema_validation": True,
                "component_validation": True,
                "semantic_validation": True
            }
        }

        report = format_validation_report(result_data)

        assert "✅ VALID" in report
        assert "Errors: 0" in report
        assert "Warnings: 0" in report
        assert "✅ Schema Validation" in report
        assert "✅ Component Validation" in report
        assert "✅ Semantic Validation" in report

    def test_format_validation_report_invalid(self):
        """Test validation report for invalid specification."""
        result_data = {
            "valid": False,
            "errors": [
                {"message": "Missing required field", "component_id": "agent", "field": "name"},
                "Simple error message"
            ],
            "warnings": [
                {"message": "Performance warning", "component_id": "llm"},
                "Simple warning"
            ],
            "suggestions": [
                {"message": "Consider using newer version"},
                "Simple suggestion"
            ],
            "summary": {
                "error_count": 2,
                "warning_count": 2,
                "suggestion_count": 2
            }
        }

        report = format_validation_report(result_data)

        assert "❌ INVALID" in report
        assert "Errors: 2" in report
        assert "Warnings: 2" in report
        assert "Missing required field (agent.name)" in report
        assert "Simple error message" in report
        assert "Performance warning (llm)" in report
        assert "Simple warning" in report
        assert "Consider using newer version" in report
        assert "Simple suggestion" in report

    def test_format_validation_report_with_actionable_suggestions(self):
        """Test validation report with actionable suggestions."""
        result_data = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "actionable_suggestions": [
                "Add error handling to component",
                "Optimize temperature settings"
            ]
        }

        report = format_validation_report(result_data)

        assert "Add error handling to component" in report
        assert "Optimize temperature settings" in report

    def test_format_validation_report_minimal(self):
        """Test validation report with minimal data."""
        result_data = {
            "valid": False
        }

        report = format_validation_report(result_data)

        assert "❌ INVALID" in report
        assert "Specification Validation Report" in report

    def test_format_validation_report_failed_phases(self):
        """Test validation report with failed validation phases."""
        result_data = {
            "valid": False,
            "validation_phases": {
                "schema_validation": True,
                "component_validation": False,
                "semantic_validation": None
            }
        }

        report = format_validation_report(result_data)

        assert "✅ Schema Validation" in report
        assert "❌ Component Validation" in report
        # None values should be skipped


class TestFormatFlowStats:
    """Test the format_flow_stats function."""

    def test_format_flow_stats_basic(self):
        """Test basic flow statistics formatting."""
        flow_data = {
            "data": {
                "nodes": [
                    {"id": "node1", "data": {"type": "Agent"}},
                    {"id": "node2", "data": {"type": "LLM"}},
                    {"id": "node3", "data": {"type": "Agent"}}
                ],
                "edges": [
                    {"id": "edge1", "source": "node1", "target": "node2"},
                    {"id": "edge2", "source": "node2", "target": "node3"}
                ]
            }
        }

        stats = format_flow_stats(flow_data)

        assert "Flow Statistics:" in stats
        assert "Nodes: 3" in stats
        assert "Edges: 2" in stats
        assert "Agent: 2" in stats
        assert "LLM: 1" in stats

    def test_format_flow_stats_empty_flow(self):
        """Test flow statistics for empty flow."""
        flow_data = {
            "data": {
                "nodes": [],
                "edges": []
            }
        }

        stats = format_flow_stats(flow_data)

        assert "Nodes: 0" in stats
        assert "Edges: 0" in stats

    def test_format_flow_stats_no_data_key(self):
        """Test flow statistics when data key is missing."""
        flow_data = {
            "nodes": [{"id": "node1", "data": {"type": "Agent"}}],
            "edges": []
        }

        stats = format_flow_stats(flow_data)

        # Should handle missing data key gracefully
        assert "Nodes: 0" in stats or "Nodes: 1" in stats

    def test_format_flow_stats_unknown_node_types(self):
        """Test flow statistics with unknown node types."""
        flow_data = {
            "data": {
                "nodes": [
                    {"id": "node1", "data": {}},  # No type
                    {"id": "node2"}  # No data
                ],
                "edges": []
            }
        }

        stats = format_flow_stats(flow_data)

        assert "Nodes: 2" in stats
        assert "Unknown: 2" in stats

    def test_format_flow_stats_single_node_type(self):
        """Test flow statistics with single node type."""
        flow_data = {
            "data": {
                "nodes": [
                    {"id": "node1", "data": {"type": "CustomComponent"}},
                    {"id": "node2", "data": {"type": "CustomComponent"}}
                ],
                "edges": [{"id": "edge1", "source": "node1", "target": "node2"}]
            }
        }

        stats = format_flow_stats(flow_data)

        assert "Nodes: 2" in stats
        assert "Edges: 1" in stats
        assert "CustomComponent: 2" in stats

    def test_format_flow_stats_missing_nodes_edges(self):
        """Test flow statistics when nodes or edges are missing."""
        flow_data = {
            "data": {}
        }

        stats = format_flow_stats(flow_data)

        assert "Flow Statistics:" in stats
        # Should handle missing nodes/edges gracefully


class TestConsoleIntegration:
    """Test console integration."""

    @patch('langflow.cli.workflow.utils.output.console')
    def test_console_capture_in_format_table(self, mock_console):
        """Test that console capture works in format_table."""
        mock_capture = Mock()
        mock_capture.get.return_value = "captured output"
        mock_console.capture.return_value.__enter__.return_value = mock_capture

        headers = ["Test"]
        rows = [["Value"]]

        result = format_table(headers, rows)

        assert result == "captured output"
        mock_console.capture.assert_called_once()

    @patch('langflow.cli.workflow.utils.output.console')
    def test_console_capture_in_format_panel(self, mock_console):
        """Test that console capture works in format_panel."""
        mock_capture = Mock()
        mock_capture.get.return_value = "captured panel"
        mock_console.capture.return_value.__enter__.return_value = mock_capture

        result = format_panel("content")

        assert result == "captured panel"
        mock_console.capture.assert_called_once()