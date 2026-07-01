# IBM Accessibility Level 1 — Validation Tracker

> Companion to the criteria guide: [IBM_ACCESSIBILITY_LEVEL1.md](IBM_ACCESSIBILITY_LEVEL1.md)
> Scope: Langflow frontend (`src/frontend/src`). Standard: IBM Equal Access Toolkit v7.3 — Level 1.

This is a **manual validation tracker**. It does not run any checks — shared checklist to confirm each piece of UI has been validated for IBM Level 1 accessibility. It complements the automated scanners in [`scripts/a11y/`](scripts/a11y/) and [`src/frontend/tests/a11y/`](src/frontend/tests/a11y); it does not replace them.

> **Validation method (2026-07-01): static source-code audit.** The current checkbox states were set by reading each component/route's source and judging it against the essentials in [IBM_ACCESSIBILITY_LEVEL1.md](IBM_ACCESSIBILITY_LEVEL1.md). This is **not** a substitute for the IBM Equal Access Checker or a real keyboard/screen-reader pass — treat `[x]` as "no blocking issue found in code," not "certified."
> - **What gates a check:** code-verifiable, non-visual essentials — accessible name/role/value (4.1.2), keyboard operability and no traps (2.1.1/2.1.2), labels/instructions (3.3.2/1.3.1), image text alternatives (1.1.1), status roles (4.1.3), focus management (2.4.3/2.4.7), and dragging alternatives (2.5.7). A missing one leaves the box empty with a `> Gap:` note.
> - **What does NOT gate a check (visual, needs human eyes):** color/contrast (1.4.3/1.4.11), resize/zoom & reflow (1.4.4/1.4.10), text spacing (1.4.12). When one of these is the only open question, the item is marked `[x]` with a `> Note:` pointing to what to confirm visually.
> - **Cannot be verified statically at all:** actual runtime focus visibility, screen-reader output, and true contrast/reflow — these still require the manual + automated passes above.

---

## How to use this document

1. **Validate a component once, in the Registry (Section A).** Every reusable component has exactly one checkbox there.
2. **Routes (Section B) do NOT re-check shared components.** A route lists the components it renders as links back to their Registry entry. The only checkbox a route owns is its own route-specific shell.
3. **Tick a box only when the item passes IBM Level 1** per the criteria in [IBM_ACCESSIBILITY_LEVEL1.md](IBM_ACCESSIBILITY_LEVEL1.md) (keyboard, focus, name/role/value, contrast, labels, etc.).

### Checkbox legend

- `- [ ]` — not yet validated
- `- [x]` — validated for IBM Level 1
- Append `(N/A)` to any item that renders no interactive/perceivable UI (e.g. a pure layout/util module) after confirming it.

### Progress convention

Each section heading carries a running count `x/N`. Update the `x` as boxes are ticked.

### Coverage guarantee

- **Section A** enumerates every reusable component under `components/{ui,common,core}` and `modals/` — so nothing reusable is missed.
- **Section B** enumerates every route/surface and lists the components it renders.
- Because routes are only ever composed of Registry items, **if every Registry box is ticked, every route is covered.** The two sections cross-check each other.

---

## Section A — Shared Component Registry

The primary, complete inventory. One checkbox per reusable component, grouped by source folder so it maps 1:1 to the codebase.

### A1. UI primitives

**Progress: 30/39** (+7 N/A) · `src/frontend/src/components/ui/`

- [x] **TextShimmer** — `components/ui/TextShimmer.tsx`
  > Note: renders real text (readable by AT); confirm color contrast of the gradient text and that the continuous shimmer animation is acceptable (1.4.3).
- [x] **accordion** — `components/ui/accordion.tsx`
- [x] **alert** — `components/ui/alert.tsx`
- [x] **animated-close** — `components/ui/animated-close.tsx`
- [ ] **background-gradient** (N/A - decorative) — `components/ui/background-gradient.tsx`
- [x] **badge** — `components/ui/badge.tsx`
  > Note: confirm color contrast for each badge variant (1.4.3 / 1.4.11).
