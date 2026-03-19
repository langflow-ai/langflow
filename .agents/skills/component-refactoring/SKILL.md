---
name: component-refactoring
description: Refactor high-complexity React components in Langflow frontend. Use when manual complexity assessment shows complexity > 50 or lineCount > 300, when the user asks for code splitting, hook extraction, or complexity reduction; avoid for simple/well-structured components, third-party wrappers, or when the user explicitly wants testing without refactoring.
---

# Langflow Component Refactoring Skill

Refactor high-complexity React components in the Langflow frontend codebase with the patterns and workflow below.

> **Complexity Threshold**: Components with complexity > 50 (measured manually by counting conditionals, nesting levels, and lines) should be refactored before testing.

## Quick Reference

### Commands (run from `src/frontend/`)

```bash
cd src/frontend

# Lint with Biome
npm run lint

# Type checking
npm run type-check

# Run tests
npm test
```

### Manual Complexity Assessment

Since Langflow does not have automated complexity analysis tools, assess components manually:

1. **Count conditionals**: Each `if/else`, `switch/case`, ternary, `&&`/`||` chain adds +1.
2. **Count nesting levels**: Each level of nesting within conditionals or loops adds +1.
3. **Count total lines**: Target < 300 lines per component file.
4. **Count state hooks**: More than 5 `useState` calls suggests hook extraction.
5. **Count effects**: More than 3 `useEffect` calls suggests effect consolidation.

### Complexity Score Interpretation

| Score | Level | Action |
|-------|-------|--------|
| 0-25 | Simple | Ready for testing |
| 26-50 | Medium | Consider minor refactoring |
| 51-75 | Complex | **Refactor before testing** |
| 76-100 | Very Complex | **Must refactor** |

## Core Refactoring Patterns

### Pattern 1: Extract Custom Hooks

**When**: Component has complex state management, multiple `useState`/`useEffect`, or business logic mixed with UI.

**Langflow Convention**: Place hooks in a `hooks/` subdirectory or alongside the component as `use-<feature>.ts`. Langflow uses kebab-case filenames with `use-` prefix.

```typescript
// Before: Complex state logic in component
const FlowPage: FC = () => {
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [buildStatus, setBuildStatus] = useState<BuildStatus>(BuildStatus.IDLE)

  // 50+ lines of state management logic...

  return <div>...</div>
}

// After: Extract to custom hook
// hooks/use-flow-state.ts
export const useFlowState = (flowId: string) => {
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [buildStatus, setBuildStatus] = useState<BuildStatus>(BuildStatus.IDLE)

  // Related state management logic here

  return { nodes, setNodes, edges, setEdges, buildStatus, setBuildStatus }
}

// Component becomes cleaner
const FlowPage: FC = () => {
  const { nodes, setNodes, edges, setEdges } = useFlowState(flowId)
  return <div>...</div>
}
```

**Langflow Examples**:
- `src/frontend/src/hooks/use-add-component.ts`
- `src/frontend/src/hooks/use-unsaved-changes.ts`
- `src/frontend/src/hooks/use-refresh-model-inputs.ts`

### Pattern 2: Extract Sub-Components

**When**: Single component has multiple UI sections, conditional rendering blocks, or repeated patterns.

**Langflow Convention**: Place sub-components in subdirectories or as separate files in the same directory. UI primitives go in `components/ui/`, domain components in `components/core/`, reusable components in `components/common/`.

```typescript
// Before: Monolithic JSX with multiple sections
const GenericNode = () => {
  return (
    <div>
      {/* 100 lines of header UI */}
      {/* 100 lines of parameter fields */}
      {/* 100 lines of output handles */}
    </div>
  )
}

// After: Split into focused components
// CustomNodes/GenericNode/
//   generic-node.tsx       (orchestration only — kebab-case, descriptive name)
//   components/
//     node-header.tsx
//     node-parameters.tsx
//     node-outputs.tsx

const GenericNode = () => {
  return (
    <div>
      <NodeHeader nodeData={data} />
      <NodeParameters fields={fields} />
      <NodeOutputs outputs={outputs} />
    </div>
  )
}
```

**Langflow Examples**:
- `src/frontend/src/CustomNodes/GenericNode/components/`
- `src/frontend/src/components/core/`
- `src/frontend/src/components/ui/`

### Pattern 3: Simplify Conditional Logic

**When**: Deep nesting (> 3 levels), complex ternaries, or multiple `if/else` chains.

