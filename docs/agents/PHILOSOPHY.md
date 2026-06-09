# Project Philosophy

Read this file before scoping any non-trivial work. Most off-narrative work comes from skipping it.

Langflow is a **visual flow builder first**. Every change should make sense to someone whose only interface is dragging nodes onto a canvas. Use these principles to scope work; if a proposed change fails one of them, stop and reconsider.

## Tenets

1. **Flows are user artifacts, not implementation details.** Flow JSON lives in users' databases and runs in production. Backwards compatibility for components is non-negotiable: never rename a class name, `name` attribute, input name, or output name; never remove an input or output; never tighten an output type; never remove methods from base classes like `LCModelComponent`. To change a component, add the new one alongside, set `legacy=True` + `replacement=[...]` on the old, and update `file_names_mapping` in tests so saved flows still load. See [CONTRACTS.md](./CONTRACTS.md) for the full surface.

2. **Every backend feature must land on the canvas.** If a capability cannot be expressed as a component (or a property of one) that a non-Python user can wire up, it is an SDK feature and belongs in `lfx`, not `langflow-base`. Backend changes that have no visual surface are almost always off-narrative.

3. **Components are the unit of work, not endpoints or services.** Before adding a route, store, or service, ask: which component does this serve? If the answer is "none yet," the route is premature. New REST endpoints without a component or UI consumer are off-narrative.

4. **`lfx` is the runtime, `langflow-base` is the platform, `langflow` is the distribution.** Components and the graph engine live in `lfx` (`src/lfx/src/lfx/components/`). API, auth, persistence, and multi-user concerns live in `langflow-base`. The `langflow` package is the integration that ships everything together. New code goes in the lowest layer that can host it. Boundaries are enforced one-way: `langflow` → `langflow-base` → `lfx`. See [ARCHITECTURE.md](./ARCHITECTURE.md).

5. **Don't add a config flag for something a builder-user would set on a node.** If a setting affects flow behavior, it's a component input. If it affects deployment, it's an env var. Hidden global flags that change component semantics break the visible-data-flow contract.

6. **Visible data flow beats clever magic.** Implicit context, hidden globals, and side-channel state make flows unreadable on the canvas. Pass data through inputs and outputs. If you find yourself reaching for a global, you're probably building something that doesn't belong in a node.

7. **Composition over capability.** Prefer adding small, single-purpose components users can wire together over one large component with many modes. The `If-Else` / `Current Date` style (one job, clear name, obvious icon) is the target shape.

8. **Every component needs `display_name`, `description`, `icon`, and a sensible category.** A component that doesn't render legibly in the sidebar shouldn't ship. The icon is part of the API, not decoration — pick a Lucide icon that matches the verb.

9. **The Playground is the test harness builder-users see.** A component is "done" when it works end-to-end in a flow on the canvas, not when its unit test passes. Use the Graph test pattern (build, `.set()`, `async_start`, validate) before claiming a feature works.

10. **Two audiences, one product: visual builders and Python devs.** When their needs conflict, the visual builder wins for `langflow-base` features and the Python dev wins for `lfx` SDK features. Don't compromise the canvas to make the SDK prettier, and don't compromise the SDK to make the canvas easier.

11. **It is not a fix if you didn't have evidence of the change fixing something.** Adding error handling, retries, type widening, or skipping a flaky test does not constitute a fix. Reproduce the failure, demonstrate the fix removes it, then ship. See [ANTI-PATTERNS.md](./ANTI-PATTERNS.md).

## How to apply

When scoping a task, walk through the tenets and name the ones the work serves. If a change fails tenet 1, 2, or 3, stop and surface the conflict before writing code. If you can't tell which tenet a change serves, it's probably off-narrative — ask.
