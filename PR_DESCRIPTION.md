# Graph Execution Debugging and Event System

## Overview

This PR introduces a comprehensive event-based debugging system for Langflow graph execution, enabling detailed tracking and analysis of graph state mutations during execution. The implementation uses a pure observer pattern that provides zero overhead when not in use, making it production-safe.

## Key Features

### 🎯 Graph Mutation Event System

- **Event Infrastructure**: New `GraphMutationEvent` system that tracks all graph state changes with before/after snapshots
- **Observer Pattern**: Pure observer pattern implementation with `register_observer()` and `unregister_observer()` methods
- **Zero Overhead**: Fast path when no observers are registered, ensuring no performance impact in production
- **Serializable Events**: Events can be serialized to dictionaries for replay and storage

### 📊 Event-Based Recording

- **EventRecorder**: Observer that captures all graph mutations during execution
- **EventBasedRecording**: Rich recording object with analysis methods:
  - `get_events_by_type()` - Filter events by type
  - `get_events_for_vertex()` - Get all events for a specific vertex
  - `get_queue_evolution()` - Track how the execution queue changes over time
  - `get_dependency_changes()` - Monitor dependency modifications
  - `show_summary()`, `show_timeline()`, `show_events_for_component()` - Visualization methods
- **Save/Load**: Recordings can be saved to and loaded from files for later analysis

### 🔧 Graph Execution Improvements

#### Loop Component Enhancements
- **Synchronized Dependencies**: Loop component now properly updates both `run_predecessors` and `run_map` to keep dependency structures synchronized
- **State Reset**: New `reset_loop_state()` method for clean loop state management between executions
- **Better Documentation**: Added critical comments explaining the relationship between dependency structures

#### Graph Manager Refactoring
- **Async Methods**: Made `remove_from_predecessors()` and `remove_vertex_from_runnables()` async for consistency
- **Sync Variants**: Added `mark_branch_sync()` for synchronous contexts (used by custom components)
- **Centralized Mutations**: All graph mutations now go through centralized methods that emit events

### 🧪 Testing Infrastructure

#### Execution Path Validation
- **Path Equivalence Testing**: New test suite that validates both `async_start()` and `arun()` execution paths produce identical results
- **Test Data Flows**: Uses test flows that don't require API keys for reliable CI testing
- **Comprehensive Tracing**: `ExecutionTracer` captures complete execution traces for comparison

#### Event System Tests
- **Mutation Event Tests**: Tests for queue operations, dependency updates, and event emission
- **Event Recorder Tests**: Tests for event capture, queue evolution tracking, and recording analysis
- **Graph Mutation Tests**: Tests ensuring both dependency structures stay synchronized

### 🛠️ Component Validation Improvements

- **TYPE_CHECKING Block Support**: Component validation now properly handles `TYPE_CHECKING` blocks, extracting imports needed for `get_type_hints()` to work correctly
- **Better Error Handling**: Improved error handling for components defined in notebooks or REPL environments
- **Source Code Extraction**: More robust source code extraction with graceful fallbacks

## Technical Details

### Event Types Tracked

- `queue_extended` - When vertices are added to the execution queue
- `queue_dequeued` - When vertices are removed from the queue
- `dependency_added` - When dynamic dependencies are added
- `vertex_marked` - When vertex states change (ACTIVE/INACTIVE)

### Architecture

```
Graph
  ├── register_observer() / unregister_observer()
  ├── _emit_event() - Emits events to all observers
  └── All mutations → emit before/after events
       ├── extend_run_queue()
       ├── add_dynamic_dependency()
       ├── mark_branch_sync()
       └── remove_from_predecessors()
```

### Usage Example

```python
from lfx.graph.graph.base import Graph
from lfx.debug.event_recorder import record_graph_with_events

# Record graph execution
graph = Graph.from_payload(flow_data)
recording = await record_graph_with_events(graph, "My Flow")

# Analyze the recording
recording.show_summary()
recording.show_timeline()

# Get specific insights
queue_evolution = recording.get_queue_evolution()
dependency_changes = recording.get_dependency_changes()

# Save for later analysis
recording.save("flow_recording.pkl")
```

## Files Changed

### New Files
- `src/lfx/src/lfx/debug/__init__.py` - Debug module initialization
- `src/lfx/src/lfx/debug/events.py` - GraphMutationEvent and observer types
- `src/lfx/src/lfx/debug/event_recorder.py` - EventRecorder and EventBasedRecording
- `src/backend/tests/unit/graph/test_execution_path_validation.py` - Execution path equivalence tests
- `src/backend/tests/unit/graph/test_execution_path_equivalence.py` - Execution tracing utilities
- `src/backend/tests/unit/graph/test_event_recorder.py` - Event recorder tests
- `src/backend/tests/unit/graph/test_graph_mutation_events.py` - Mutation event tests

### Modified Files
- `src/lfx/src/lfx/graph/graph/base.py` - Added observer pattern, event emission
- `src/lfx/src/lfx/graph/graph/runnable_vertices_manager.py` - Made methods async
- `src/lfx/src/lfx/components/logic/loop.py` - Improved dependency synchronization
- `src/lfx/src/lfx/custom/custom_component/component.py` - Better error handling
- `src/lfx/src/lfx/custom/custom_component/custom_component.py` - Use mark_branch_sync
- `src/lfx/src/lfx/custom/validate.py` - TYPE_CHECKING block support
- `pyproject.toml` - Added marimo dependency for debugging notebooks

## Benefits

1. **Debugging**: Comprehensive visibility into graph execution state changes
2. **Testing**: Better test coverage with execution path validation
3. **Reliability**: Synchronized dependency structures prevent bugs
4. **Performance**: Zero overhead when debugging is not active
5. **Extensibility**: Easy to add new event types and observers

## Testing

- ✅ All existing tests pass
- ✅ New execution path validation tests pass
- ✅ Event system tests pass
- ✅ Loop component tests pass with improved dependency handling

## Breaking Changes

None - This is a purely additive change. The event system is opt-in and has zero overhead when not used.

## Future Work

- [ ] Add more event types (vertex execution start/end, memory updates, etc.)
- [ ] Create visualization tools for event recordings
- [ ] Add event filtering and querying capabilities
- [ ] Integrate with Langflow UI for real-time debugging

