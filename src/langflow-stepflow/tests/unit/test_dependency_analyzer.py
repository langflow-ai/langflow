"""Unit tests for DependencyAnalyzer."""

import pytest

from langflow_stepflow.translation.dependency_analyzer import (
    DependencyAnalyzer,
)


class TestDependencyAnalyzer:
    """Test DependencyAnalyzer functionality."""

    def test_build_empty_dependency_graph(self):
        """Test building dependency graph from empty edges."""
        analyzer = DependencyAnalyzer()
        dependencies = analyzer.build_dependency_graph([])
        assert dependencies == {}

    def test_build_simple_dependency_graph(self):
        """Test building dependency graph from simple edges."""
        analyzer = DependencyAnalyzer()
        edges = [
            {"source": "A", "target": "B"},
            {"source": "B", "target": "C"},
        ]

        dependencies = analyzer.build_dependency_graph(edges)

        assert dependencies == {"B": ["A"], "C": ["B"]}

    def test_build_complex_dependency_graph(self):
        """Test building dependency graph with multiple sources."""
        analyzer = DependencyAnalyzer()
        edges = [
            {"source": "A", "target": "C"},
            {"source": "B", "target": "C"},
            {"source": "C", "target": "D"},
        ]

        dependencies = analyzer.build_dependency_graph(edges)

        assert dependencies == {"C": ["A", "B"], "D": ["C"]}

    def test_get_execution_order_simple(self):
        """Test execution order for simple dependency chain."""
        analyzer = DependencyAnalyzer()
        dependencies = {"B": ["A"], "C": ["B"]}

        order = analyzer.get_execution_order(dependencies)
        assert order == ["A", "B", "C"]

    def test_get_execution_order_complex(self):
        """Test execution order for complex dependency graph."""
        analyzer = DependencyAnalyzer()
        dependencies = {"C": ["A", "B"], "D": ["C"], "E": ["B"]}

        order = analyzer.get_execution_order(dependencies)

        # A and B should come before C
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("C")

        # C should come before D
        assert order.index("C") < order.index("D")

        # B should come before E
        assert order.index("B") < order.index("E")

        # All nodes should be present
        assert set(order) == {"A", "B", "C", "D", "E"}

    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies."""
        analyzer = DependencyAnalyzer()
        dependencies = {"A": ["B"], "B": ["C"], "C": ["A"]}  # Circular!

        with pytest.raises(ValueError, match="Circular dependencies detected"):
            analyzer.get_execution_order(dependencies)
