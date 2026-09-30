# Component Development

Components are the unit of work in Langflow. They render as nodes on the canvas, persist into flow JSON, and become tools for Agents. Get the contract right and the rest of the system follows; get it wrong and you orphan every saved flow that referenced your component.

Components live in **`src/lfx/src/lfx/components/<category>/`**. The mirror tree under `src/backend/base/langflow/components/` is legacy stubs — do not add files there.

## Before you add a component (decision checklist)

Stop and check, in order. If any answer is "yes," do not create a new component.

1. **Does one already exist?** Search:
   ```bash
   rg -l 'display_name = ".*<keyword>.*"' src/lfx/src/lfx/components/
   ```
   and check the category folder. The Calculator regret (two of them, see `tools/calculator.py` `legacy = True, replacement = ["helpers.CalculatorComponent"]`) is what happens when this step is skipped.
2. **Is this a thin wrapper around an existing tool/SDK that an Agent could call directly via `tool_mode=True`?** If yes, add `tool_mode=True` to the relevant input on the existing component instead of building a new one.
3. **Does it belong in a vendor bundle** (e.g., `openai/`, `anthropic/`, `datastax/`) rather than in generic `tools/` or `helpers/`? Vendor logic goes in vendor folders so bundles can ship/version independently.
4. **Is this an lfx-runtime concern** (graph execution, schema, IO primitives) or a **Langflow-app concern** (auth, DB, tracing)? Components are lfx; never import `langflow.services.*` from a component.
5. **Does an existing base class cover this category?** Use it:
   - LLMs → `LCModelComponent` (see `openai/openai_chat_model.py`)
   - Tools → `LCToolComponent` (see `tools/calculator.py`)
   - Vector stores → `LCVectorStoreComponent` + `@check_cached_vector_store` (see `vectorstores/local_db.py`)
   - Chat IO → `ChatComponent` (see `input_output/chat.py`)

## Scope rules (one component, one job)

- One job per component. If the description has " and " in it, split it.
- **Inputs budget:** aim for ≤8 visible inputs; push the rest behind `advanced=True`. If you need a mode switch (Ingest/Retrieve etc.), use `TabInput` + `update_build_config` to hide irrelevant fields — see `vectorstores/local_db.py`.
- **Outputs:** one primary `Output(method=...)` is the default. Add more only if downstream nodes genuinely need different shapes (Message vs DataFrame vs Data). Don't add an output you don't use.
- Mark inputs an Agent should be able to fill with `tool_mode=True` (e.g., `local_db.py`) — this is how a component becomes an agent tool.

## Breaking-change list (locked once shipped)

Saved flows reference components by string identifiers. Once a component is merged, the following are **frozen** — change them and existing user flows break silently:

- The **class name** (already in our rules).
- The **`name = "..."` class attribute**. **This is the flow-JSON identifier**, not the class name. See `openai_chat_model.py`, `chat.py`.
- Each input **`name=...`**. Renaming `input_value` → `prompt` orphans every edge pointing at it.
- Each output **`name=...`** and its declared return type. Downstream nodes match on both.
- **Default values** and default behavior of existing inputs (a flow saved with the default re-loads with the new default).

To remove or rework a component, **do not edit it in place**. Add the replacement under the right category, then on the old one set:

```python
legacy = True
replacement = ["<category>.<NewClassName>"]
```

(see `tools/calculator.py`, `flow_controls/sub_flow.py`). The UI shows "Updates Available" and migrates users; the old class stays importable.

See [CONTRACTS.md](./CONTRACTS.md) for the full user-facing surface this protects.

## Conventions agents miss

These appear all over the codebase but rarely in old docs.

