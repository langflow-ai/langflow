# Component Splitting Patterns

This document provides detailed guidance on splitting large components into smaller, focused components in Langflow.

## When to Split Components

Split a component when you identify:

1. **Multiple UI sections** - Distinct visual areas with minimal coupling that can be composed independently
1. **Conditional rendering blocks** - Large `{condition && <JSX />}` blocks
1. **Repeated patterns** - Similar UI structures used multiple times
1. **300+ lines** - Component exceeds manageable size
1. **Modal clusters** - Multiple modals rendered in one component

## Splitting Strategies

### Strategy 1: Section-Based Splitting

Identify visual sections and extract each as a component.

```typescript
// Before: Monolithic component (500+ lines)
const FlowPage = () => {
  return (
    <div className="flex h-full w-full">
      {/* Sidebar Section - 100 lines */}
      <div className="w-64 border-r">
        <input placeholder="Search components..." />
        {categories.map((cat) => (
          <div key={cat.name}>
            <h3>{cat.name}</h3>
            {cat.components.map((comp) => (
              <div key={comp.name} draggable>
                {comp.display_name}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Canvas Section - 200 lines */}
      <div className="flex-1">
        <ReactFlow nodes={nodes} edges={edges} onConnect={onConnect}>
          {/* toolbar, minimap, controls */}
        </ReactFlow>
      </div>

      {/* Inspect Panel Section - 150 lines */}
      {showInspectPanel && (
        <div className="w-80 border-l">
          {selectedNode && <NodeInspector node={selectedNode} />}
        </div>
      )}

      {/* Modals Section - 50 lines */}
      {showExportModal && <ExportModal />}
      {showShareModal && <ShareModal />}
    </div>
  )
}

// After: Split into focused components (kebab-case, descriptive names — NEVER index.tsx)
// pages/FlowPage/
//   flow-page.tsx              (orchestration)
//   components/
//     flow-sidebar.tsx
//     flow-canvas.tsx
//     flow-inspect-panel.tsx
//     flow-modals.tsx

// FlowSidebar.tsx
interface FlowSidebarProps {
  categories: Category[]
  searchTerm: string
  onSearchChange: (term: string) => void
}

const FlowSidebar: FC<FlowSidebarProps> = ({
  categories,
  searchTerm,
  onSearchChange,
}) => {
  return (
    <div className="w-64 border-r">
      <input
        placeholder="Search components..."
        value={searchTerm}
        onChange={(e) => onSearchChange(e.target.value)}
      />
      {categories.map((cat) => (
        <SidebarCategory key={cat.name} category={cat} />
      ))}
    </div>
  )
}

// flow-page.tsx (orchestration only — kebab-case, NOT index.tsx)
const FlowPage = () => {
  const { nodes, edges, onConnect } = useFlowState()
  const { activeModal, openModal, closeModal } = useModalState()
  const [searchTerm, setSearchTerm] = useState("")

  return (
    <div className="flex h-full w-full">
      <FlowSidebar
        categories={filteredCategories}
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
      />
      <FlowCanvas
        nodes={nodes}
        edges={edges}
        onConnect={onConnect}
      />
      {showInspectPanel && (
        <FlowInspectPanel selectedNode={selectedNode} />
      )}
      <FlowModals
        activeModal={activeModal}
        onClose={closeModal}
      />
    </div>
  )
}
```

### Strategy 2: Conditional Block Extraction

Extract large conditional rendering blocks.