- [x] **button** — `components/ui/button.tsx`
- [ ] **card** (N/A - presentational container) — `components/ui/card.tsx`
- [x] **checkbox** — `components/ui/checkbox.tsx`
- [ ] **checkmark** (N/A - decorative icon) — `components/ui/checkmark.tsx`
- [x] **command** — `components/ui/command.tsx`
- [x] **context-menu** — `components/ui/context-menu.tsx`
- [x] **dialog** — `components/ui/dialog.tsx`
- [x] **dialog-with-no-close** — `components/ui/dialog-with-no-close.tsx`
- [x] **disclosure** — `components/ui/disclosure.tsx`
- [ ] **dot-background** (N/A - decorative) — `components/ui/dot-background.tsx`
- [x] **dropdown-menu** — `components/ui/dropdown-menu.tsx`
- [x] **input** — `components/ui/input.tsx`
- [x] **label** — `components/ui/label.tsx`
- [x] **loading** — `components/ui/loading.tsx`
- [x] **popover** — `components/ui/popover.tsx`
- [x] **radio-group** — `components/ui/radio-group.tsx`
- [ ] **refreshButton** — `components/ui/refreshButton.tsx`
  > Gap: icon-only path (no `button_text`) sets no `aria-label`; the refresh icon needs an accessible name (2.4.4 / 4.1.2).
- [x] **select** — `components/ui/select.tsx`
- [x] **select-custom** — `components/ui/select-custom.tsx`
- [x] **separator** — `components/ui/separator.tsx`
- [x] **sidebar** — `components/ui/sidebar.tsx`
- [x] **simple-sidebar** — `components/ui/simple-sidebar.tsx`
- [ ] **skeleton** (N/A - decorative placeholder) — `components/ui/skeleton.tsx`
- [ ] **skeletonGroup** (N/A - decorative placeholder) — `components/ui/skeletonGroup.tsx`
- [x] **switch** — `components/ui/switch.tsx`
- [x] **table** — `components/ui/table.tsx`
- [x] **tabs** — `components/ui/tabs.tsx`
- [x] **tabs-button** — `components/ui/tabs-button.tsx`
- [ ] **text-loop** — `components/ui/text-loop.tsx`
  > Gap: auto-cycles text on a timer with no pause/stop control (2.2.2 Pause, Stop, Hide).
- [x] **textAnimation** — `components/ui/textAnimation.tsx`
- [x] **textarea** — `components/ui/textarea.tsx`
- [x] **tooltip** — `components/ui/tooltip.tsx`
- [ ] **xmark** (N/A - decorative icon) — `components/ui/xmark.tsx`

### A2. Common components

**Progress: 18/26** (+4 N/A) · `src/frontend/src/components/common/`

- [ ] **GradientWrapper** (N/A - decorative svg gradient def) — `components/common/GradientWrapper`
- [ ] **ImageViewer** — `components/common/ImageViewer`
  > Gap: icon-only zoom/home/fullscreen/download `<button>`s have no `aria-label`/text (2.4.4 / 4.1.2); the viewer image has no text alternative (1.1.1).
- [x] **accordionComponent** — `components/common/accordionComponent`
- [x] **animatedNumbers** — `components/common/animatedNumbers`
- [x] **crashErrorComponent** — `components/common/crashErrorComponent`
- [x] **fetchErrorComponent** — `components/common/fetchErrorComponent`
- [x] **genericIconComponent** — `components/common/genericIconComponent`
- [ ] **horizontalScrollFadeComponent** (N/A - decorative scroll fade) — `components/common/horizontalScrollFadeComponent`
- [x] **loadingComponent** — `components/common/loadingComponent`
- [x] **loadingTextComponent** — `components/common/loadingTextComponent`
- [x] **messageMetadataComponent** — `components/common/messageMetadataComponent`
- [x] **modelProviderCountComponent** — `components/common/modelProviderCountComponent`
- [x] **numberReader** — `components/common/numberReader`
- [x] **objectRender** — `components/common/objectRender`
- [x] **pageLayout** — `components/common/pageLayout`
- [x] **paginatorComponent** — `components/common/paginatorComponent`
- [x] **renderIconComponent** — `components/common/renderIconComponent` (includes `renderKey`)
- [ ] **safari-scroll-fix** (N/A - util, renders no UI) — `components/common/safari-scroll-fix.tsx`
- [ ] **sanitizedHTMLWrapper** — `components/common/sanitizedHTMLWrapper`
  > Note: passthrough that injects sanitized HTML; its accessibility depends entirely on the caller-provided content, so it cannot be validated in isolation.
