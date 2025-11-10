# Graph Execution Debugging and Event System

## Summary

Introduces a comprehensive event-based debugging system for Langflow graph execution with zero overhead when not in use. Uses a pure observer pattern to track all graph state mutations during execution.

## Key Changes

### 🎯 Event System
- New `GraphMutationEvent` system tracking all graph state changes
- Observer pattern with `register_observer()` / `unregister_observer()`
- Zero overhead fast path when no observers registered
- Serializable events for replay and analysis

### 📊 Event Recording
- `EventRecorder` captures all graph mutations
- `EventBasedRecording` with analysis methods (queue evolution, dependency changes, etc.)
- Save/load recordings for later analysis

### 🔧 Graph Improvements
- **Loop Component**: Synchronized `run_predecessors` and `run_map` dependencies
- **Graph Manager**: Made `remove_from_predecessors()` async, added `mark_branch_sync()` for sync contexts
- **Component Validation**: Better `TYPE_CHECKING` block handling

### 🧪 Testing
- Execution path validation tests (`async_start()` vs `arun()` equivalence)
- Event system tests
- Comprehensive test coverage

## Usage

```python
from lfx.debug.event_recorder import record_graph_with_events

recording = await record_graph_with_events(graph, "My Flow")
recording.show_summary()
recording.get_queue_evolution()
recording.save("recording.pkl")
```

## Breaking Changes

None - purely additive, opt-in feature.