```typescript
// Before: Large conditional blocks
const NodeField = ({ field }: { field: InputFieldType }) => {
  return (
    <div>
      {field.show ? (
        <div className="field-visible">
          {field.load_from_db ? (
            <div className="global-variable-badge">
              <Badge>{field.value}</Badge>
              <Button onClick={() => clearGlobalVariable(field.name)}>
                Clear
              </Button>
            </div>
          ) : field.type === "str" && field.multiline ? (
            <TextAreaComponent
              value={field.value}
              onChange={(val) => handleChange(field.name, val)}
            />
          ) : field.type === "str" ? (
            <InputComponent
              value={field.value}
              onChange={(val) => handleChange(field.name, val)}
              password={field.password}
            />
          ) : field.type === "code" ? (
            <CodeAreaComponent
              value={field.value}
              onChange={(val) => handleChange(field.name, val)}
            />
          ) : (
            <GenericInput field={field} onChange={handleChange} />
          )}
        </div>
      ) : null}
    </div>
  )
}

// After: Separate rendering components
const GlobalVariableBadge: FC<{ field: InputFieldType; onClear: () => void }> = ({
  field,
  onClear,
}) => (
  <div className="global-variable-badge">
    <Badge>{field.value}</Badge>
    <Button onClick={onClear}>Clear</Button>
  </div>
)

const FieldInput: FC<{ field: InputFieldType; onChange: FieldChangeHandler }> = ({
  field,
  onChange,
}) => {
  if (field.load_from_db) {
    return <GlobalVariableBadge field={field} onClear={() => onChange(field.name, "")} />
  }

  const Component = getFieldComponent(field)
  return <Component value={field.value} onChange={(val) => onChange(field.name, val)} />
}

const NodeField = ({ field }: { field: InputFieldType }) => {
  if (!field.show) return null

  return (
    <div className="field-visible">
      <FieldInput field={field} onChange={handleChange} />
    </div>
  )
}
```

### Strategy 3: Modal Extraction

Extract modals with their trigger logic.

```typescript
// Before: Multiple modals in one component
const FlowToolbar = () => {
  const [showExport, setShowExport] = useState(false)
  const [showShare, setShowShare] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [showApi, setShowApi] = useState(false)

  const onExport = async (format: string) => { /* 20 lines */ }
  const onShare = async (data: ShareData) => { /* 20 lines */ }
  const onDelete = async () => { /* 15 lines */ }

  return (
    <div>
      {/* Main toolbar content */}

      {showExport && <ExportModal onConfirm={onExport} onClose={() => setShowExport(false)} />}
      {showShare && <ShareModal onConfirm={onShare} onClose={() => setShowShare(false)} />}
      {showDelete && <DeleteConfirm onConfirm={onDelete} onClose={() => setShowDelete(false)} />}
      {showApi && <ApiModal flowId={flowId} onClose={() => setShowApi(false)} />}
    </div>
  )
}

// After: Modal manager component
// flow-toolbar-modals.tsx
type ToolbarModalType = "export" | "share" | "delete" | "api" | null

interface FlowToolbarModalsProps {
  flowId: string
  activeModal: ToolbarModalType
  onClose: () => void
  onSuccess: () => void
}

const FlowToolbarModals: FC<FlowToolbarModalsProps> = ({
  flowId,
  activeModal,
  onClose,
  onSuccess,
}) => {
  const handleExport = async (format: string) => {
    // export logic
    onSuccess()
  }

  const handleShare = async (data: ShareData) => {
    // share logic
    onSuccess()
  }

  const handleDelete = async () => {
    // delete logic
    onSuccess()
  }

  return (
    <>
      {activeModal === "export" && (
        <ExportModal onConfirm={handleExport} onClose={onClose} />
      )}
      {activeModal === "share" && (
        <ShareModal onConfirm={handleShare} onClose={onClose} />
      )}
      {activeModal === "delete" && (
        <DeleteConfirm onConfirm={handleDelete} onClose={onClose} />
      )}
      {activeModal === "api" && (
        <ApiModal flowId={flowId} onClose={onClose} />
      )}
    </>
  )
}

// Parent component
const FlowToolbar = () => {
  const { activeModal, openModal, closeModal } = useModalState()

  return (
    <div>
      {/* Main toolbar with openModal triggers */}
      <Button onClick={() => openModal("export")}>Export</Button>
      <Button onClick={() => openModal("share")}>Share</Button>

      <FlowToolbarModals
        flowId={flowId}
        activeModal={activeModal}
        onClose={closeModal}
        onSuccess={handleSuccess}
      />
    </div>
  )
}
```

### Strategy 4: List Item Extraction

Extract repeated item rendering.