- [x] **shadTooltipComponent** — `components/common/shadTooltipComponent`
- [ ] **skeletonCardComponent** (N/A - decorative placeholder) — `components/common/skeletonCardComponent`
- [ ] **storeCardComponent** — `components/common/storeCardComponent`
  > Gap: icon-only like/install buttons rely on tooltip only (no `aria-label`, 4.1.2); liked state is conveyed by fill color alone (1.4.1).
- [x] **stringReaderComponent** — `components/common/stringReaderComponent`
- [ ] **tagsSelectorComponent** — `components/common/tagsSelectorComponent`
  > Gap: selected-tag state is conveyed by background color only, with no `aria-pressed`/programmatic state (1.4.1 / 4.1.2).
- [x] **timeoutErrorComponent** — `components/common/timeoutErrorComponent`
- [x] **versionLabelComponent** — `components/common/versionLabelComponent`

### A3. Core components

**Progress: 22/25** (+1 N/A) · `src/frontend/src/components/core/`

- [x] **GlobalVariableModal** — `components/core/GlobalVariableModal`
- [x] **appHeaderComponent** — `components/core/appHeaderComponent`
- [x] **assistantPanel** — `components/core/assistantPanel`
- [ ] **border-trail** (N/A - decorative animated border) — `components/core/border-trail.tsx`
- [x] **canvasControlsComponent** — `components/core/canvasControlsComponent`
- [x] **cardComponent** — `components/core/cardComponent`
  > Note: card is `draggable`; confirm a non-drag alternative exists where used (2.5.7) - the collection cards are also click/keyboard openable.
- [x] **cardsWrapComponent** — `components/core/cardsWrapComponent`
- [x] **chatComponents** — `components/core/chatComponents`
- [ ] **codeTabsComponent** — `components/core/codeTabsComponent`
  > Gap: icon-only copy-code button has no `aria-label`/text (2.4.4 / 4.1.2).
- [x] **csvOutputComponent** — `components/core/csvOutputComponent`
- [x] **dataOutputComponent** — `components/core/dataOutputComponent`
- [x] **dateReaderComponent** — `components/core/dateReaderComponent`
- [x] **dropdownComponent** — `components/core/dropdownComponent`
- [x] **editFlowSettingsComponent** — `components/core/editFlowSettingsComponent`
- [x] **flowBuilderWelcome** — `components/core/flowBuilderWelcome`
- [x] **flowSettingsComponent** — `components/core/flowSettingsComponent`
- [x] **flowToolbarComponent** — `components/core/flowToolbarComponent`
- [x] **folderSidebarComponent** — `components/core/folderSidebarComponent`
- [x] **jsonEditor** — `components/core/jsonEditor`
- [x] **jsonOutputComponent** — `components/core/jsonOutputComponent`
- [x] **parameterRenderComponent** (container; inputs listed in A4) — `components/core/parameterRenderComponent`
- [ ] **pdfViewer** — `components/core/pdfViewer`
  > Gap: icon-only page-nav and zoom `<button>`s have no accessible name (2.4.4 / 4.1.2) and the scale `<input type="number">` has no label (3.3.2).
- [x] **playgroundComponent** — `components/core/playgroundComponent`
  > Note: large composite chat surface built on labeled inputs/menus; recommend a dedicated manual keyboard + screen-reader pass in addition to this static check.
- [x] **sanitizedMarkdown** — `components/core/sanitizedMarkdown`
- [x] **sidebarComponent** — `components/core/sidebarComponent`

### A4. Parameter input components

**Progress: 29/34** (+1 N/A) · `src/frontend/src/components/core/parameterRenderComponent/components/` — the form/input widgets rendered across node config, settings, and forms. High a11y priority (labels, keyboard, name/role/value).

- [x] **TableNodeComponent** — `.../TableNodeComponent`
- [x] **ToolsComponent** — `.../ToolsComponent`
- [x] **accordionPromptComponent** — `.../accordionPromptComponent`
- [x] **codeAreaComponent** — `.../codeAreaComponent`
  > Note: wraps a code editor; confirm the editor surface exposes an accessible name and keyboard operation in a manual pass.