```typescript
// Before: Deeply nested conditionals
const getFieldComponent = (field: InputFieldType) => {
  if (field.type === "str") {
    if (field.multiline) {
      return <TextAreaComponent />
    } else if (field.password) {
      return <PasswordInput />
    } else if (field.options?.length) {
      return <Dropdown options={field.options} />
    } else {
      return <InputComponent />
    }
  } else if (field.type === "int") {
    return <IntComponent />
  } else if (field.type === "float") {
    return <FloatComponent />
  }
  return null
}

// After: Use lookup tables + early returns
const FIELD_COMPONENT_MAP: Record<string, FC<FieldProps>> = {
  int: IntComponent,
  float: FloatComponent,
  bool: ToggleComponent,
  code: CodeAreaComponent,
}

const STR_VARIANT_MAP: Record<string, FC<FieldProps>> = {
  multiline: TextAreaComponent,
  password: PasswordInput,
  options: Dropdown,
}

const getFieldComponent = (field: InputFieldType) => {
  if (field.type !== "str") {
    const Component = FIELD_COMPONENT_MAP[field.type]
    return Component ? <Component {...field} /> : null
  }

  const variant = field.multiline ? "multiline"
    : field.password ? "password"
    : field.options?.length ? "options"
    : "default"

  const Component = STR_VARIANT_MAP[variant] ?? InputComponent
  return <Component {...field} />
}
```

### Pattern 4: Extract API/Data Logic

**When**: Component directly handles API calls, data transformation, or complex async operations.

**Langflow Convention**:
- This skill is for component decomposition, not query/mutation design.
- When refactoring data fetching, use `frontend-query-mutation` for query patterns, `UseRequestProcessor`, cache invalidation, and mutation error handling.
- Do not create thin passthrough `useQuery` wrappers during refactoring; only extract a custom hook when it truly orchestrates multiple queries/mutations or shared derived state.
- API hooks live in `controllers/API/queries/{domain}/`.

**Langflow Examples**:
- `src/frontend/src/controllers/API/queries/flows/use-post-add-flow.ts`
- `src/frontend/src/controllers/API/queries/variables/use-get-global-variables.ts`
- `src/frontend/src/controllers/API/queries/folders/use-get-folders.ts`

### Pattern 5: Extract Modal/Dialog Management

**When**: Component manages multiple modals with complex open/close states.

**Langflow Convention**: Modals should be extracted with their state management.

```typescript
// Before: Multiple modal states in component
const FlowToolbar = () => {
  const [showExportModal, setShowExportModal] = useState(false)
  const [showShareModal, setShowShareModal] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showApiModal, setShowApiModal] = useState(false)
  // 5+ more modal states...
}

// After: Extract to modal management hook
type ModalType = "export" | "share" | "delete" | "api" | null

const useFlowToolbarModals = () => {
  const [activeModal, setActiveModal] = useState<ModalType>(null)

  const openModal = useCallback((type: ModalType) => setActiveModal(type), [])
  const closeModal = useCallback(() => setActiveModal(null), [])

  return {
    activeModal,
    openModal,
    closeModal,
    isOpen: (type: ModalType) => activeModal === type,
  }
}
```

### Pattern 6: Extract Form Logic

**When**: Complex form validation, submission handling, or field transformation.

**Langflow Convention**: Extract form state and validation into hooks.

```typescript
// Extract form validation and submission
const useFlowSettingsForm = (initialValues: FlowSettings) => {
  const [values, setValues] = useState(initialValues)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = useCallback(() => {
    const newErrors: Record<string, string> = {}
    if (!values.name?.trim()) newErrors.name = "Name is required"
    if (values.endpoint_name && !/^[a-z0-9-]+$/.test(values.endpoint_name)) {
      newErrors.endpoint_name = "Must be lowercase alphanumeric with hyphens"
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }, [values])

  const handleChange = useCallback((field: string, value: any) => {
    setValues((prev) => ({ ...prev, [field]: value }))
  }, [])

  return { values, errors, validate, handleChange }
}
```

## Langflow-Specific Refactoring Guidelines

### 1. Zustand Store Selectors

**When**: Component reads many values from a Zustand store, causing unnecessary re-renders.

```typescript
// Before: Selecting too many values
const Component = () => {
  const flowStore = useFlowStore()
  // Component re-renders on ANY store change
}

// After: Use individual selectors
const Component = () => {
  const nodes = useFlowStore((state) => state.nodes)
  const edges = useFlowStore((state) => state.edges)
  // Component only re-renders when nodes or edges change
}
```