```typescript
// Before: Inline item rendering
const ComponentList = () => {
  return (
    <div>
      {components.map((comp) => (
        <div key={comp.name} className="component-item">
          <div className="flex items-center gap-2">
            {comp.icon && <img src={comp.icon} className="h-5 w-5" />}
            <span className="font-medium">{comp.display_name}</span>
            {comp.beta && <Badge variant="secondary">Beta</Badge>}
            {comp.legacy && <Badge variant="destructive">Legacy</Badge>}
          </div>
          <p className="text-sm text-muted-foreground">{comp.description}</p>
          <div className="flex gap-1">
            {comp.output_types?.map((type) => (
              <Badge key={type} variant="outline">{type}</Badge>
            ))}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleAddToCanvas(comp)}
          >
            Add
          </Button>
        </div>
      ))}
    </div>
  )
}

// After: Extracted item component
interface ComponentItemProps {
  component: APIClassType
  onAdd: (component: APIClassType) => void
}

const ComponentItem: FC<ComponentItemProps> = ({ component, onAdd }) => {
  return (
    <div className="component-item">
      <div className="flex items-center gap-2">
        {component.icon && <img src={component.icon} className="h-5 w-5" />}
        <span className="font-medium">{component.display_name}</span>
        {component.beta && <Badge variant="secondary">Beta</Badge>}
        {component.legacy && <Badge variant="destructive">Legacy</Badge>}
      </div>
      <p className="text-sm text-muted-foreground">{component.description}</p>
      <div className="flex gap-1">
        {component.output_types?.map((type) => (
          <Badge key={type} variant="outline">{type}</Badge>
        ))}
      </div>
      <Button variant="ghost" size="sm" onClick={() => onAdd(component)}>
        Add
      </Button>
    </div>
  )
}

const ComponentList = () => {
  return (
    <div>
      {components.map((comp) => (
        <ComponentItem
          key={comp.display_name}
          component={comp}
          onAdd={handleAddToCanvas}
        />
      ))}
    </div>
  )
}
```

## Directory Structure Patterns

### Pattern A: Flat Structure (Simple Components)

For components with 2-3 sub-components:

```
my-component/
  my-component.tsx        # Main component (kebab-case, descriptive — NOT index.tsx)
  sub-component-a.tsx
  sub-component-b.tsx
  my-component-types.ts   # Shared types
```

### Pattern B: Nested Structure (Complex Components)

For components with many sub-components:

```
my-component/
  my-component.tsx        # Main orchestration (NOT index.tsx)
  my-component-types.ts   # Shared types
  hooks/
    use-feature-a.ts
    use-feature-b.ts
  components/
    header-section.tsx
    content-section.tsx
    modals-section.tsx
  helpers/
    format-data.ts
```

> **IMPORTANT**: Never use `index.tsx` for new files. This is a legacy pattern. Use kebab-case file names that describe the component's purpose.

### Pattern C: Page Structure

Pages follow a standard directory layout with sub-pages, components, hooks, and helpers:

```
pages/SettingsPage/
  settings-page.tsx          # Main page component
  pages/                     # Sub-pages
    ApiKeysPage/
      api-keys-page.tsx
      components/
        api-key-header.tsx
      helpers/
        column-defs.ts
        get-modal-props.tsx
    GlobalVariablesPage/
      global-variables-page.tsx
  components/                # Shared page components
  hooks/                     # Page-level hooks
  utils/                     # Page-level utilities
```

### Pattern D: UI Components (shadcn — kebab-case files)

```
components/ui/
  button.tsx
  input.tsx
  badge.tsx
  dialog.tsx
  popover.tsx
  select.tsx
  textarea.tsx
  tooltip.tsx
  dropdown-menu.tsx
```

### Pattern E: Legacy Codebase (existing — do NOT follow for new code)

The existing codebase has `index.tsx` and mixed naming. When refactoring, migrate toward the new kebab-case standard:

```
// Legacy (existing — DO NOT create new files this way)
components/core/appHeaderComponent/index.tsx
components/common/loadingComponent/index.tsx
CustomNodes/GenericNode/index.tsx

// New standard (use this for all new code and refactors)
components/core/app-header/app-header.tsx
components/common/loading-indicator/loading-indicator.tsx
CustomNodes/GenericNode/generic-node.tsx
    NodeName/
    NodeOutputField/
    NodeStatus/
```

## Props Design

