"""
Genesis Debugger and Debug Tools - Phase 4 Developer Capabilities.

Provides comprehensive debugging capabilities for Genesis specifications including:
- Interactive debugging sessions
- Step-by-step execution tracking
- Variable inspection and modification
- Breakpoint management
- Error analysis and recovery
- Integration with Phase 1-3 validation and conversion systems
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable, Union
from dataclasses import dataclass, field
from enum import Enum

import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.tree import Tree

from langflow.services.spec.service import SpecService
from langflow.services.runtime import RuntimeType, ValidationOptions, converter_factory

logger = logging.getLogger(__name__)
console = Console()


class DebugLevel(Enum):
    """Debug verbosity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    TRACE = "trace"


class ExecutionState(Enum):
    """Execution state for debugging."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    STEP = "step"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class DebugBreakpoint:
    """Debug breakpoint definition."""
    id: str
    file_path: str
    line: int
    column: int = 0
    condition: Optional[str] = None
    enabled: bool = True
    hit_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DebugFrame:
    """Debug stack frame."""
    id: str
    name: str
    file_path: str
    line: int
    column: int
    variables: Dict[str, Any] = field(default_factory=dict)
    locals: Dict[str, Any] = field(default_factory=dict)
    scope: str = "local"


@dataclass
class DebugEvent:
    """Debug event record."""
    timestamp: datetime
    event_type: str
    level: DebugLevel
    component_id: Optional[str]
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[List[str]] = None


class DebugSession:
    """
    Interactive debugging session for Genesis specifications.

    Provides comprehensive debugging capabilities with real-time inspection,
    step-by-step execution, and error analysis.
    """

    def __init__(self, session_id: Optional[str] = None, debug_level: DebugLevel = DebugLevel.INFO):
        """
        Initialize debug session.

        Args:
            session_id: Unique session identifier
            debug_level: Debug verbosity level
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.debug_level = debug_level
        self.state = ExecutionState.STOPPED
        self.spec_service = SpecService()

        # Debug state
        self.breakpoints: Dict[str, DebugBreakpoint] = {}
        self.current_frame: Optional[DebugFrame] = None
        self.call_stack: List[DebugFrame] = []
        self.events: List[DebugEvent] = []
        self.variables: Dict[str, Any] = {}
        self.watch_expressions: Dict[str, str] = {}

        # Configuration
        self.auto_continue = False
        self.break_on_error = True
        self.break_on_warning = False
        self.max_events = 1000

        # Callbacks
        self.event_callbacks: List[Callable[[DebugEvent], None]] = []
        self.state_callbacks: List[Callable[[ExecutionState], None]] = []

        # Performance tracking
        self.start_time: Optional[datetime] = None
        self.performance_metrics = {
            "execution_time": 0.0,
            "validation_time": 0.0,
            "conversion_time": 0.0,
            "components_processed": 0,
            "errors_encountered": 0,
            "warnings_generated": 0
        }

        logger.info(f"Debug session {self.session_id} initialized")

    async def debug_specification(
        self,
        spec_path: str,
        target_runtime: RuntimeType = RuntimeType.LANGFLOW,
        watch_expressions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Debug Genesis specification with comprehensive analysis.

        Args:
            spec_path: Path to specification file
            target_runtime: Target runtime for debugging
            watch_expressions: List of expressions to watch

        Returns:
            Debug session results
        """
        try:
            self.start_time = datetime.now(timezone.utc)
            self._set_state(ExecutionState.RUNNING)

            # Load specification
            spec_content = self._load_specification(spec_path)
            if not spec_content:
                await self._log_event("error", "SPEC_LOAD_FAILED", None, f"Failed to load specification: {spec_path}")
                return {"success": False, "error": "Failed to load specification"}

            # Set up watch expressions
            if watch_expressions:
                for i, expr in enumerate(watch_expressions):
                    self.watch_expressions[f"watch_{i}"] = expr

            await self._log_event("info", "DEBUG_STARTED", None, f"Debugging specification: {spec_path}")

            # Phase 1: Parse and validate syntax
            await self._debug_phase("syntax_validation", self._debug_syntax_validation, spec_content)

            # Phase 2: Component analysis
            spec_dict = yaml.safe_load(spec_content)
            await self._debug_phase("component_analysis", self._debug_component_analysis, spec_dict)

            # Phase 3: Validation with enhanced system
            await self._debug_phase("enhanced_validation", self._debug_enhanced_validation, spec_content, target_runtime)

            # Phase 4: Conversion analysis
            await self._debug_phase("conversion_analysis", self._debug_conversion_analysis, spec_content, target_runtime)

            # Phase 5: Performance analysis
            await self._debug_phase("performance_analysis", self._debug_performance_analysis, spec_dict)

            self._set_state(ExecutionState.COMPLETED)
            return await self._generate_debug_report()

        except Exception as e:
            await self._log_event("error", "DEBUG_EXCEPTION", None, f"Debug session failed: {e}")
            self._set_state(ExecutionState.ERROR)
            return {"success": False, "error": str(e), "session_id": self.session_id}

    async def set_breakpoint(
        self,
        file_path: str,
        line: int,
        condition: Optional[str] = None
    ) -> str:
        """
        Set debugging breakpoint.

        Args:
            file_path: File path for breakpoint
            line: Line number (1-based)
            condition: Optional condition expression

        Returns:
            Breakpoint ID
        """
        breakpoint_id = str(uuid.uuid4())
        breakpoint = DebugBreakpoint(
            id=breakpoint_id,
            file_path=file_path,
            line=line,
            condition=condition
        )

        self.breakpoints[breakpoint_id] = breakpoint
        await self._log_event("info", "BREAKPOINT_SET", None, f"Breakpoint set at {file_path}:{line}")

        return breakpoint_id

    async def remove_breakpoint(self, breakpoint_id: str) -> bool:
        """
        Remove debugging breakpoint.

        Args:
            breakpoint_id: Breakpoint identifier

        Returns:
            True if breakpoint was removed
        """
        if breakpoint_id in self.breakpoints:
            del self.breakpoints[breakpoint_id]
            await self._log_event("info", "BREAKPOINT_REMOVED", None, f"Breakpoint {breakpoint_id} removed")
            return True
        return False

    async def step_into(self) -> bool:
        """Step into next operation."""
        if self.state == ExecutionState.PAUSED:
            self._set_state(ExecutionState.STEP)
            await self._log_event("debug", "STEP_INTO", None, "Stepping into next operation")
            return True
        return False

    async def step_over(self) -> bool:
        """Step over current operation."""
        if self.state == ExecutionState.PAUSED:
            self._set_state(ExecutionState.STEP)
            await self._log_event("debug", "STEP_OVER", None, "Stepping over current operation")
            return True
        return False

    async def continue_execution(self) -> bool:
        """Continue execution from current position."""
        if self.state == ExecutionState.PAUSED:
            self._set_state(ExecutionState.RUNNING)
            await self._log_event("debug", "CONTINUE", None, "Continuing execution")
            return True
        return False

    async def pause_execution(self) -> bool:
        """Pause execution at current position."""
        if self.state == ExecutionState.RUNNING:
            self._set_state(ExecutionState.PAUSED)
            await self._log_event("debug", "PAUSE", None, "Execution paused")
            return True
        return False

    def get_current_frame(self) -> Optional[DebugFrame]:
        """Get current execution frame."""
        return self.current_frame

    def get_call_stack(self) -> List[DebugFrame]:
        """Get current call stack."""
        return self.call_stack.copy()

    def get_variables(self, frame_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get variables for frame or session.

        Args:
            frame_id: Frame identifier (current frame if None)

        Returns:
            Dictionary of variables
        """
        if frame_id and self.current_frame and self.current_frame.id == frame_id:
            return self.current_frame.variables.copy()
        return self.variables.copy()

    def evaluate_watch_expression(self, expression: str) -> Any:
        """
        Evaluate watch expression in current context.

        Args:
            expression: Expression to evaluate

        Returns:
            Evaluation result
        """
        try:
            # Simple evaluation in current variable context
            context = {**self.variables}
            if self.current_frame:
                context.update(self.current_frame.variables)

            # Basic expression evaluation (extend as needed)
            if expression in context:
                return context[expression]
            elif "." in expression:
                # Handle dot notation
                parts = expression.split(".")
                value = context.get(parts[0])
                for part in parts[1:]:
                    if hasattr(value, part):
                        value = getattr(value, part)
                    elif isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        return f"<undefined: {expression}>"
                return value
            else:
                return f"<undefined: {expression}>"

        except Exception as e:
            return f"<error: {e}>"

    def get_debug_events(
        self,
        event_type: Optional[str] = None,
        level: Optional[DebugLevel] = None,
        limit: Optional[int] = None
    ) -> List[DebugEvent]:
        """
        Get debug events with optional filtering.

        Args:
            event_type: Filter by event type
            level: Filter by debug level
            limit: Maximum number of events

        Returns:
            List of debug events
        """
        events = self.events

        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if level:
            events = [e for e in events if e.level == level]

        # Apply limit
        if limit:
            events = events[-limit:]

        return events

    def add_event_callback(self, callback: Callable[[DebugEvent], None]) -> None:
        """Add callback for debug events."""
        self.event_callbacks.append(callback)

    def add_state_callback(self, callback: Callable[[ExecutionState], None]) -> None:
        """Add callback for state changes."""
        self.state_callbacks.append(callback)

    # Private methods

    async def _debug_phase(self, phase_name: str, phase_func: Callable, *args) -> Any:
        """Execute debug phase with timing and error handling."""
        start_time = time.time()

        # Create debug frame
        frame = DebugFrame(
            id=str(uuid.uuid4()),
            name=phase_name,
            file_path="<debug_session>",
            line=0,
            column=0
        )

        self._push_frame(frame)

        try:
            await self._log_event("debug", "PHASE_START", None, f"Starting phase: {phase_name}")
            result = await phase_func(*args)

            duration = time.time() - start_time
            await self._log_event("debug", "PHASE_COMPLETE", None, f"Phase {phase_name} completed in {duration:.3f}s")

            return result

        except Exception as e:
            duration = time.time() - start_time
            await self._log_event("error", "PHASE_ERROR", None, f"Phase {phase_name} failed after {duration:.3f}s: {e}")
            if self.break_on_error:
                self._set_state(ExecutionState.PAUSED)
            raise
        finally:
            self._pop_frame()

    async def _debug_syntax_validation(self, spec_content: str) -> Dict[str, Any]:
        """Debug syntax validation phase."""
        try:
            # Parse YAML
            spec_dict = yaml.safe_load(spec_content)
            await self._log_event("info", "YAML_PARSE_SUCCESS", None, "YAML parsing successful")

            # Basic structure validation
            required_fields = ["name", "description", "agentGoal", "components"]
            missing_fields = [field for field in required_fields if field not in spec_dict]

            if missing_fields:
                await self._log_event("warning", "MISSING_FIELDS", None, f"Missing required fields: {missing_fields}")
                if self.break_on_warning:
                    self._set_state(ExecutionState.PAUSED)

            self.variables["spec_dict"] = spec_dict
            self.variables["missing_fields"] = missing_fields

            return {
                "valid": len(missing_fields) == 0,
                "missing_fields": missing_fields,
                "parsed_structure": spec_dict
            }

        except yaml.YAMLError as e:
            await self._log_event("error", "YAML_PARSE_ERROR", None, f"YAML parsing failed: {e}")
            raise

    async def _debug_component_analysis(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Debug component analysis phase."""
        components = spec_dict.get("components", {})

        analysis = {
            "component_count": len(components),
            "component_types": {},
            "connections": [],
            "orphaned_components": [],
            "tool_components": []
        }

        # Analyze each component
        for comp_id, comp_data in components.items():
            comp_type = comp_data.get("type", "unknown")

            # Count component types
            if comp_type not in analysis["component_types"]:
                analysis["component_types"][comp_type] = 0
            analysis["component_types"][comp_type] += 1

            # Check tool components
            if comp_data.get("asTools", False):
                analysis["tool_components"].append(comp_id)

            # Analyze connections
            provides = comp_data.get("provides", [])
            for connection in provides:
                if isinstance(connection, dict):
                    analysis["connections"].append({
                        "from": comp_id,
                        "to": connection.get("in"),
                        "type": connection.get("useAs")
                    })

        # Find orphaned components
        connected_components = set()
        for conn in analysis["connections"]:
            connected_components.add(conn["from"])
            if conn["to"]:
                connected_components.add(conn["to"])

        for comp_id in components.keys():
            if comp_id not in connected_components:
                analysis["orphaned_components"].append(comp_id)

        # Log findings
        await self._log_event("info", "COMPONENT_ANALYSIS", None,
                            f"Analyzed {analysis['component_count']} components")

        if analysis["orphaned_components"]:
            await self._log_event("warning", "ORPHANED_COMPONENTS", None,
                                f"Found orphaned components: {analysis['orphaned_components']}")

        self.variables["component_analysis"] = analysis
        self.performance_metrics["components_processed"] = analysis["component_count"]

        return analysis

    async def _debug_enhanced_validation(self, spec_content: str, target_runtime: RuntimeType) -> Dict[str, Any]:
        """Debug enhanced validation phase."""
        start_time = time.time()

        # Use Phase 3 enhanced validation
        validation_result = await self.spec_service.validate_spec_with_runtime(
            spec_content,
            target_runtime,
            ValidationOptions(
                strict_mode=True,
                performance_checks=True,
                detailed_errors=True
            )
        )

        validation_time = time.time() - start_time
        self.performance_metrics["validation_time"] = validation_time

        # Process validation results
        errors = validation_result.get("errors", [])
        warnings = validation_result.get("warnings", [])

        for error in errors:
            await self._log_event("error", "VALIDATION_ERROR",
                                error.get("component_id"), str(error))
            self.performance_metrics["errors_encountered"] += 1

        for warning in warnings:
            await self._log_event("warning", "VALIDATION_WARNING",
                                warning.get("component_id"), str(warning))
            self.performance_metrics["warnings_generated"] += 1

        self.variables["validation_result"] = validation_result

        await self._log_event("info", "VALIDATION_COMPLETE", None,
                            f"Validation completed in {validation_time:.3f}s")

        return validation_result

    async def _debug_conversion_analysis(self, spec_content: str, target_runtime: RuntimeType) -> Dict[str, Any]:
        """Debug conversion analysis phase."""
        start_time = time.time()

        try:
            # Use Phase 3 enhanced conversion
            conversion_result = await self.spec_service.convert_spec_to_flow_enhanced(
                spec_content,
                target_runtime=target_runtime,
                optimization_level="balanced"
            )

            conversion_time = time.time() - start_time
            self.performance_metrics["conversion_time"] = conversion_time

            if conversion_result.get("success", False):
                await self._log_event("info", "CONVERSION_SUCCESS", None,
                                    f"Conversion completed in {conversion_time:.3f}s")
            else:
                await self._log_event("error", "CONVERSION_FAILED", None,
                                    f"Conversion failed after {conversion_time:.3f}s")

            self.variables["conversion_result"] = conversion_result
            return conversion_result

        except Exception as e:
            conversion_time = time.time() - start_time
            await self._log_event("error", "CONVERSION_EXCEPTION", None,
                                f"Conversion failed with exception after {conversion_time:.3f}s: {e}")
            raise

    async def _debug_performance_analysis(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Debug performance analysis phase."""
        analysis = {
            "complexity_score": 0,
            "performance_issues": [],
            "optimization_suggestions": []
        }

        components = spec_dict.get("components", {})

        # Calculate complexity score
        component_count = len(components)
        edge_count = sum(len(comp.get("provides", [])) for comp in components.values())

        analysis["complexity_score"] = component_count * 2 + edge_count

        # Check for performance issues
        if component_count > 10:
            analysis["performance_issues"].append("High component count may impact performance")
            analysis["optimization_suggestions"].append("Consider breaking down into smaller workflows")

        if edge_count > 20:
            analysis["performance_issues"].append("Complex connection patterns detected")
            analysis["optimization_suggestions"].append("Review component relationships for optimization")

        # Check for multi-agent complexity
        agent_count = sum(1 for comp in components.values()
                         if comp.get("type", "").endswith("agent"))

        if agent_count > 5:
            analysis["performance_issues"].append("High agent count may cause coordination overhead")
            analysis["optimization_suggestions"].append("Consider hierarchical agent patterns")

        await self._log_event("info", "PERFORMANCE_ANALYSIS", None,
                            f"Performance analysis complete. Complexity score: {analysis['complexity_score']}")

        for issue in analysis["performance_issues"]:
            await self._log_event("warning", "PERFORMANCE_ISSUE", None, issue)

        self.variables["performance_analysis"] = analysis
        return analysis

    def _load_specification(self, spec_path: str) -> Optional[str]:
        """Load specification content from file."""
        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading specification: {e}")
            return None

    async def _log_event(
        self,
        level: str,
        event_type: str,
        component_id: Optional[str],
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log debug event."""
        event = DebugEvent(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            level=DebugLevel(level),
            component_id=component_id,
            message=message,
            data=data or {}
        )

        self.events.append(event)

        # Trim events if too many
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

        # Call event callbacks
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Error in event callback: {e}")

    def _set_state(self, new_state: ExecutionState) -> None:
        """Set execution state and notify callbacks."""
        old_state = self.state
        self.state = new_state

        if old_state != new_state:
            # Call state callbacks
            for callback in self.state_callbacks:
                try:
                    callback(new_state)
                except Exception as e:
                    logger.warning(f"Error in state callback: {e}")

    def _push_frame(self, frame: DebugFrame) -> None:
        """Push frame onto call stack."""
        self.call_stack.append(frame)
        self.current_frame = frame

    def _pop_frame(self) -> Optional[DebugFrame]:
        """Pop frame from call stack."""
        if self.call_stack:
            frame = self.call_stack.pop()
            self.current_frame = self.call_stack[-1] if self.call_stack else None
            return frame
        return None

    async def _generate_debug_report(self) -> Dict[str, Any]:
        """Generate comprehensive debug report."""
        end_time = datetime.now(timezone.utc)
        execution_time = (end_time - self.start_time).total_seconds() if self.start_time else 0

        self.performance_metrics["execution_time"] = execution_time

        report = {
            "session_id": self.session_id,
            "success": self.state == ExecutionState.COMPLETED,
            "execution_time": execution_time,
            "state": self.state.value,
            "performance_metrics": self.performance_metrics,
            "events_summary": {
                "total_events": len(self.events),
                "errors": len([e for e in self.events if e.level == DebugLevel.ERROR]),
                "warnings": len([e for e in self.events if e.level == DebugLevel.WARNING]),
                "info": len([e for e in self.events if e.level == DebugLevel.INFO])
            },
            "variables": self.variables,
            "watch_expressions": {
                name: self.evaluate_watch_expression(expr)
                for name, expr in self.watch_expressions.items()
            },
            "breakpoints": [
                {
                    "id": bp.id,
                    "file_path": bp.file_path,
                    "line": bp.line,
                    "hit_count": bp.hit_count,
                    "enabled": bp.enabled
                }
                for bp in self.breakpoints.values()
            ]
        }

        return report


class GenesisDebugger:
    """
    Main debugger interface for Genesis specifications.

    Provides high-level debugging operations and session management.
    """

    def __init__(self):
        """Initialize Genesis debugger."""
        self.active_sessions: Dict[str, DebugSession] = {}
        self.session_history: List[Dict[str, Any]] = []

    async def create_debug_session(
        self,
        debug_level: DebugLevel = DebugLevel.INFO
    ) -> DebugSession:
        """
        Create new debug session.

        Args:
            debug_level: Debug verbosity level

        Returns:
            New debug session
        """
        session = DebugSession(debug_level=debug_level)
        self.active_sessions[session.session_id] = session

        logger.info(f"Created debug session: {session.session_id}")
        return session

    async def debug_specification_file(
        self,
        spec_path: str,
        target_runtime: RuntimeType = RuntimeType.LANGFLOW,
        debug_level: DebugLevel = DebugLevel.INFO,
        watch_expressions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Debug specification file with comprehensive analysis.

        Args:
            spec_path: Path to specification file
            target_runtime: Target runtime for debugging
            debug_level: Debug verbosity level
            watch_expressions: List of expressions to watch

        Returns:
            Debug results
        """
        session = await self.create_debug_session(debug_level)

        try:
            result = await session.debug_specification(
                spec_path, target_runtime, watch_expressions
            )

            # Store session history
            self.session_history.append({
                "session_id": session.session_id,
                "spec_path": spec_path,
                "target_runtime": target_runtime.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": result.get("success", False)
            })

            return result

        finally:
            # Clean up session
            if session.session_id in self.active_sessions:
                del self.active_sessions[session.session_id]

    def get_active_sessions(self) -> List[str]:
        """Get list of active debug session IDs."""
        return list(self.active_sessions.keys())

    def get_session(self, session_id: str) -> Optional[DebugSession]:
        """Get debug session by ID."""
        return self.active_sessions.get(session_id)

    def get_session_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get debug session history.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session history entries
        """
        history = self.session_history
        if limit:
            history = history[-limit:]
        return history

    async def cleanup_sessions(self) -> int:
        """
        Clean up inactive debug sessions.

        Returns:
            Number of sessions cleaned up
        """
        inactive_sessions = []

        for session_id, session in self.active_sessions.items():
            if session.state in [ExecutionState.COMPLETED, ExecutionState.ERROR]:
                inactive_sessions.append(session_id)

        for session_id in inactive_sessions:
            del self.active_sessions[session_id]

        logger.info(f"Cleaned up {len(inactive_sessions)} inactive debug sessions")
        return len(inactive_sessions)


# Convenience functions

async def create_debug_session(debug_level: DebugLevel = DebugLevel.INFO) -> DebugSession:
    """
    Create new debug session.

    Args:
        debug_level: Debug verbosity level

    Returns:
        New debug session
    """
    return DebugSession(debug_level=debug_level)


async def debug_genesis_spec(
    spec_path: str,
    target_runtime: RuntimeType = RuntimeType.LANGFLOW,
    debug_level: DebugLevel = DebugLevel.INFO,
    watch_expressions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Debug Genesis specification file (convenience function).

    Args:
        spec_path: Path to specification file
        target_runtime: Target runtime for debugging
        debug_level: Debug verbosity level
        watch_expressions: List of expressions to watch

    Returns:
        Debug results
    """
    debugger = GenesisDebugger()
    return await debugger.debug_specification_file(
        spec_path, target_runtime, debug_level, watch_expressions
    )


if __name__ == "__main__":
    async def main():
        """Example usage of Genesis debugger."""
        # Create debugger
        debugger = GenesisDebugger()

        # Debug a specification file
        result = await debugger.debug_specification_file(
            "example.genesis.yaml",
            target_runtime=RuntimeType.LANGFLOW,
            debug_level=DebugLevel.DEBUG,
            watch_expressions=["component_analysis.component_count", "validation_result.valid"]
        )

        console.print("Debug Results:")
        console.print(json.dumps(result, indent=2, default=str))

    # Run example
    asyncio.run(main())