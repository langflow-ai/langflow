"""Graph Execution Debugging with Marimo.

Run with: marimo edit debug_graph_marimo.py
"""

# ruff: noqa: N806, N803, B018, PLR2004

import marimo

__generated_with = "0.17.0"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    mo.md(
        """
        # Graph Execution Debugging Tool

        Interactive debugging for Langflow graph execution with:
        - **Trace graphs** - See execution details, state deltas, loop progression
        - **Time-travel debugging** - Record once, jump to any point
        - **Compare paths** - Validate both execution methods match

        ## Quick Start

        1. Choose a flow from the dropdown
        2. Select what to do (trace, record, or compare)
        3. Explore the results interactively
        """
    )
    return (mo,)


@app.cell
def _():
    # Available test flows
    TEST_FLOWS = {
        "LoopTest": "src/backend/tests/data/LoopTest.json",
        "Loop with CSV": "src/backend/tests/data/loop_csv_test.json",
        "Memory Chatbot": "src/backend/tests/data/MemoryChatbotNoLLM.json",
    }
    return (TEST_FLOWS,)


@app.cell
def _(TEST_FLOWS, mo):
    # Flow selection
    flow_selector = mo.ui.dropdown(options=list(TEST_FLOWS.keys()), value="LoopTest", label="Select Flow:")

    action_selector = mo.ui.dropdown(
        options=["Trace", "Record & Navigate", "Compare Paths"], value="Trace", label="Action:"
    )

    mo.md(f"""
    ## Configuration

    {flow_selector}

    {action_selector}
    """)
    return action_selector, flow_selector


@app.cell
async def _(TEST_FLOWS, action_selector, flow_selector, mo):
    # Execute based on selection
    selected_flow = TEST_FLOWS[flow_selector.value]

    if action_selector.value == "Trace":
        from lfx.debug.tracer import trace_graph

        trace = await trace_graph(selected_flow, method="async_start", show=False)

        # Display summary
        summary = mo.md(f"""
        ## Trace Results: {flow_selector.value}

        - **Components executed:** {len(set(trace.vertices_executed))}
        - **Total executions:** {len(trace.vertices_executed)}
        - **State changes:** {len(trace.state_deltas)}
        - **Loops detected:** {len(trace.loop_iterations)}
        - **Error:** {trace.error or "None"}
        """)

        # Execution order
        exec_order = trace.execution_order[:20]
        order_display = "\n".join(
            [f"{step}. {vid.split('-')[0]} (run #{count})" for step, (vid, count) in enumerate(exec_order, 1)]
        )

        details = mo.md(f"""
    ### Execution Order (first 20)

    {order_display}
    """)

        result = mo.vstack([summary, details])

    elif action_selector.value == "Record & Navigate":
        result = mo.md("**Recording functionality - see below**")

    else:  # Compare Paths
        from lfx.debug.tracer import compare_paths

        comparison = await compare_paths(selected_flow)

        comp_display = mo.md(f"""
        ## Path Comparison: {flow_selector.value}

        ### Async_start
        - Components: {comparison["async_start"]["components"]}
        - Executions: {comparison["async_start"]["total_executions"]}
        - Loops: {comparison["async_start"]["loops"]}
        - Error: {comparison["async_start"]["error"] or "None"}

        ### Arun
        - Components: {comparison["arun"]["components"]}
        - Executions: {comparison["arun"]["total_executions"]}
        - Loops: {comparison["arun"]["loops"]}
        - Error: {comparison["arun"]["error"] or "None"}

        ### Result
        {"✅ **Identical execution!**" if comparison["async_start"] == comparison["arun"] else "⚠️ **Paths differ!**"}
        """)

        result = comp_display

    result


@app.cell
def _(mo):
    mo.md(
        """
    ---
    ## Time-Travel Debugging

    Record a flow and navigate through its execution timeline.
    """
    )


@app.cell
def _():
    return


@app.cell
def _(mo):
    # Recording section
    record_button = mo.ui.button(label="📼 Record Flow", on_click=lambda _value: 1)

    mo.md(f"""
    {record_button}
    """)
    return (record_button,)