- [x] **connectionComponent** — `.../connectionComponent`
- [x] **copyFieldAreaComponent** — `.../copyFieldAreaComponent`
- [x] **dbProviderInputComponent** — `.../dbProviderInputComponent`
- [x] **dictComponent** — `.../dictComponent`
- [x] **dropdownComponent** — `.../dropdownComponent`
- [ ] **emptyParameterComponent** (N/A - renders no interactive/perceivable UI) — `.../emptyParameterComponent`
- [x] **floatComponent** — `.../floatComponent`
- [x] **helperTextComponent** — `.../helperTextComponent`
- [x] **inputComponent** — `.../inputComponent`
- [x] **inputFileComponent** — `.../inputFileComponent`
- [x] **inputGlobalComponent** — `.../inputGlobalComponent`
- [ ] **inputListComponent** — `.../inputListComponent`
  > Gap: icon-only delete (`X`) button has no `aria-label`/text (2.4.4 / 4.1.2).
- [x] **intComponent** — `.../intComponent`
- [ ] **keypairListComponent** — `.../keypairListComponent`
  > Gap: icon-only add/remove (`Plus`/`Trash2`) buttons have no accessible name (2.4.4 / 4.1.2); key/value inputs use placeholder only, no programmatic label (3.3.2).
- [x] **linkComponent** — `.../linkComponent`
- [x] **mcpComponent** — `.../mcpComponent`
- [x] **modelInputComponent** — `.../modelInputComponent`
- [x] **multiselectComponent** — `.../multiselectComponent`
- [x] **mustachePromptComponent** — `.../mustachePromptComponent`
- [x] **promptComponent** — `.../promptComponent`
- [x] **queryComponent** — `.../queryComponent`
- [ ] **searchBarComponent** — `.../searchBarComponent`
  > Gap: search input relies on `placeholder` as its only label; add a visible `<label>`/`aria-label` (3.3.2).
- [x] **sliderComponent** — `.../sliderComponent`
- [ ] **sortableListComponent** — `.../sortableListComponent`
  > Gap: uses drag-to-reorder (react-sortablejs) with no keyboard/non-drag alternative (2.5.7 Dragging Movements).
- [x] **strRenderComponent** — `.../strRenderComponent`
- [x] **tabComponent** — `.../tabComponent`
- [x] **tableComponent** — `.../tableComponent`
  > Note: ag-grid data grid; confirm grid keyboard navigation and header semantics in a manual pass.
- [x] **textAreaComponent** — `.../textAreaComponent`
- [x] **toggleShadComponent** — `.../toggleShadComponent`
- [x] **webhookFieldComponent** — `.../webhookFieldComponent`

### A5. Shared modals

**Progress: 31/31** · `src/frontend/src/modals/` — reused across many routes. `baseModal` (Radix Dialog: focus trap, Escape to close, focus restore, `DialogTitle`/`aria-label`) is the a11y-tested shell most modals build on, so modals inherit the accessible dialog behavior. Internal control gaps (e.g. copy button, search bar) are tracked on the reused registry entries, not duplicated here.

- [x] **EmbedModal** — `modals/EmbedModal`
- [x] **IOModal** — `modals/IOModal` (playground chat, session view)
  > Note: large composite surface (chat, voice assistant, sessions); recommend a dedicated manual keyboard + screen-reader pass in addition to this static check.
- [x] **addMcpServerModal** — `modals/addMcpServerModal`
- [x] **apiModal** — `modals/apiModal`
- [x] **authModal** — `modals/authModal`
- [x] **baseModal** — `modals/baseModal`
- [x] **codeAreaModal** — `modals/codeAreaModal`
- [x] **confirmationModal** — `modals/confirmationModal`
- [x] **createMemoryModal** — `modals/createMemoryModal`
- [x] **deleteConfirmationModal** — `modals/deleteConfirmationModal`
- [x] **dictAreaModal** — `modals/dictAreaModal`
- [x] **editNodeModal** — `modals/editNodeModal`
- [x] **exportModal** — `modals/exportModal`
- [x] **fileManagerModal** — `modals/fileManagerModal`
- [x] **flowSettingsModal** — `modals/flowSettingsModal`
- [x] **knowledgeBaseUploadModal** — `modals/knowledgeBaseUploadModal`
- [x] **modelProviderModal** — `modals/modelProviderModal`
- [x] **mustachePromptModal** — `modals/mustachePromptModal`
- [x] **promptModal** — `modals/promptModal`
- [x] **queryModal** — `modals/queryModal`
- [x] **saveChangesModal** — `modals/saveChangesModal`
- [x] **secretKeyModal** — `modals/secretKeyModal`
- [x] **shareModal** — `modals/shareModal`
- [x] **stepperModal** — `modals/stepperModal`
- [x] **tableModal** — `modals/tableModal`
- [x] **templatesModal** — `modals/templatesModal`
- [x] **textAreaModal** — `modals/textAreaModal`
- [x] **textModal** — `modals/textModal`
- [x] **toolsModal** — `modals/toolsModal`
- [x] **updateComponentModal** — `modals/updateComponentModal`
- [x] **userManagementModal** — `modals/userManagementModal`