- **`name`** (class attr): flow-JSON identifier. Always set it explicitly; do not rely on `__class__.__name__`. Example: `chat.py` `name = "ChatInput"`.
- **`legacy = True` + `replacement = [...]`**: deprecation pair. Always together. Example: `tools/calculator.py`.
- **`tool_mode=True`** on an input: exposes the component as an Agent tool with that input as the tool argument. Example: `vectorstores/local_db.py`.
- **`real_time_refresh=True` + `update_build_config(self, build_config, value, name)`**: dynamic form. Use for mode switches and dependent-field hide/show. Examples: `openai/openai_chat_model.py`, `vectorstores/local_db.py`.
- **`metadata = {"keywords": [...]}`**: extra search terms for the component picker. Example: `data_source/sql_executor.py`.
- **`minimized = True`**: render collapsed by default. Example: `input_output/chat.py`.
- **`documentation = "https://docs.langflow.org/..."`**: deep-link from the node UI. Example: `input_output/chat.py`.

## Placement rules

- **Vendor-specific code** → vendor folder (`openai/`, `anthropic/`, `datastax/`, `cohere/`, …). Not `tools/`, not `models/`.
- **Generic, vendor-agnostic helpers** → `helpers/`, `processing/`, `logic/`, `flow_controls/`.
- **IO primitives** → `input_output/`.
- Add the import to the category `__init__.py` in **alphabetical order**.
- **Do not invent a new top-level category.** If you think you need one, that is a signal to discuss with the team first — categories are visible in the UI sidebar and are part of the product surface.

## Icons

Every component needs an icon. Use a Lucide icon when one fits; create a custom SVG only for vendor logos.

### Lucide icon (default)

```python
icon = "calculator"  # any Lucide icon name, lowercase
```

See https://lucide.dev/icons for the catalog.

### Custom vendor icon

For brand logos you need a frontend SVG component. The Python `icon` string and the frontend mapping key must match **exactly** (case-sensitive).

1. **Python:** set `icon = "AstraDB"` on the component.
2. **Frontend SVG component** at `src/frontend/src/icons/AstraDB/AstraDB.jsx`:
   ```jsx
   const AstraSVG = (props) => (
     <svg {...props}>
       <path fill={props.isDark ? "#ffffff" : "#0A0A0A"} d="..." />
     </svg>
   );
   ```
3. **Wrapper** at `src/frontend/src/icons/AstraDB/index.tsx`:
   ```tsx
   import React, { forwardRef } from "react";
   import AstraSVG from "./AstraDB";

   export const AstraDBIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
     (props, ref) => <AstraSVG ref={ref} isDark={isDark} {...props} />
   );
   ```
4. **Lazy import** in `src/frontend/src/icons/lazyIconImports.ts`:
   ```ts
   AstraDB: () =>
     import("@/icons/AstraDB").then((mod) => ({ default: mod.AstraDBIcon })),
   ```
5. Verify in the UI in **both light and dark mode**.

### Icon checklist

- [ ] Python `icon = "..."` set.
- [ ] If custom: SVG component with `isDark` prop, wrapper with `forwardRef`, entry in `lazyIconImports.ts`.
- [ ] Light and dark mode both verified.

## Component testing

See [TESTING.md](./TESTING.md) for the full testing contract. Quick reference:

- Inherit from `ComponentTestBaseWithClient` (needs API) or `ComponentTestBaseWithoutClient` (pure logic).
- Provide three fixtures: `component_class`, `default_kwargs`, `file_names_mapping`.
- Use `MockLanguageModel` for pure-logic LLM paths; use `@pytest.mark.api_key_required` for real-API tests.
- For graph behavior, use the Graph test pattern: build, `.set()`, `async_start`, validate. Do not poke graph internals.

## Canonical examples

When in doubt, read these files before starting:

- LLM with dynamic provider switching: `src/lfx/src/lfx/components/openai/openai_chat_model.py`
- Tool with `tool_mode` and legacy/replacement: `src/lfx/src/lfx/components/tools/calculator.py`
- Vector store with cache + tab inputs: `src/lfx/src/lfx/components/vectorstores/local_db.py`
- Chat input with `minimized`: `src/lfx/src/lfx/components/input_output/chat.py`
- Component with searchable metadata: `src/lfx/src/lfx/components/data_source/sql_executor.py`
- Legacy + replacement pattern: `src/lfx/src/lfx/components/flow_controls/sub_flow.py`