@app.cell
def _(mo, record_button):
    mo.md(f"""{record_button.value!r}""")


@app.cell
async def _(TEST_FLOWS, flow_selector, mo, record_button):
    # Initialize recording if button clicked
    recording = None
    if record_button.value:
        from lfx.debug.recorder import record_graph

        _selected_flow = TEST_FLOWS[flow_selector.value]

        recording = await record_graph(_selected_flow)
    else:
        mo.md(f"Recording value: {record_button.value}")
    return (recording,)


@app.cell
def _(current_pos, mo, recording):
    def _():
        if recording is None:
            result = mo.md("*Click 'Record Flow' to start*")
        else:
            # Timeline display
            timeline_lines = []
            for _i, _snap in enumerate(recording.snapshots[:30]):
                _short_id = _snap.vertex_id.split("-")[0]
                marker = "👉" if _i == current_pos else "  "
                status = "❌" if _snap.error else "✅"
                timeline_lines.append(f"{marker} [{_i:3d}] {status} {_short_id}")

            if len(recording.snapshots) > 30:
                timeline_lines.append(f"... and {len(recording.snapshots) - 30} more")

            timeline_text = "\n".join(timeline_lines)

            result = mo.vstack(
                [
                    mo.md(f"""
    ## Recording Timeline

    Total steps: {len(recording.snapshots)}
    Current position: {current_pos}
    """),
                    mo.plain_text(timeline_text),
                ]
            )
        return result

    _()


@app.cell
def _(mo, recording):
    def show_navigation():
        if recording is not None:
            max_step = len(recording.snapshots) - 1

            # Slider to pick a step
            step_slider = mo.ui.slider(start=0, stop=max_step, value=0, label="🔢 Jump to step")

            # Dropdown to pick a component by name
            component_names = sorted({snap.vertex_id.split("-")[0] for snap in recording.snapshots})
            component_selector = mo.ui.dropdown(options=["", *component_names], value="", label="📦 Jump to component")

            # Display
            display = mo.vstack([mo.md("## Navigation"), step_slider, component_selector])

            return component_selector, step_slider, display

        return None, None, mo.md("*Record a flow to enable navigation controls*")

    component_selector, step_slider, nav_display = show_navigation()
    nav_display
    return component_selector, step_slider


@app.cell
def _(component_selector, recording, step_slider):
    # ── Compute current position reactively from UI ──

    # Default if no recording yet
    if recording is None:
        current_pos = 0

    else:
        # 1) start with slider.value if the slider exists
        current_pos = step_slider.value if step_slider is not None else 0

        # 2) override with component selector if a non-empty .value was picked
        if (component_selector is not None) and component_selector.value:
            # find first snapshot whose id contains the selected name
            for idx, snap in enumerate(recording.snapshots):
                if component_selector.value in snap.vertex_id:
                    current_pos = idx
                    break

    current_pos  # reactively display the chosen step
    return (current_pos,)


@app.cell
def _(current_pos, mo, recording):
    def show_current_state():
        if recording is not None:
            # Show current state
            current_snapshot = recording.snapshots[current_pos]
            current_short_id = current_snapshot.vertex_id.split("-")[0]

            # Format inputs
            input_items = list(current_snapshot.inputs.items())[:5]
            inputs_display = "\n".join([f"- **{k}**: {str(v)[:80]}..." for k, v in input_items])

            # Format queue
            queue_display = ", ".join([v.split("-")[0] for v in current_snapshot.queue_state_after[:10]])
            queue_len = len(current_snapshot.queue_state_after)
            queue_more = f"... and {queue_len - 10} more" if queue_len > 10 else ""

            return mo.md(f"""
## Current State: {current_short_id}

**Step:** {current_pos}
**Component:** {current_snapshot.vertex_id}

### Inputs
{inputs_display}

### Queue
{queue_display}
{queue_more}

### Context
- Has {len(current_snapshot.context)} context keys
""")
        return mo.md("")

    show_current_state()