---

## Section B — Route & Surface Map

Every route/surface from [`scripts/a11y/a11y_routes.json`](scripts/a11y/a11y_routes.json) and [`src/frontend/src/routes.tsx`](src/frontend/src/routes.tsx). Each route owns **one checkbox** — its route-specific shell (page component). "Reused components" are links back to Section A and are **not** re-checked here. Reused lists were derived from each page's actual `import` statements.

### B0. Global chrome (shared by all authenticated routes) — 5/5

Validated once; every route below inherits it.

- [x] **App header** — `components/core/appHeaderComponent` (see [A3](#a3-core-components))
- [x] **Left nav / folder sidebar** — `components/core/folderSidebarComponent` + `components/core/sidebarComponent` (see [A3](#a3-core-components))
- [x] **Page layout wrapper** — `components/common/pageLayout` (see [A2](#a2-common-components))
- [x] **Dashboard wrapper shell** — `pages/DashboardWrapperPage`
- [x] **Collection/main-page shell** — `pages/MainPage/pages/main-page.tsx` (uses `ui/sidebar`, `folderSidebarComponent`)

### B1. Static routes — 15/15

#### `/flows` · `/all` · `/components` · `/mcp` — Home / collection lists
- [x] **Route shell** — `pages/MainPage/pages/homePage`
- Reused → **UI:** `button`, `tabs-button` ([A1](#a1-ui-primitives)) · **Common:** `genericIconComponent`, `shadTooltipComponent`, `paginatorComponent` ([A2](#a2-common-components)) · **Core:** `cardsWrapComponent`, `flowBuilderWelcome` ([A3](#a3-core-components)) · **Inputs:** `ToolsComponent` ([A4](#a4-parameter-input-components)) · **Modals:** `authModal` ([A5](#a5-shared-modals))

#### `/assets/files` — Files page
- [x] **Route shell** — `pages/MainPage/pages/filesPage`
- Reused → **UI:** `button`, `input`, `loading`, `sidebar` ([A1](#a1-ui-primitives)) · **Common:** `genericIconComponent`, `shadTooltipComponent` ([A2](#a2-common-components)) · **Core:** `cardsWrapComponent` ([A3](#a3-core-components)) · **Inputs:** `tableComponent` ([A4](#a4-parameter-input-components)) · **Modals:** `deleteConfirmationModal`, `fileManagerModal` ([A5](#a5-shared-modals))

#### `/assets/knowledge-bases` — Knowledge bases page
- [x] **Route shell** — `pages/MainPage/pages/knowledgePage`
- Reused → **UI:** `button`, `input`, `loading`, `badge`, `separator`, `popover`, `command`, `dropdown-menu`, `tooltip`, `sidebar` ([A1](#a1-ui-primitives)) · **Common:** `genericIconComponent`, `loadingTextComponent` ([A2](#a2-common-components)) · **Inputs:** `tableComponent` ([A4](#a4-parameter-input-components)) · **Modals:** `deleteConfirmationModal`, `knowledgeBaseUploadModal` ([A5](#a5-shared-modals))

#### `/settings` shell (wraps all settings pages)
- [x] **Route shell** — `pages/SettingsPage` (uses `components/core/sidebarComponent`, `ui/sidebar`)

#### `/settings/general` — General settings
- [x] **Route shell** — `pages/SettingsPage/pages/GeneralPage`
- Reused → **UI:** `select` ([A1](#a1-ui-primitives)) · page-local `ProfilePictureForm/profilePictureChooserComponent`

#### `/settings/global-variables` — Global variables
- [x] **Route shell** — `pages/SettingsPage/pages/GlobalVariablesPage`
- Reused → **Core:** `dropdownComponent`, `GlobalVariableModal` ([A3](#a3-core-components)) · **Inputs:** `tableComponent` ([A4](#a4-parameter-input-components))

#### `/settings/model-providers` — Model providers
- [x] **Route shell** — `pages/SettingsPage/pages/ModelProvidersPage`
- Reused → **Common:** `genericIconComponent` ([A2](#a2-common-components)) · **Modals:** `modelProviderModal` ([A5](#a5-shared-modals))

#### `/settings/db-providers` — DB providers
- [x] **Route shell** — `pages/SettingsPage/pages/DBProvidersPage`
- Reused → **UI:** `badge`, `button`, `input`, `switch` ([A1](#a1-ui-primitives)) · **Common:** `genericIconComponent` ([A2](#a2-common-components))

#### `/settings/mcp-servers` — MCP servers
- [x] **Route shell** — `pages/SettingsPage/pages/MCPServersPage`
- Reused → **UI:** `button`, `dropdown-menu`, `loading` ([A1](#a1-ui-primitives)) · **Common:** `genericIconComponent`, `shadTooltipComponent` ([A2](#a2-common-components)) · **Modals:** `addMcpServerModal`, `deleteConfirmationModal` ([A5](#a5-shared-modals))

#### `/settings/mcp-client` — MCP client
- [x] **Route shell** — `pages/SettingsPage/pages/McpClientPage`
- Reused → **UI:** `button` ([A1](#a1-ui-primitives)) · **Common:** `genericIconComponent` ([A2](#a2-common-components))

#### `/settings/api-keys` — API keys
- [x] **Route shell** — `pages/SettingsPage/pages/ApiKeysPage`
- Reused → **UI:** `tooltip` ([A1](#a1-ui-primitives)) · **Core:** `dateReaderComponent` ([A3](#a3-core-components)) · **Inputs:** `tableComponent` (tableAutoCellRender) ([A4](#a4-parameter-input-components))

#### `/settings/shortcuts` — Shortcuts
- [x] **Route shell** — `pages/SettingsPage/pages/ShortcutsPage`
- Reused → **Common:** `renderIconComponent` (+ `renderKey`) ([A2](#a2-common-components))

#### `/settings/messages` — Messages
- [x] **Route shell** — `pages/SettingsPage/pages/messagesPage`
- Reused → **Modals:** `IOModal` (session-view) ([A5](#a5-shared-modals))

#### `/settings/store` — Store API key
- [x] **Route shell** — `pages/SettingsPage/pages/StoreApiKeyPage`
- Reused → **Common:** `genericIconComponent` ([A2](#a2-common-components))

#### `/account/delete` — Delete account
- [x] **Route shell** — `pages/DeleteAccountPage`
- Reused → **UI:** `button`, `input` ([A1](#a1-ui-primitives)) · **Modals:** `baseModal` ([A5](#a5-shared-modals))

### B2. Dynamic routes — 4/4

#### `/flow/:id/` — Flow editor (canvas)
The richest surface. Also hosts the flow sidebar, node toolbar, inspection panel, trace panel, and memories panel (page-local under `pages/FlowPage/components/*`).
- [x] **Route shell** — `pages/FlowPage` (page-local children: `flowSidebarComponent`, `PageComponent`, `nodeToolbarComponent`, `InspectionPanel`, `TraceComponent`, `MemoriesMainContent`, `UpdateAllComponents`)
  > Note: richest surface (React Flow canvas + panels); it renders a `<main>` landmark, but node drag/drop and canvas interactions need a dedicated manual keyboard + screen-reader pass beyond this static check.
- Reused → **UI:** `button`, `input`, `checkbox`, `switch`, `badge`, `loading`, `accordion`, `alert`, `dialog`, `popover`, `dropdown-menu`, `tooltip`, `select`, `select-custom`, `disclosure`, `sidebar`, `simple-sidebar`, `skeletonGroup`, `table`, `TextShimmer` ([A1](#a1-ui-primitives)) · **Common:** `genericIconComponent`, `shadTooltipComponent`, `versionLabelComponent`, `stringReaderComponent`, `paginatorComponent`, `storeCardComponent` (util) ([A2](#a2-common-components)) · **Core:** `flowToolbarComponent`, `flowBuilderWelcome`, `assistantPanel`, `playgroundComponent`, `canvasControlsComponent`, `border-trail`, `codeTabsComponent` ([A3](#a3-core-components)) · **Inputs:** `toggleShadComponent`, `tableComponent`, and node config inputs ([A4](#a4-parameter-input-components)) · **Modals:** `saveChangesModal`, `createMemoryModal`, `updateComponentModal`, `codeAreaModal`, `confirmationModal`, `editNodeModal`, `shareModal`, `deleteConfirmationModal`, `addMcpServerModal` ([A5](#a5-shared-modals))

#### `/flow/:id/view` — Flow view (read-only canvas)
- [x] **Route shell** — `pages/ViewPage` (renders `pages/FlowPage/components/PageComponent`; validate any view-only differences from the flow editor)

#### `/playground/:id/` — Shared playground
- [x] **Route shell** — `pages/Playground`
- Reused → **Modals:** `IOModal` (via `customization/components/custom-new-modal`) ([A5](#a5-shared-modals)) · **Core:** `playgroundComponent` ([A3](#a3-core-components))

#### `/assets/knowledge-bases/:sourceId/chunks` — KB source chunks
- [x] **Route shell** — `pages/MainPage/pages/knowledgePage/sourceChunksPage`
- Reused → **UI:** `button`, `input`, `loading`, `select`, `sidebar`, `badge`, `popover`, `command` ([A1](#a1-ui-primitives)) · **Common:** `genericIconComponent` ([A2](#a2-common-components))

### B3. Gated routes (auth/role/environment specific) — 6/6

#### `/login` — Login
- [x] **Route shell** — `pages/LoginPage`
- Reused → **UI:** `button`, `input` ([A1](#a1-ui-primitives)) · **Common:** `shadTooltipComponent` ([A2](#a2-common-components)) · **Inputs:** `inputComponent` ([A4](#a4-parameter-input-components))

#### `/signup` — Sign up
- [x] **Route shell** — `pages/SignUpPage`
- Reused → **Common:** `shadTooltipComponent` ([A2](#a2-common-components)) · **Inputs:** `inputComponent` ([A4](#a4-parameter-input-components))

#### `/login/admin` — Admin login
- [x] **Route shell** — `pages/AdminPage/LoginPage`
- Reused → **UI:** `button`, `input` ([A1](#a1-ui-primitives))

#### `/admin` — Admin page
- [x] **Route shell** — `pages/AdminPage`
- Reused → **Common:** `paginatorComponent` ([A2](#a2-common-components)) · **Modals:** `userManagementModal`, `confirmationModal` ([A5](#a5-shared-modals))

#### `/store` — Store
- [x] **Route shell** — `pages/StorePage`
- Reused → **Common:** `paginatorComponent`, `storeCardComponent` ([A2](#a2-common-components))

#### `/store/:id/` — Store item detail
- [x] **Route shell** — `pages/StorePage` (detail view)
- Reused → **Common:** `storeCardComponent` ([A2](#a2-common-components))

---

## Section C — Keeping this tracker complete

Because IBM Level 1 coverage must not have gaps, keep the two sections in sync with the code:

1. **New component** under `components/{ui,common,core}` or a new `modals/` folder → add a row to the matching Registry subsection (A1–A5) and bump that subsection's `x/N` denominator.
2. **New parameter input** under `parameterRenderComponent/components/` → add a row to **A4**.
3. **New route** in [`src/frontend/src/routes.tsx`](src/frontend/src/routes.tsx) → add it to [`scripts/a11y/a11y_routes.json`](scripts/a11y/a11y_routes.json) (per that file's convention) **and** add a route entry to Section B, populating "Reused" from the page's `import` statements.
4. **Refactor that moves imports** → re-derive the affected route's "Reused" list. Coverage still holds via the Registry even if a route list drifts, but keep it accurate.
5. **Cross-check periodically:** every component in Section A should appear in at least one Section B route (or be intentionally unused); every route in `a11y_routes.json` should have a Section B entry.

> Reminder: ticking a box means the item was manually validated against [IBM_ACCESSIBILITY_LEVEL1.md](IBM_ACCESSIBILITY_LEVEL1.md), ideally corroborated by the IBM Equal Access Checker and a keyboard/screen-reader pass.