**Langflow Reference**: All stores in `src/frontend/src/stores/` follow this selector pattern.

### 2. Custom Node Components

**When**: Refactoring flow node components (`CustomNodes/GenericNode/`).

**Conventions**:
- Keep node logic in custom hooks
- Extract parameter rendering to separate components
- Use the existing `components/` subdirectory for sub-components

```
CustomNodes/GenericNode/
  generic-node.tsx             # Node registration and main render (kebab-case, NOT index.tsx)
  components/
    handle-render.tsx           # Handle rendering
    node-description.tsx        # Node description display
    node-input-field.tsx        # Input field rendering
    node-name.tsx               # Node name display
    node-output-field.tsx       # Output field rendering
    node-status.tsx             # Build status display
```

### 3. Flow Canvas Components

**When**: Refactoring components related to the flow editor canvas.

**Conventions**:
- `@xyflow/react` v12 is the canvas library
- Keep canvas event handlers separate from UI rendering
- Use `useFlowStore` for flow state management
- Use `useFlowsManagerStore` for multi-flow management

### 4. API Query Hook Components

**When**: Refactoring components that consume API data.

**Conventions**:
- Use existing query hooks from `controllers/API/queries/`
- Access `UseRequestProcessor` for new queries/mutations
- Use query key arrays like `["useGetGlobalVariables"]` for cache management
- Cache invalidation belongs in mutation `onSettled` callbacks

## Refactoring Workflow

### Step 1: Assess Complexity

Manually count:
- Total conditionals (if/else, switch, ternary, &&/||)
- Maximum nesting depth
- Total lines of code
- Number of useState/useEffect hooks
- Number of distinct UI sections

### Step 2: Plan

Create a refactoring plan based on detected features:

| Detected Feature | Refactoring Action |
|------------------|-------------------|
| 5+ `useState` hooks with related state | Extract custom hook |
| API calls in component body | Extract to query hook |
| 3+ event handlers with logic | Extract event handlers to hook |
| 300+ lines | Split into sub-components |
| Deep conditional nesting (>3) | Simplify conditional logic |
| Multiple modal states | Extract modal management |

### Step 3: Execute Incrementally

1. **Extract one piece at a time**
2. **Run lint, type-check, and tests after each extraction**
3. **Verify functionality before next step**

```
For each extraction:
  1. Extract code
  2. Run: npm run lint
  3. Run: npm run type-check
  4. Run: npm test
  5. Test functionality manually
  6. PASS? -> Next extraction
     FAIL? -> Fix before continuing
```

### Step 4: Verify

After refactoring, re-assess complexity manually:

- Target complexity < 50
- Target line count < 300
- Target max nesting depth <= 3
- Target max function length < 30 lines

## Common Mistakes to Avoid

### Over-Engineering

```typescript
// Too many tiny hooks
const useButtonText = () => useState("Click")
const useButtonDisabled = () => useState(false)
const useButtonLoading = () => useState(false)

// Cohesive hook with related state
const useButtonState = () => {
  const [text, setText] = useState("Click")
  const [disabled, setDisabled] = useState(false)
  const [loading, setLoading] = useState(false)
  return { text, setText, disabled, setDisabled, loading, setLoading }
}
```

### Breaking Existing Patterns

- Follow existing directory structures in `components/ui/`, `components/core/`, `components/common/`
- Maintain naming conventions (kebab-case files, PascalCase components)
- Preserve export patterns for compatibility
- Keep Zustand store selector patterns consistent

### Premature Abstraction

- Only extract when there is clear complexity benefit
- Do not create abstractions for single-use code
- Keep refactored code in the same domain area

### Bypassing UseRequestProcessor

- Do not call `useQuery` or `useMutation` directly for API calls
- Always use the `UseRequestProcessor` pattern for consistency with retry and invalidation logic
- See `frontend-query-mutation` skill for API hook patterns

## References

### Langflow Codebase Examples

- **Hook extraction**: `src/frontend/src/hooks/`
- **Component splitting**: `src/frontend/src/CustomNodes/GenericNode/components/`
- **UI components**: `src/frontend/src/components/ui/`
- **Core components**: `src/frontend/src/components/core/`
- **Common components**: `src/frontend/src/components/common/`
- **API query hooks**: `src/frontend/src/controllers/API/queries/`
- **Zustand stores**: `src/frontend/src/stores/`

### Related Skills

- `frontend-query-mutation` - For API query and mutation patterns
- `frontend-testing` - For testing refactored components
