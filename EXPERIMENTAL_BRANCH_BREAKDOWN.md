# Langflow Experimental Branch Breakdown

**Branch:** `langflow-experimental` vs `main`
**Total files changed:** 281 | **Insertions:** ~16,094 | **Deletions:** ~1,589

This document breaks down every change into independent, self-contained features. Each section can be handed to a developer to implement against `main`. Files are listed exactly once across all sections.

---

## Table of Contents

1. [Inspection Panel (Major UI Overhaul)](#1-inspection-panel-major-ui-overhaul)
2. [Native Tracing System (Backend)](#2-native-tracing-system-backend)
3. [Logs, Messages & Traces Frontend](#3-logs-messages--traces-frontend)
4. [Datasets Feature (Full Stack)](#4-datasets-feature-full-stack)
5. [Evaluations Feature (Full Stack)](#5-evaluations-feature-full-stack)
6. [Sidebar Navigation Restructuring](#6-sidebar-navigation-restructuring)
7. [Workflow V2 API Endpoints](#7-workflow-v2-api-endpoints)
8. [API Response Component](#8-api-response-component)
9. [API Modal 2-Panel Redesign](#9-api-modal-2-panel-redesign)
10. [Tool Router Component & Dynamic Outputs](#10-tool-router-component--dynamic-outputs)
11. [Unified Operations Component](#11-unified-operations-component)
12. [Auto Type Coercion](#12-auto-type-coercion)
13. [Knowledge Info Component & Exact Match Search](#13-knowledge-info-component--exact-match-search)
14. [Knowledge Ingestion Batch Size Fix](#14-knowledge-ingestion-batch-size-fix)
15. [YouTube Comments Empty Fix](#15-youtube-comments-empty-fix)
16. [Loop Dual Mode (For-Each + Counted)](#16-loop-dual-mode-for-each--counted)
17. [Component Progress Bar](#17-component-progress-bar)
18. [CombineInputs Rename (DynamicCreateData)](#18-combineinputs-rename-dynamiccreatedata)
19. [Input/Output Legacy Tags](#19-inputoutput-legacy-tags)
20. [Component Context & Memory Management](#20-component-context--memory-management)
21. [Loading.py Variable Error Handling Fix](#21-loadingpy-variable-error-handling-fix)
22. [File & SaveFile Component Changes](#22-file--savefile-component-changes)
23. [Modal Autofocus Removal & Close Button TestID](#23-modal-autofocus-removal--close-button-testid)
24. [Starter Project Updates](#24-starter-project-updates)
25. [Alembic Migration Merge](#25-alembic-migration-merge)
26. [Test Infrastructure Updates](#26-test-infrastructure-updates)
27. [Miscellaneous UI Tweaks](#27-miscellaneous-ui-tweaks)

---

## 1. Inspection Panel (Major UI Overhaul)

### Summary
Replaces the traditional node editing modal with an inline inspection panel that appears beside the selected node on the canvas. When a node is clicked, its editable fields appear in a side panel instead of requiring a modal popup. Behind a feature flag (`ENABLE_INSPECTION_PANEL`).

### What it does
- Adds a right-side panel showing the selected node's fields, outputs, name, and description
- Moves editable fields from inside the node to the panel (node only shows connected handles)
- Adds inline prompt editing via a new AccordionPromptComponent
- Adds a `showParameter` prop to ALL parameter render components (when `false`, the component runs its useEffects but renders nothing)
- Modifies the node toolbar (removes code/controls when flag is on, adds freeze, docs buttons)
- Canvas controls move from bottom-right to bottom-left; inspector toggle goes to bottom-right
- Feature flag `ENABLE_INSPECTION_PANEL` controls everything

### Files to CREATE (new files)

**`src/frontend/src/pages/FlowPage/components/InspectionPanel/index.tsx`** (87 lines)
- Main panel component, renders when a node is selected and `inspectionPanelVisible` is true
- Wraps header, fields, and outputs in a fixed-width right panel

**`src/frontend/src/pages/FlowPage/components/InspectionPanel/components/InspectionPanelHeader.tsx`** (166 lines)
- Shows node icon, editable name/description, code button, docs button

**`src/frontend/src/pages/FlowPage/components/InspectionPanel/components/InspectionPanelFields.tsx`** (147 lines)
- Renders the editable fields for the selected node, with advanced toggle

**`src/frontend/src/pages/FlowPage/components/InspectionPanel/components/InspectionPanelField.tsx`** (200 lines)
- Individual field row with label, ParameterRenderComponent, and connection indicator

**`src/frontend/src/pages/FlowPage/components/InspectionPanel/components/InspectionPanelEditField.tsx`** (95 lines)
- Editable field specifically for the inspection panel context

**`src/frontend/src/pages/FlowPage/components/InspectionPanel/components/InspectionPanelOutputs.tsx`** (76 lines)
- Shows component outputs with inspection buttons

**`src/frontend/src/pages/FlowPage/components/InspectionPanel/components/EditableHeaderContent.tsx`** (213 lines)
- Inline editing for node name and description

**`src/frontend/src/CustomNodes/helpers/parameter-filtering.ts`** (72 lines)
- Extracted filtering logic for which parameters to show on node vs panel

**`src/frontend/src/components/core/parameterRenderComponent/components/accordionPromptComponent/index.tsx`** (487 lines)
- New inline prompt editor using accordion pattern (replaces modal-based prompt editing)

**`src/frontend/src/utils/styleUtils.ts`** (21 lines)
- Style utility for 4.5-height custom sizing

### Files to MODIFY

**`src/frontend/src/customization/feature-flags.ts`**
- Add: `export const ENABLE_INSPECTION_PANEL = true;`

**`src/frontend/src/customization/constants.ts`**
- Add constants related to inspection panel behavior

**`src/frontend/src/stores/flowStore.ts`** (inspection panel portion only)
- Add state: `inspectionPanelVisible: true`, `setInspectionPanelVisible`

**`src/frontend/src/types/zustand/flow/index.ts`**
- Add types: `inspectionPanelVisible`, `setInspectionPanelVisible`

**`src/frontend/src/pages/FlowPage/components/PageComponent/index.tsx`**
- Add InspectionPanel rendering beside the canvas when node is selected
- Pass `selectedNode` state

**`src/frontend/src/pages/FlowPage/components/PageComponent/MemoizedComponents.tsx`**
- Add `selectedNode` prop to CanvasControls, pass it through

**`src/frontend/src/components/core/canvasControlsComponent/CanvasControls.tsx`**
- Move panel from `bottom-right` to `bottom-left`
- Add a second Panel at `bottom-right` with inspector toggle button
- Accept `selectedNode` prop

**`src/frontend/src/components/core/canvasControlsComponent/CanvasControlsDropdown.tsx`**
- Accept `selectedNode` prop
- FitView with dynamic padding: `right: ENABLE_INSPECTION_PANEL && selectedNode ? "340px" : "20px"`

**`src/frontend/src/components/core/canvasControlsComponent/HelpDropdown.tsx`**
- Add inspector panel toggle option

**`src/frontend/src/components/core/canvasControlsComponent/HelpDropdownView.tsx`**
- Add "Show Inspector Panel" dropdown control button

**`src/frontend/src/CustomNodes/GenericNode/index.tsx`**
- Conditionally hide inputs that aren't handles when `ENABLE_INSPECTION_PANEL` is on
- Remove output modal from node (moved to panel)

**`src/frontend/src/CustomNodes/GenericNode/components/NodeInputField/index.tsx`**
- Add `showParameter` prop, add logic to show/hide based on inspection panel flag

**`src/frontend/src/CustomNodes/GenericNode/components/NodeOutputfield/index.tsx`**
- Simplify output display when inspection panel is active

**`src/frontend/src/CustomNodes/GenericNode/components/OutputComponent/index.tsx`**
- Minor adjustment for panel-aware rendering

**`src/frontend/src/CustomNodes/GenericNode/components/RenderInputParameters/index.tsx`**
- Filter inputs shown on node when inspection panel is active
- Use parameter-filtering helper

**`src/frontend/src/CustomNodes/GenericNode/components/RenderInputParameters/utils.ts`**
- Updated filtering logic for which fields appear on node vs panel

**`src/frontend/src/CustomNodes/GenericNode/components/RenderInputParameters/__tests__/primaryInputIdentification.test.ts`**
- Updated tests for new filtering behavior

**`src/frontend/src/CustomNodes/GenericNode/components/handleRenderComponent/index.tsx`**
- Changed rendering logic for handles when inspection panel is on

**`src/frontend/src/CustomNodes/GenericNode/components/nodeIcon/index.tsx`**
- Minor icon size adjustment

**`src/frontend/src/CustomNodes/GenericNode/components/outputModal/index.tsx`**
- Removed (55 lines deleted) -- output modal moved to inspection panel

**`src/frontend/src/CustomNodes/GenericNode/components/NodeName/index.tsx`**
- Minor text size adjustment

**`src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx`**
- Hide code/controls buttons when `ENABLE_INSPECTION_PANEL`
- Add freeze button always visible
- Add docs button

**`src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/components/toolbar-button.tsx`**
- Support for new button variants

**`src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/hooks/use-shortcuts.ts`**
- Disable advanced shortcut when inspection panel is enabled

**`src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/__tests__/minimal-condition.test.tsx`**
- Updated test for new toolbar behavior

**`src/frontend/src/components/core/parameterRenderComponent/index.tsx`**
- Add `showParameter` prop to ParameterRenderComponent
- Route `prompt` type to AccordionPromptComponent when flag is on

**`src/frontend/src/components/core/parameterRenderComponent/types.ts`**
- Add `showParameter?: boolean` to `BaseInputProps`
- Add `toggleField?: "advanced" | "api_only"` to `ToggleComponentType`

**`src/frontend/src/components/core/parameterRenderComponent/components/toggleShadComponent/index.tsx`**
- Add `toggleField` prop support (for `api_only` vs `advanced`)
- Add `showParameter` early return

**`src/frontend/src/components/core/parameterRenderComponent/components/tableComponent/components/tableAdvancedToggleCellRender/index.tsx`**
- Support `api_only` toggle field in tweaks mode

**All other parameterRenderComponent children** (each gets `showParameter = true` prop and early `if (!showParameter) return null`):
- `floatComponent/index.tsx`
- `intComponent/index.tsx`
- `inputComponent/components/popover/index.tsx`
- `inputComponent/components/popoverObject/index.tsx`
- `inputGlobalComponent/index.tsx`
- `inputListComponent/index.tsx`
- `codeAreaComponent/index.tsx`
- `copyFieldAreaComponent/index.tsx`
- `dictComponent/index.tsx`
- `dropdownComponent/index.tsx`
- `emptyParameterComponent/index.tsx`
- `keypairListComponent/index.tsx`
- `mcpComponent/index.tsx`
- `modelInputComponent/index.tsx`
- `multiselectComponent/index.tsx`
- `mustachePromptComponent/index.tsx`
- `promptComponent/index.tsx`
- `queryComponent/index.tsx`
- `sliderComponent/index.tsx`
- `sortableListComponent/index.tsx`
- `tabComponent/index.tsx`
- `textAreaComponent/index.tsx`
- `webhookFieldComponent/index.tsx`
- `TableNodeComponent/index.tsx`
- `ToolsComponent/index.tsx`

**`src/frontend/src/components/core/dropdownComponent/index.tsx`**
- Fix dropdown collision avoidance

**`src/frontend/src/customization/components/custom-parameter.tsx`**
- Pass `showParameter` through to rendered components

**`src/frontend/src/utils/reactflowUtils.ts`**
- Add utility for fitView with panel-aware padding

**`src/frontend/tailwind.config.mjs`**
- Add custom height/width classes for 4.5 sizing

**`src/frontend/src/types/components/index.ts`**
- Remove unused type

---

## 2. Native Tracing System (Backend)

### Summary
Implements a database-backed execution tracing system that captures component-level and LangChain-level spans during flow execution. Eliminates the need for external tracing services for basic observability.

### What it does
- Creates `trace` and `span` database tables
- Implements `NativeTracer` that hooks into Langflow's TracingService
- Implements `NativeCallbackHandler` for LangChain event capture (LLM, tool, chain, retriever calls)
- Captures token usage, latency, cost, inputs/outputs, errors per span
- Provides REST API endpoints for querying trace data
- Enabled by default; disable with `LANGFLOW_NATIVE_TRACING=false`

### Files to CREATE

**`src/backend/base/langflow/api/v1/traces.py`** (292 lines)
- FastAPI router at `/api/v1/traces`
- `GET /traces` -- list traces (filtered by flow_id, session_id, status)
- `GET /traces/{trace_id}` -- single trace with hierarchical span tree
- `DELETE /traces/{trace_id}` -- delete a trace
- `DELETE /traces?flow_id=...` -- delete all traces for a flow
- Helper: `_build_span_tree()` builds parent-child hierarchy, `_span_to_dict()` converts to camelCase JSON

**`src/backend/base/langflow/services/database/models/traces/__init__.py`** (3 lines)
- Exports `SpanTable`, `TraceTable`

**`src/backend/base/langflow/services/database/models/traces/model.py`** (184 lines)
- `SpanType` enum: CHAIN, LLM, TOOL, RETRIEVER, EMBEDDING, PARSER, AGENT
- `SpanStatus` enum: SUCCESS, ERROR, RUNNING
- `TraceTable`: id, name, status, start/end time, total_latency_ms, total_tokens, total_cost, flow_id, session_id
- `SpanTable`: id, trace_id, parent_span_id (self-ref), name, span_type, status, times, latency, inputs/outputs (JSON), error, model_name, token counts, cost

**`src/backend/base/langflow/alembic/versions/3671f35245e5_add_trace_and_span_tables.py`** (107 lines)
- Creates `trace` and `span` tables with indexes on flow_id, session_id, trace_id, parent_span_id

**`src/backend/base/langflow/services/tracing/native.py`** (469 lines)
- `NativeTracer(BaseTracer)` implementation
- `add_trace()`/`end_trace()`: component-level span tracking
- `end()`: schedules `_flush_to_database()` async task
- `wait_for_flush()`: awaited by TracingService
- `_flush_to_database()`: writes TraceTable + SpanTable in single transaction
- `get_langchain_callback()`: returns NativeCallbackHandler
- `_ensure_tables_exist()`: auto-creates tables if missing

**`src/backend/base/langflow/services/tracing/native_callback.py`** (413 lines)
- `NativeCallbackHandler(BaseCallbackHandler)`
- Handles all LangChain events: LLM start/end, chain start/end, tool start/end, retriever start/end, agent actions
- Captures token usage, model names, inputs/outputs per span
- Creates parent-child span relationships

### Files to MODIFY

**`src/backend/base/langflow/services/tracing/service.py`** (26 lines added)
- Add `_get_native_tracer()` lazy import
- Add `_initialize_native_tracer()` method
- Call it in `start_tracers()`
- In end: `await native_tracer.wait_for_flush()`

**`src/backend/base/langflow/api/v1/__init__.py`** (add traces_router import/export)

**`src/backend/base/langflow/api/router.py`** (add `router_v1.include_router(traces_router)`)

**`src/backend/base/langflow/services/database/models/__init__.py`** (add traces model imports)

---

## 3. Logs, Messages & Traces Frontend

### Summary
Frontend components for viewing execution logs, message history, and trace details within the flow editor. Replaces the canvas with dedicated views when logs/messages sections are active in the sidebar.

### Dependencies
- Requires: [Native Tracing System](#2-native-tracing-system-backend) for trace data
- Requires: [Sidebar Navigation Restructuring](#6-sidebar-navigation-restructuring) for section switching

### Files to CREATE

**`src/frontend/src/controllers/API/queries/traces/index.ts`** (2 lines)
- Re-exports trace query hooks

**`src/frontend/src/controllers/API/queries/traces/use-get-traces.ts`** (71 lines)
- React Query hook: `GET /traces?flow_id=...&session_id=...`

**`src/frontend/src/controllers/API/queries/traces/use-get-trace.ts`** (113 lines)
- React Query hook: `GET /traces/{traceId}` with span tree conversion

**`src/frontend/src/modals/flowLogsModal/components/TraceView/types.ts`** (38 lines)
- TypeScript types: SpanType, SpanStatus, TokenUsage, Span (recursive), Trace

**`src/frontend/src/modals/flowLogsModal/components/TraceView/index.tsx`** (175 lines)
- Split-panel: span tree (left 1/3) + span details (right 2/3)
- Trace summary header with status, latency, tokens, cost

**`src/frontend/src/modals/flowLogsModal/components/TraceView/SpanTree.tsx`** (71 lines)
- Recursive tree with expand/collapse

**`src/frontend/src/modals/flowLogsModal/components/TraceView/SpanNode.tsx`** (163 lines)
- Individual span row: icon by type, name, tokens, latency, status badge

**`src/frontend/src/modals/flowLogsModal/components/TraceView/SpanDetail.tsx`** (228 lines)
- Detail panel: header, error display, metrics grid, input/output JSON viewers

**`src/frontend/src/pages/FlowPage/components/LogsMainContent/index.tsx`** (105 lines)
- Two sub-views: LogsTableView (flat table) and TracesDetailView (execution tree)

**`src/frontend/src/pages/FlowPage/components/LogsMainContent/components/LogsTableView.tsx`** (256 lines)
- Table of runs: status filter, refresh, columns (status, run ID, time, input, output, latency, view trace)

**`src/frontend/src/pages/FlowPage/components/LogsMainContent/components/TracesDetailView.tsx`** (215 lines)
- Wrapper: renders TraceView if traces exist, falls back to RunDetailsFallback

**`src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/LogsSidebarGroup.tsx`** (187 lines)
- Logs/Traces tabs in sidebar, trace list with status badges, auto-select first

**`src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/MessagesSidebarGroup.tsx`** (243 lines)
- Groups messages by session_id, shows session list with preview/counts

**`src/frontend/src/pages/FlowPage/components/MessagesMainContent/index.tsx`** (183 lines)
- Table of messages filtered by session, supports edit/delete

### Files to MODIFY

**`src/frontend/src/modals/flowLogsModal/index.tsx`** (104 lines changed)
- Add Logs/Traces tab switcher
- Render TraceView in traces tab

**`src/frontend/src/controllers/API/helpers/constants.ts`**
- Add `TRACES: "traces"` to URLs object

---

## 4. Datasets Feature (Full Stack)

### Summary
A complete dataset management system for storing input/expected-output pairs. Used by the Evaluations feature. Includes CRUD API, CSV import, and a full management UI.

### Files to CREATE

**`src/backend/base/langflow/api/v1/datasets.py`** (522 lines)
- FastAPI router at `/api/v1/datasets`
- CRUD: create, list, get, update, delete datasets
- Item CRUD: create, update, delete individual items
- CSV: preview and import endpoints
- Bulk delete endpoint

**`src/backend/base/langflow/services/database/models/dataset/__init__.py`** (23 lines)
- Exports all dataset model classes

**`src/backend/base/langflow/services/database/models/dataset/model.py`** (114 lines)
- `Dataset`: id, name, description, user_id (FK), timestamps
- `DatasetItem`: id, dataset_id (FK), input, expected_output, order, created_at
- Pydantic schemas: DatasetCreate, DatasetRead, DatasetItemCreate, DatasetItemRead

**`src/backend/base/langflow/alembic/versions/a1b2c3d4e5f6_create_dataset_tables.py`** (68 lines)
- Creates `dataset` (unique on user_id+name) and `datasetitem` tables

**`src/frontend/src/controllers/API/queries/datasets/index.ts`** (11 lines)
**`src/frontend/src/controllers/API/queries/datasets/use-create-dataset.ts`** (34 lines)
**`src/frontend/src/controllers/API/queries/datasets/use-create-dataset-item.ts`** (46 lines)
**`src/frontend/src/controllers/API/queries/datasets/use-get-datasets.ts`** (37 lines)
**`src/frontend/src/controllers/API/queries/datasets/use-get-dataset.ts`** (53 lines)
**`src/frontend/src/controllers/API/queries/datasets/use-update-dataset.ts`** (41 lines)
**`src/frontend/src/controllers/API/queries/datasets/use-update-dataset-item.ts`** (47 lines)
**`src/frontend/src/controllers/API/queries/datasets/use-delete-dataset.ts`** (29 lines)
**`src/frontend/src/controllers/API/queries/datasets/use-delete-datasets.ts`** (37 lines)
**`src/frontend/src/controllers/API/queries/datasets/use-delete-dataset-item.ts`** (35 lines)
**`src/frontend/src/controllers/API/queries/datasets/use-import-csv.ts`** (47 lines)
**`src/frontend/src/controllers/API/queries/datasets/use-preview-csv.ts`** (46 lines)

**`src/frontend/src/modals/createDatasetModal/index.tsx`** (115 lines)
- Modal for creating a new dataset (name + description)

**`src/frontend/src/modals/importCsvModal/index.tsx`** (247 lines)
- CSV import modal: file upload, column mapping, preview, import

**`src/frontend/src/pages/MainPage/pages/datasetsPage/index.tsx`** (90 lines)
- Main datasets list page

**`src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetsTab.tsx`** (220 lines)
- Dataset list with selection, bulk delete, create/import buttons

**`src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetEmptyState.tsx`** (36 lines)
**`src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetSelectionOverlay.tsx`** (51 lines)
**`src/frontend/src/pages/MainPage/pages/datasetsPage/config/datasetColumns.tsx`** (78 lines)
- Column definitions for the dataset table

**`src/frontend/src/pages/MainPage/pages/datasetDetailPage/index.tsx`** (369 lines)
- Individual dataset detail page: view/edit items, add rows, import CSV

### Files to MODIFY

**`src/frontend/src/routes.tsx`** (add dataset routes: `/assets/datasets` and `/assets/datasets/:id`)

**`src/frontend/src/controllers/API/helpers/constants.ts`**
- Add `DATASETS: "datasets"` to URLs object

**`src/frontend/src/components/core/folderSidebarComponent/components/sideBarFolderButtons/index.tsx`**
- Add "Datasets" navigation button (behind `ENABLE_DATASETS` flag)

**`src/backend/base/langflow/services/database/models/user/model.py`**
- Add `datasets` relationship on User model

**`src/backend/base/langflow/api/v1/__init__.py`** (add datasets_router)
**`src/backend/base/langflow/api/router.py`** (include datasets_router)

---

## 5. Evaluations Feature (Full Stack)

### Summary
Systematic flow testing against datasets. Runs each dataset item through a flow, scores results using exact match, contains, similarity, or LLM Judge, and displays results in real-time.

### Dependencies
- Requires: [Datasets Feature](#4-datasets-feature-full-stack)

### Files to CREATE

**`src/backend/base/langflow/api/v1/evaluations.py`** (685 lines)
- FastAPI router at `/api/v1/evaluations`
- `POST /evaluations/` -- create (optionally run immediately via `asyncio.create_task`)
- `GET /evaluations/` -- list (filtered by flow_id)
- `GET /evaluations/{id}` -- get with results
- `POST /evaluations/{id}/run` -- re-run
- `DELETE /evaluations/{id}` -- delete
- Scoring: `calculate_score()` (exact_match, contains, similarity)
- `run_llm_judge()` -- LLM-based scoring using unified model provider
- `run_single_evaluation_item()` -- runs one dataset item through a Graph
- `run_evaluation_background()` -- async background task iterating all items

**`src/backend/base/langflow/services/database/models/evaluation/__init__.py`** (25 lines)
**`src/backend/base/langflow/services/database/models/evaluation/model.py`** (203 lines)
- `EvaluationStatus` enum: PENDING, RUNNING, COMPLETED, FAILED
- `ScoringMethod` enum: EXACT_MATCH, CONTAINS, SIMILARITY, LLM_JUDGE
- `Evaluation`: id, name, status, scoring_methods (JSON), timestamps, FKs (user, dataset, flow), summary metrics
- `EvaluationResult`: id, evaluation_id, dataset_item_id, input, expected/actual output, duration, scores (JSON), passed, error

**`src/backend/base/langflow/alembic/versions/b2c3d4e5f6g7_create_evaluation_tables.py`** (87 lines)
- Creates `evaluation` and `evaluationresult` tables

**`src/frontend/src/controllers/API/queries/evaluations/use-create-evaluation.ts`** (49 lines)
**`src/frontend/src/controllers/API/queries/evaluations/use-get-evaluations.ts`** (74 lines)
**`src/frontend/src/controllers/API/queries/evaluations/use-get-evaluation.ts`** (36 lines)
**`src/frontend/src/controllers/API/queries/evaluations/use-run-evaluation.ts`** (35 lines)
**`src/frontend/src/controllers/API/queries/evaluations/use-delete-evaluation.ts`** (31 lines)

**`src/frontend/src/modals/createEvaluationModal/index.tsx`** (448 lines)
- Dataset selector, multi-select scoring methods, LLM Judge model picker, validation

**`src/frontend/src/pages/EvaluationPage/index.tsx`** (265 lines)
- Standalone results page with polling, progress bar, results table, summary stats

**`src/frontend/src/pages/FlowPage/components/EvaluationsMainContent/index.tsx`** (292 lines)
- Inline version of evaluation results (replaces canvas when evaluations sidebar is active)

**`src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/EvaluationsSidebarGroup.tsx`** (322 lines)
- Sidebar panel: list evaluations, create new, auto-select, status badges

**`src/frontend/src/components/core/flowToolbarComponent/components/evaluate-button.tsx`** (71 lines)
- Toolbar button to trigger evaluation creation

### Files to MODIFY

**`src/backend/base/langflow/services/database/models/user/model.py`**
- Add `evaluations` relationship

**`src/frontend/src/controllers/API/helpers/constants.ts`**
- Add `EVALUATIONS: "evaluations"` to URLs

**`src/backend/base/langflow/api/v1/__init__.py`** (add evaluations_router)
**`src/backend/base/langflow/api/router.py`** (include evaluations_router)

---

## 6. Sidebar Navigation Restructuring

### Summary
Transforms the flow sidebar from a simple component list into a multi-section navigation system with segmented controls. Adds sections for Logs, Messages, Evaluations, and Saved Components alongside the existing Components/MCP/Bundles.

### Files to MODIFY

**`src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/sidebarSegmentedNav.tsx`** (96 lines changed)
- Remove "search" and "add_note" nav items
- Add new nav items: `"saved"`, `"logs"`, `"messages"`, `"evaluations"` (with icons)
- Add visual separator before logs/messages/evaluations group
- Different click behavior for content-replacing sections

**`src/frontend/src/pages/FlowPage/components/flowSidebarComponent/index.tsx`** (105 lines changed)
- Extended props: `selectedSessionId`, `onSelectSession`, `logsActiveTab`, `onLogsTabChange`, `selectedRunId`, `onSelectRun`, `selectedTraceId`, `onSelectTrace`, `selectedEvaluationId`, `onSelectEvaluation`
- Section visibility flags: `showLogs`, `showMessages`, `showEvaluations`, `showSaved`
- Conditionally hides search header and footer for non-component sections
- Routes to LogsSidebarGroup/MessagesSidebarGroup/EvaluationsSidebarGroup/SavedComponentsSidebarGroup

**`src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/sidebarFooterButtons.tsx`** (65 lines changed)
- Restructured footer with conditional visibility

**`src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/categoryGroup.tsx`** (3 lines changed)
- Minor adjustment for new layout

**`src/frontend/src/pages/FlowPage/index.tsx`** (124 lines changed)
- Created `FlowMainContent` wrapper component
- Conditionally renders: Page (canvas), LogsMainContent, MessagesMainContent, or EvaluationsMainContent based on `activeSection`
- Lifted state: `selectedSessionId`, `logsActiveTab`, `selectedRunId`, `selectedTraceId`, `selectedEvaluationId`

**`src/frontend/src/components/core/flowToolbarComponent/components/flow-toolbar-options.tsx`** (4 lines added)
- Pass evaluate button integration

**`src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx`** (11 lines added)
- Deploy dropdown adjustments

**`src/frontend/src/components/core/flowToolbarComponent/components/playground-button.tsx`** (15 lines changed)
- Block playground button when API request is on canvas

**`src/frontend/src/components/ui/sidebar.tsx`** (7 lines changed)
- Minor sidebar component adjustments

---

## 7. Workflow V2 API Endpoints

### Summary
New `/api/v2/run/stateless/{flow_id}` endpoint for simplified, stateless workflow execution. Returns clean JSON responses without storing messages in the database. Designed for API Response components.

### Files to CREATE

**`src/backend/tests/unit/test_workflow_endpoint.py`** (147 lines)
- 7 tests: no payload, with inputs, empty inputs, invalid flow ID, missing flow, inputs parameter, no messages stored

### Files to MODIFY

**`src/backend/base/langflow/api/v1/chat.py`** (3 lines added)
- Integration point for v2 workflow routing

**`src/backend/base/langflow/api/v1/schemas.py`** (7 lines added)
- New schema types for workflow responses

**`src/backend/base/langflow/api/build.py`** (21 lines changed)
- Build process modifications for stateless execution

**`src/backend/base/langflow/api/utils/core.py`** (16 lines changed)
- Core utility changes for workflow support

**`src/backend/base/langflow/memory.py`** (26 lines added)
- Memory handling with context support for stateless mode

**`src/backend/base/langflow/services/job_queue/service.py`** (1 line added)
- Job queue integration

**`src/lfx/src/lfx/graph/graph/base.py`** (62 lines changed)
- Add `arun_single()` async method to Graph class
- Support for stateless execution flow

**`src/lfx/src/lfx/graph/__init__.py`** (12 lines changed)
- Updated exports

---

## 8. API Response Component

### Summary
New components for minimal JSON API responses, enabling flows to act as clean API endpoints that return structured JSON instead of chat messages.

### Files to CREATE

**`src/lfx/src/lfx/components/input_output/api_response.py`** (72 lines)
- APIResponseComponent: takes input_value and metadata, returns structured JSON

**`src/lfx/src/lfx/components/input_output/request_payload.py`** (94 lines)
- RequestPayloadComponent: parses incoming API request payloads

### Files to MODIFY

**`src/lfx/src/lfx/components/input_output/__init__.py`** (15 lines changed)
- Add exports for APIResponseComponent, RequestPayloadComponent
- Reorganize imports, add legacy tags to old components

---

## 9. API Modal 2-Panel Redesign

### Summary
Transforms the API modal from a single panel to a 2-panel layout. Left panel shows component/field selection, right panel shows generated code. Supports the new workflow API endpoint.

### Files to CREATE

**`src/frontend/src/modals/apiModal/components/ComponentSelector.tsx`** (74 lines)
- Dropdown to select which component to configure

**`src/frontend/src/modals/apiModal/components/FieldSelector.tsx`** (137 lines)
- Toggle-able field list for the selected component

### Files to MODIFY

**`src/frontend/src/modals/apiModal/utils/get-python-api-code.tsx`** (37 lines changed)
- Add `hasAPIResponse` parameter
- Generate v2 stateless endpoint URL when API Response component is present
- Different code template for workflow vs chat API

**`src/frontend/src/stores/tweaksStore.ts`** (5 lines changed)
- Store adjustments for the new 2-panel flow

---

## 10. Tool Router Component & Dynamic Outputs

### Summary
A new ToolRouter component that dynamically creates outputs based on connected tool inputs. When tools are connected/disconnected, the component updates its outputs in real-time via backend API calls.

### Files to CREATE

**`src/backend/base/langflow/components/helpers/universal_output_selector.py`** (400 lines)
- Universal output selection logic for dynamic routing

### Files to MODIFY

**`src/frontend/src/stores/flowStore.ts`** (178 lines added -- Tool Router portion)
- New `updateHandleInputOutputs()` helper function: calls backend API to update component template/outputs when HandleInput connections change
- In `deleteEdge()`: detect HandleInput with `real_time_refresh`, get remaining connections, trigger output update
- In `onConnect()`: detect HandleInput with `real_time_refresh`, get all connections, trigger output update

**`src/frontend/src/types/zustand/flow/index.ts`**
- Type additions for flow store

---

## 11. Unified Operations Component

### Summary
A single `Operations` component that replaces separate Text Operations, Data Operations, and DataFrame Operations components (marked as legacy).

### Files to CREATE

**`src/lfx/src/lfx/components/processing/operations.py`** (1,357 lines)
- Unified Operations component handling text, data, and dataframe operations
- Tab-based mode selection
- All operations from the three legacy components in one place

**`src/lfx/src/lfx/components/processing/progress_test.py`** (54 lines)
- Test component for the progress bar feature

### Files to MODIFY

**`src/lfx/src/lfx/components/processing/__init__.py`** (9 lines added)
- Add Operations, DynamicCreateDataComponent, ProgressTestComponent exports

**`src/lfx/src/lfx/components/processing/data_operations.py`** (2 lines added)
- Add `legacy = True`

**`src/lfx/src/lfx/components/processing/dataframe_operations.py`** (2 lines added)
- Add `legacy = True`

**`src/lfx/src/lfx/components/processing/text_operations.py`** (2 lines added)
- Add `legacy = True`

---

## 12. Auto Type Coercion

### Summary
Allows automatic conversion between Data, Message, and DataFrame types when connecting components. Includes backend coercion logic, frontend store, and a settings page.

### Files to CREATE

**`src/lfx/src/lfx/graph/coercion.py`** (230 lines)
- Backend coercion logic: `coerce_value()`, `can_coerce()`, conversion functions between Data/Message/DataFrame

**`src/frontend/src/stores/coercionStore.ts`** (103 lines)
- Zustand store with `enabled`/`autoParse` settings
- `isCoercibleType()`, `areTypesCoercible()` helpers
- localStorage persistence

**`src/frontend/src/pages/SettingsPage/pages/TypeCoercionPage/index.tsx`** (139 lines)
- Settings page with toggle switches for auto-coercion and auto-parse

### Files to MODIFY

**`src/lfx/src/lfx/graph/edge/base.py`** (24 lines added)
- Add coercion check in edge validation

**`src/lfx/src/lfx/graph/vertex/base.py`** (46 lines added)
- Apply coercion when passing values between vertices

**`src/lfx/src/lfx/graph/schema.py`** (4 lines added)
- Schema support for coercion metadata

**`src/frontend/src/pages/SettingsPage/index.tsx`** (10 lines added)
- Add Type Coercion link to settings navigation

**`src/frontend/src/routes.tsx`** (add type-coercion route)

---

## 13. Knowledge Info Component & Exact Match Search

### Summary
New KnowledgeInfo component that returns metadata about a knowledge base. Adds exact match search mode to the existing Knowledge Retrieval component.

### Files to CREATE

**`src/lfx/src/lfx/components/files_and_knowledge/info.py`** (245 lines)
- KnowledgeInfoComponent: returns metadata (document count, chunk count, storage info)

### Files to MODIFY

**`src/lfx/src/lfx/components/files_and_knowledge/__init__.py`** (3 lines added)
- Export KnowledgeInfoComponent

**`src/lfx/src/lfx/components/files_and_knowledge/retrieval.py`** (167 lines changed)
- Add `search_mode` input with options: "Similarity", "Exact Match"
- Implement exact match search using metadata filtering
- Add `match_field` and `match_value` inputs for exact match mode

---

## 14. Knowledge Ingestion Batch Size Fix

### Summary
Fixes Chroma's maximum batch size limit by adding batch processing to the Knowledge Ingestion component.

### Files to MODIFY

**`src/lfx/src/lfx/components/files_and_knowledge/ingestion.py`** (30 lines changed)
- Add batch processing: splits documents into chunks of 5,000 (Chroma's limit) before insertion
- Processes each batch sequentially to avoid exceeding vector DB limits

---

## 15. YouTube Comments Empty Fix

### Summary
Fixes crash when a YouTube video has no comments or comments are disabled.

### Files to MODIFY

**`src/lfx/src/lfx/components/youtube/comments.py`** (24 lines changed)
- Check for empty comments list before processing
- Return empty DataFrame with proper column structure instead of crashing
- Add graceful handling for videos with comments disabled

---

## 16. Loop Dual Mode (For-Each + Counted)

### Summary
Merges Loop and For Loop components into a single dual-mode component with For-Each (iterate over DataFrame) and Counted (repeat N times) modes.

### Files to MODIFY

**`src/backend/base/langflow/components/logic/loop.py`** (78 lines added)
- Add `TabInput` for mode selection
- `For-Each` mode: iterate over DataFrame/list (original behavior)
- `Counted` mode: takes Data/Message + iterations count, repeats N times
- `update_build_config()`: dynamic field visibility based on mode
- New inputs: `dataframe_input`, `data_input`, `iterations`
- Renamed original `data` input to mode-specific inputs
- Backward compatible (defaults to For-Each)

**`src/backend/tests/unit/components/logic/test_loop.py`** (209 lines added)
- Comprehensive tests for both modes

---

## 17. Component Progress Bar

### Summary
Visual progress tracking for component execution, showing a progress bar on nodes during long-running operations.

### Files to MODIFY

**`src/frontend/src/stores/flowStore.ts`** (nodeProgress portion)
- Add `nodeProgress: {}` state (maps nodeId -> progress value)
- Add `setNodeProgress(nodeId, progress)` and `clearAllNodeProgress()`

**`src/frontend/src/utils/buildUtils.ts`** (23 lines added)
- Build utilities for progress tracking

**`src/lfx/src/lfx/events/event_manager.py`** (1 line added)
- Add progress event type

**`src/frontend/src/components/core/logCanvasControlsComponent/index.tsx`** (30 lines changed)
- Canvas controls for log view with progress support

**`src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/index.tsx`**
- Display progress bar on node during execution

---

## 18. CombineInputs Rename (DynamicCreateData)

### Summary
Renames the DynamicCreateData component to CombineInputs while maintaining backward compatibility.

### Files to MODIFY

**`src/lfx/src/lfx/components/processing/dynamic_create_data.py`** (355 lines changed)
- Component class remains `DynamicCreateDataComponent` for backward compat
- `display_name` changed to "Combine Inputs"
- Updated description and icon
- Added functionality improvements

---

## 19. Input/Output Legacy Tags

### Summary
Marks TextInput and TextOutput components as legacy with replacement pointers.

### Files to MODIFY

**`src/lfx/src/lfx/components/input_output/text.py`** (2 lines added)
- Add `legacy = True` and `replacement` pointer

**`src/lfx/src/lfx/components/input_output/text_output.py`** (2 lines added)
- Add `legacy = True` and `replacement` pointer

**`src/lfx/src/lfx/components/models_and_agents/mcp_component.py`** (1 line added)
- Add `legacy = True` to MCP component

---

## 20. Component Context & Memory Management

### Summary
Enhances the Component class with context management methods and adds memory stubs for stateless execution.

### Files to MODIFY

**`src/lfx/src/lfx/custom/custom_component/component.py`** (50 lines changed)
- Add context management methods for stateless mode
- Enhanced `update_ctx()` and `get_ctx()` support

### Files to CREATE

**`src/lfx/src/lfx/memory/stubs.py`** (26 lines)
- Memory stubs for stateless execution (no-op implementations)

---

## 21. Loading.py Variable Error Handling Fix

### Summary
Changes error handling so "variable not found" errors are always re-raised instead of being silently caught when `fallback_to_env_vars` is True.

### Files to MODIFY

**`src/lfx/src/lfx/interface/initialize/loading.py`** (4 lines changed)
- Before: `"variable not found."` errors only re-raised when `fallback_to_env_vars=False`
- After: Always re-raised using combined `any()` check

**`src/backend/tests/unit/interface/initialize/test_loading.py`** (8 lines changed)
- Change mock error from `"TEST_API_KEY variable not found."` to `"Database connection failed"` to avoid triggering the new re-raise behavior

---

## 22. File & SaveFile Component Changes

### Summary
Removes `storage_location` field from File and SaveFile components.

### Files to MODIFY

**`src/lfx/src/lfx/components/files_and_knowledge/file.py`** (2 lines changed)
- Remove storage_location field/logic

**`src/lfx/src/lfx/components/files_and_knowledge/save_file.py`** (3 lines changed)
- Remove storage_location field/logic

**`src/backend/tests/unit/components/files_and_knowledge/test_file_component.py`** (14 lines deleted)
- Remove `test_storage_location_defaults_to_local` and `test_storage_location_is_advanced`

**`src/backend/tests/unit/components/processing/test_save_file_component.py`** (10 lines deleted)
- Same storage_location test removals

---

## 23. Modal Autofocus Removal & Close Button TestID

### Summary
Removes `onOpenAutoFocus` from modals and adds a `data-testid` to the edit modal close button.

### Files to MODIFY

**`src/frontend/src/modals/baseModal/index.tsx`** (4 lines removed)
- Remove `onOpenAutoFocus` prop from interface and DialogContent

**`src/frontend/src/modals/confirmationModal/index.tsx`** (8 lines changed)
- Remove `onOpenAutoFocus` prop

**`src/frontend/src/modals/saveChangesModal/index.tsx`** (11 lines changed)
- Remove `handleOpenAutoFocus` callback and `onOpenAutoFocus` usage

**`src/frontend/src/modals/editNodeModal/index.tsx`** (7 lines changed)
- Add `data-testid="edit-button-close"` to the Close button

---

## 24. Starter Project Updates

### Summary
Updates 27 starter project JSON files with model field cleanup and legacy component marking.

### Pattern A: Model field cleanup (all projects)
- Remove `"options": []` from model field
- Change `"value": []` to `"value": ""`
- Some remove `"input_types": ["LanguageModel"]` -> `"input_types": []`

### Pattern B: TextInput legacy marking (selected projects)
- Blog Writer, Instagram Copywriter, Knowledge Retrieval, Twitter Thread Generator, News Aggregator, Portfolio Website Code Generator
- TextInput code updated with `legacy = True`, `replacement = ["input_output.JSONInput"]`

### Files to MODIFY
All files in `src/backend/base/langflow/initial_setup/starter_projects/`:
- Basic Prompting.json, Blog Writer.json, Custom Component Generator.json, Document Q&A.json, Instagram Copywriter.json, Invoice Summarizer.json, Knowledge Ingestion.json, Knowledge Retrieval.json, Market Research.json, Meeting Summary.json, Memory Chatbot.json, News Aggregator.json, Nvidia Remix.json, Pokedex Agent.json, Portfolio Website Code Generator.json, Price Deal Finder.json, Research Agent.json, SaaS Pricing.json, Search agent.json, Sequential Tasks Agents.json, Simple Agent.json, Social Media Agent.json, Text Sentiment Analysis.json, Travel Planning Agents.json, Twitter Thread Generator.json, Vector Store RAG.json, Youtube Analysis.json

---

## 25. Alembic Migration Merge

### Summary
Merge migration that brings together three experimental branch migration heads.

### Files to CREATE

**`src/backend/base/langflow/alembic/versions/23c16fac4a0d_merge_experimental_branches.py`** (31 lines)
- 3-way merge: `3671f35245e5` (tracing) + `369268b9af8b` + `bcbbf8c17c25` (memory path)
- Empty upgrade/downgrade (pure merge point)

**`src/backend/base/langflow/alembic/versions/bcbbf8c17c25_update_memory_component_path_from_.py`** (73 lines)
- Updates Memory component path in saved flows: `lfx.components.helpers.memory` -> `lfx.components.models_agents.memory`
- SQL REPLACE on flow.data column

---

## 26. Test Infrastructure Updates

### Summary
Systematic test updates to support the Inspection Panel UX changes. Tests now click nodes before interacting with their fields.

### New Test Utilities

**`src/frontend/tests/utils/unselect-nodes.ts`** (6 lines)
- Clicks empty area of `.react-flow__pane` to deselect all nodes

**`src/frontend/tests/utils/select-anthropic-model.ts`** (65 lines)
- Selects `claude-sonnet-4-5-20250929` model via provider UI

### Modified Test Utilities

**`src/frontend/tests/utils/select-gpt-model.ts`** (22 lines changed)
- Node-scoped locators, click node before model dropdown, call unselectNodes between iterations

**`src/frontend/tests/utils/initialGPTsetup.ts`** (6 lines added)
- Call `adjustScreenView` and `unselectNodes` at end of setup

**`src/frontend/tests/utils/upload-file.ts`** (6 lines added)
- Click "File" node before upload, unselectNodes after

### Modified Test Files (all changes map to inspection panel patterns)

**Pattern: Click node before interacting with fields:**
- `tests/core/features/freeze-path.spec.ts` (12 lines)
- `tests/core/features/freeze.spec.ts` (9 lines)
- `tests/core/features/globalVariables.spec.ts` (2 lines)
- `tests/core/features/stop-building.spec.ts` (6 lines)
- `tests/core/features/logs.spec.ts` (7 lines)
- `tests/core/integrations/Blog Writer.spec.ts` (4 lines)
- `tests/core/integrations/Custom Component Generator.spec.ts` (24 lines)
- `tests/core/integrations/Financial Report Parser.spec.ts` (2 lines)
- `tests/core/integrations/Image Sentiment Analysis.spec.ts` (3 lines)
- `tests/core/integrations/Instagram Copywriter.spec.ts` (18 lines)
- `tests/core/integrations/Invoice Summarizer.spec.ts` (24 lines)
- `tests/core/integrations/Market Research.spec.ts` (43 lines)
- `tests/core/integrations/decisionFlow.spec.ts` (21 lines)
- `tests/extended/features/mcp-server.spec.ts` (8 lines)
- `tests/extended/regression/generalBugs-shard-3.spec.ts` (1 line)
- `tests/extended/regression/generalBugs-shard-10.spec.ts` (10 lines)

**Pattern: Close button selector -> `data-testid="edit-button-close"`:**
- `tests/core/features/chatInputOutputUser-shard-0.spec.ts` (2 lines)
- `tests/core/features/filterSidebar.spec.ts` (2 lines)
- `tests/core/unit/dropdownComponent.spec.ts` (2 lines)
- `tests/core/unit/floatComponent.spec.ts` (6 lines)
- `tests/core/unit/inputComponent.spec.ts` (10 lines)
- `tests/core/unit/inputListComponent.spec.ts` (2 lines)
- `tests/core/unit/intComponent.spec.ts` (6 lines)
- `tests/core/unit/keyPairListComponent.spec.ts` (6 lines)
- `tests/core/unit/promptModalComponent.spec.ts` (11 lines)
- `tests/core/unit/queryInputComponent.spec.ts` (2 lines)
- `tests/core/unit/sliderComponent.spec.ts` (2 lines)
- `tests/core/unit/toggleComponent.spec.ts` (6 lines)
- `tests/extended/features/limit-file-size-upload.spec.ts` (2 lines)
- `tests/extended/integrations/chatInputOutputUser-shard-2.spec.ts` (4 lines)
- `tests/extended/regression/general-bugs-agent-sum-duplicate-message-playground.spec.ts` (5 lines)
- `tests/extended/regression/general-bugs-delete-handle-advanced-input.spec.ts` (4 lines)
- `tests/extended/regression/generalBugs-shard-7.spec.ts` (26 lines)
- `tests/core/regression/generalBugs-prompt.spec.ts` (2 lines)

**Deleted:**
- `tests/extended/features/output-modal-copy-button.spec.ts` (132 lines removed -- output modal eliminated)

---

## 27. Miscellaneous UI Tweaks

### Summary
Small UI changes that don't fit neatly into other features.

### Files

**`src/frontend/src/components/common/loadingComponent/index.tsx`** (73 lines changed)
- Redesigned loading animation (new SVG assets)

**`src/frontend/src/assets/langflow-loading-draw.svg`** (new)
**`src/frontend/src/assets/langflow-loading.svg`** (new)
- New loading animation assets

**`src/frontend/src/components/core/appHeaderComponent/index.tsx`** (8 lines changed)
- Minor header adjustments

**`src/frontend/src/components/core/appHeaderComponent/components/langflow-counts.tsx`** (6 lines changed)
- Count display tweaks

**`src/lfx/src/lfx/_assets/component_index.json`** (436 lines changed)
- Rebuilt component index reflecting all component changes

**`src/lfx/src/lfx/_assets/stable_hash_history.json`** (18 lines changed)
- Updated hash history

**`src/lfx/tests/data/starter_projects_1_6_0/Custom Component Generator.json`** (2 lines changed)
- Test data update

---

## File Cross-Reference (Verification)

Every file from `git diff main --name-only` is accounted for above. The following files appear in git status as untracked (`??`) and are NOT part of the committed diff -- they are work-in-progress:

- `src/backend/base/langflow/api/v1/scorer/` (untracked directory)
- `src/frontend/src/components/common/caseStudyGrid/` (untracked directory)
- `src/frontend/src/controllers/API/queries/models/use-get-llm-models.ts` (untracked file)
- `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/SavedComponentsSidebarGroup.tsx` (untracked file)

The following files in the diff are data/temporary artifacts (not code):
- `.playwright-mcp/run_flow_state.png`
- `haha.csv`, `mindscape.csv`, `mindscape_split.csv`, `prs.csv`

---

## Implementation Order Recommendation

For implementing these features in `main`, the recommended dependency order is:

```
1. File & SaveFile Changes (#22) -- standalone
2. Loading.py Fix (#21) -- standalone
3. Modal Autofocus Removal (#23) -- standalone
4. YouTube Comments Fix (#15) -- standalone
5. Knowledge Ingestion Batch Fix (#14) -- standalone
6. Input/Output Legacy Tags (#19) -- standalone
7. Loop Dual Mode (#16) -- standalone
8. CombineInputs Rename (#18) -- standalone
9. Unified Operations Component (#11) -- standalone
10. Knowledge Info & Exact Match (#13) -- standalone
11. Component Context & Memory (#20) -- standalone
12. Auto Type Coercion (#12) -- standalone
13. API Response Component (#8) -- standalone
14. Inspection Panel (#1) -- large, standalone
15. Component Progress Bar (#17) -- depends on flow store from #1
16. Tool Router + Dynamic Outputs (#10) -- depends on flow store from #1
17. Native Tracing System (#2) -- standalone backend
18. Workflow V2 API (#7) -- depends on #20
19. API Modal Redesign (#9) -- depends on #7
20. Sidebar Navigation (#6) -- depends on #1
21. Logs/Messages/Traces Frontend (#3) -- depends on #2, #6
22. Datasets (#4) -- standalone but needed by #5
23. Evaluations (#5) -- depends on #4
24. Alembic Migration Merge (#25) -- after all migrations
25. Starter Project Updates (#24) -- after all component changes
26. Test Updates (#26) -- after #1 (inspection panel)
27. Misc UI Tweaks (#27) -- anytime
```