@app.cell
def _(current_pos, mo, recording):
    def show_state_deltas():
        if recording is not None and current_pos < len(recording.snapshots):
            current_snap = recording.snapshots[current_pos]

            # Use the built-in get_delta() method!
            delta = current_snap.get_delta()

            delta_lines = []
            comp_name = current_snap.vertex_id.split("-")[0]
            delta_lines.append(f"🎯 {comp_name}\n")

            # Show queue changes (happens on almost every component)
            if "queue" in delta:
                q = delta["queue"]
                if q["added"]:
                    added_items = [v.split("-")[0] for v in q["added"]]
                    delta_lines.append(f"  + Queued: {added_items}")
                if q["removed"]:
                    removed_items = [v.split("-")[0] for v in q["removed"]]
                    delta_lines.append(f"  - Dequeued: {removed_items}")

            # Show run_predecessors changes (rare - only when component modifies deps)
            if "run_predecessors" in delta:
                delta_lines.append("\n  Dependencies changed:")
                for k, change in delta["run_predecessors"].items():
                    short_k = k.split("-")[0]
                    if change["added"]:
                        added_deps = [v.split("-")[0] for v in change["added"]]
                        delta_lines.append(f"    ✅ {short_k} now waits for: {added_deps}")
                    if change["removed"]:
                        removed_deps = [v.split("-")[0] for v in change["removed"]]
                        delta_lines.append(f"    ❌ {short_k} no longer waits for: {removed_deps}")

            # Show run_map changes (rare - only when component modifies deps)
            if "run_map" in delta:
                delta_lines.append("\n  Dependents changed:")
                for k, change in delta["run_map"].items():
                    short_k = k.split("-")[0]
                    if change["added"]:
                        added_deps = [v.split("-")[0] for v in change["added"]]
                        delta_lines.append(f"    📌 {short_k} gained dependents: {added_deps}")
                    if change["removed"]:
                        removed_deps = [v.split("-")[0] for v in change["removed"]]
                        delta_lines.append(f"    🔓 {short_k} lost dependents: {removed_deps}")

            delta_text = "\n".join(delta_lines) if delta_lines else "  (no changes)"

            return mo.vstack([mo.md("## What Changed This Step"), mo.plain_text(delta_text)])

        return mo.md("")

    show_state_deltas()


@app.cell
def _(mo, recording):
    def show_loop_analysis():
        if recording is not None and len(recording.snapshots) > 0:
            # Loop analysis if loops exist
            loop_steps = [(i, s) for i, s in enumerate(recording.snapshots) if "Loop" in s.vertex_id]

            if loop_steps:
                loop_data = []
                for _loop_i, (_step, _snap) in enumerate(loop_steps[:10]):
                    loop_id = _snap.vertex_id
                    ctx = _snap.context
                    index = ctx.get(f"{loop_id}_index", "?")
                    aggregated = len(ctx.get(f"{loop_id}_aggregated", []))
                    loop_data.append(f"Iteration {_loop_i} (step {_step}): index={index}, aggregated={aggregated}")

                loop_display = "\n".join(loop_data)

                return mo.vstack(
                    [mo.md(f"## Loop Analysis\n\nFound {len(loop_steps)} loop iterations"), mo.plain_text(loop_display)]
                )

            return mo.md("*No loops in this flow*")

        return mo.md("")

    show_loop_analysis()


@app.cell
def _(mo):
    mo.md(
        """
    ---

    ## How to Use

    ### Tracing
    1. Select "Trace" action
    2. Choose a flow
    3. See execution summary and order

    ### Time-Travel
    1. Select "Record & Navigate"
    2. Click "Record Flow"
    3. Use navigation controls to jump around
    4. Inspect state at any point

    ### Comparison
    1. Select "Compare Paths"
    2. See if both execution methods match

    ## Keyboard Shortcuts
    - Use arrow keys in jump input to navigate
    - Or click Previous/Next buttons
    - Or select component from dropdown
    """
    )


if __name__ == "__main__":
    app.run()