### Minimal Props Principle

Pass only what is needed:

```typescript
// Bad: Passing entire objects when only some fields needed
<NodeHeader nodeData={nodeData} flowData={flowData} />

// Good: Destructure to minimum required
<NodeHeader
  displayName={nodeData.node?.display_name ?? ""}
  nodeType={nodeData.type}
  isFrozen={nodeData.node?.frozen ?? false}
  onNameChange={handleNameChange}
/>
```

### Callback Props Pattern

Use callbacks for child-to-parent communication:

```typescript
// Parent
const GenericNode = () => {
  const [showDescription, setShowDescription] = useState(false)

  return (
    <div>
      <NodeHeader
        displayName={data.node?.display_name ?? ""}
        onToggleDescription={() => setShowDescription((prev) => !prev)}
      />
      {showDescription && (
        <NodeDescription
          description={data.node?.description ?? ""}
          onChange={handleDescriptionChange}
        />
      )}
    </div>
  )
}

// Child
interface NodeHeaderProps {
  displayName: string
  onToggleDescription: () => void
}

const NodeHeader: FC<NodeHeaderProps> = ({ displayName, onToggleDescription }) => {
  return (
    <div className="flex items-center justify-between">
      <span>{displayName}</span>
      <button onClick={onToggleDescription}>Toggle Description</button>
    </div>
  )
}
```

### Render Props for Flexibility

When sub-components need parent context:

```typescript
interface FieldListProps<T> {
  fields: T[]
  renderField: (field: T, index: number) => React.ReactNode
  renderEmpty?: () => React.ReactNode
}

function FieldList<T>({ fields, renderField, renderEmpty }: FieldListProps<T>) {
  if (fields.length === 0 && renderEmpty) {
    return <>{renderEmpty()}</>
  }

  return (
    <div className="flex flex-col gap-2">
      {fields.map((field, index) => renderField(field, index))}
    </div>
  )
}

// Usage
<FieldList
  fields={visibleFields}
  renderField={(field, i) => (
    <NodeInputField key={field.name ?? i} field={field} onChange={handleChange} />
  )}
  renderEmpty={() => <span className="text-muted-foreground">No fields</span>}
/>
```

## Langflow-Specific Splitting Guidelines

### Splitting GenericNode Components

The `GenericNode` component is one of the most complex components in Langflow. When splitting:

1. Keep the main `index.tsx` as an orchestrator that composes sub-components.
2. Parameter rendering goes in `components/NodeInputField/`.
3. Handle rendering goes in `components/HandleRenderComponent/`.
4. Status display goes in `components/NodeStatus/`.
5. Keep node-level state in the parent; pass callbacks to children.

### Splitting Flow Page Components

The flow editor page has multiple distinct regions:

1. **Sidebar** - Component library, search, categories
2. **Canvas** - ReactFlow canvas with nodes and edges
3. **Toolbar** - Build, save, export, share actions
4. **Inspect Panel** - Node details when selected
5. **Playground** - Chat/run interface
6. **Modals** - Export, share, API, settings

Each region should be its own component with clearly defined props.

### Splitting Store-Connected Components

When a component reads from multiple Zustand stores:

1. Keep store selectors in the parent orchestrator.
2. Pass data as props to presentational children.
3. This makes children testable without mocking stores.

```typescript
// Parent: reads from stores
const FlowToolbar = () => {
  const isBuilding = useFlowStore((state) => state.isBuilding)
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  return (
    <ToolbarActions
      isBuilding={isBuilding}
      flowName={currentFlow?.name ?? ""}
      canBuild={isAuthenticated && !isBuilding}
      onBuild={handleBuild}
      onSave={handleSave}
    />
  )
}

// Child: pure presentational
const ToolbarActions: FC<ToolbarActionsProps> = ({
  isBuilding,
  flowName,
  canBuild,
  onBuild,
  onSave,
}) => {
  return (
    <div className="flex items-center gap-2">
      <span>{flowName}</span>
      <Button onClick={onBuild} disabled={!canBuild}>
        {isBuilding ? "Building..." : "Build"}
      </Button>
      <Button onClick={onSave}>Save</Button>
    </div>
  )
}
```
