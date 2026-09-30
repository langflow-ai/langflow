# Hook Extraction Patterns

This document provides detailed guidance on extracting custom hooks from complex components in Langflow.

## When to Extract Hooks

Extract a custom hook when you identify:

1. **Coupled state groups** - Multiple `useState` hooks that are always used together
1. **Complex effects** - `useEffect` with multiple dependencies or cleanup logic
1. **Business logic** - Data transformations, validations, or calculations
1. **Reusable patterns** - Logic that appears in multiple components

## Extraction Process

### Step 1: Identify State Groups

Look for state variables that are logically related:

```typescript
// These belong together - extract to hook
const [nodes, setNodes] = useState<Node[]>([])
const [edges, setEdges] = useState<Edge[]>([])
const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, zoom: 1 })

// These are canvas-related state that should be in useCanvasState()
```

### Step 2: Identify Related Effects

Find effects that modify the grouped state:

```typescript
// These effects belong with the state above
useEffect(() => {
  if (flowData?.nodes) {
    setNodes(flowData.nodes)
    setEdges(flowData.edges ?? [])
  }
}, [flowData])

useEffect(() => {
  if (fitViewOnLoad && nodes.length > 0) {
    reactFlowInstance?.fitView()
  }
}, [nodes.length, fitViewOnLoad, reactFlowInstance])
```

### Step 3: Create the Hook

```typescript
// hooks/use-canvas-state.ts
import type { Edge, Node, Viewport } from "@xyflow/react"
import { useEffect, useState } from "react"
import type { FlowType } from "@/types/flow"

interface UseCanvasStateParams {
  flowData: FlowType | undefined
  fitViewOnLoad?: boolean
  reactFlowInstance?: any
}

interface UseCanvasStateReturn {
  nodes: Node[]
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>
  edges: Edge[]
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>
  viewport: Viewport
  setViewport: React.Dispatch<React.SetStateAction<Viewport>>
}

export const useCanvasState = ({
  flowData,
  fitViewOnLoad = false,
  reactFlowInstance,
}: UseCanvasStateParams): UseCanvasStateReturn => {
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, zoom: 1 })

  // Sync flow data to canvas state
  useEffect(() => {
    if (flowData?.nodes) {
      setNodes(flowData.nodes)
      setEdges(flowData.edges ?? [])
    }
  }, [flowData])

  // Fit view on initial load
  useEffect(() => {
    if (fitViewOnLoad && nodes.length > 0) {
      reactFlowInstance?.fitView()
    }
  }, [nodes.length, fitViewOnLoad, reactFlowInstance])

  return {
    nodes,
    setNodes,
    edges,
    setEdges,
    viewport,
    setViewport,
  }
}
```

### Step 4: Update Component

```typescript
// Before: 50+ lines of state management
const FlowPage: FC = () => {
  const [nodes, setNodes] = useState<Node[]>([])
  // ... lots of related state and effects
}

// After: Clean component
const FlowPage: FC = () => {
  const {
    nodes,
    setNodes,
    edges,
    setEdges,
    viewport,
  } = useCanvasState({
    flowData,
    fitViewOnLoad: true,
    reactFlowInstance,
  })

  // Component now focuses on UI
}
```

## Naming Conventions

### Hook Names

- Use `use` prefix: `useFlowState`, `useNodeDrag`, `useBuildStatus`
- Be specific: `useRefreshModelInputs` not `useRefresh`
- Include domain: `useFlowStore`, `useGlobalVariables`, `useAddComponent`
- Match existing Langflow patterns: `useFlowsManagerStore`, `useFlowStore`

### File Names

- Kebab-case: `use-flow-state.ts`, `use-node-drag.ts`
- Place in `hooks/` directory for globally reusable hooks: `src/frontend/src/hooks/use-debounce.ts`
- Place alongside component for single-use hooks
- Place in component's `hooks/` subdirectory when multiple hooks exist for one feature

### Return Type Names

- Suffix with `Return`: `UseCanvasStateReturn`
- Suffix params with `Params`: `UseCanvasStateParams`

## Common Hook Patterns in Langflow

### 1. Zustand Store Derived State Hook

When you need to compute derived state from a Zustand store, extract a hook rather than computing in the component.

```typescript
// Pattern: Derived state from store
export const useFlowValidation = () => {
  const nodes = useFlowStore((state) => state.nodes)
  const edges = useFlowStore((state) => state.edges)

  const hasErrors = useMemo(
    () => nodes.some((n) => n.data?.node?.error),
    [nodes],
  )

  const hasDisconnectedInputs = useMemo(
    () =>
      nodes.some((n) => {
        const requiredInputs = Object.values(n.data?.node?.template ?? {}).filter(
          (field) => field.required && field.show,
        )
        return requiredInputs.some(
          (input) =>
            !edges.some(
              (e) => e.target === n.id && e.targetHandle === input.name,
            ),
        )
      }),
    [nodes, edges],
  )

  return {
    hasErrors,
    hasDisconnectedInputs,
    isValid: !hasErrors && !hasDisconnectedInputs,
  }
}
```

### 2. API Data Hooks

When hook extraction touches query or mutation code, do not use this reference as the source of truth for data-layer patterns.

- Use `frontend-query-mutation` for `UseRequestProcessor`, query patterns, cache invalidation, and mutation error handling.
- Do not create thin passthrough `useQuery` hooks; only extract orchestration hooks that combine multiple queries or shared derived state.
- API hooks live in `controllers/API/queries/{domain}/` and follow the `UseRequestProcessor` pattern.

Example of an orchestration hook (acceptable to extract):

```typescript
// hooks/use-flow-with-variables.ts
// This combines multiple API queries with derived state - worth extracting
export const useFlowWithVariables = (flowId: string) => {
  const { data: flow } = useGetFlow({ id: flowId })
  const { data: globalVariables } = useGetGlobalVariables()

  const resolvedVariables = useMemo(() => {
    if (!flow || !globalVariables) return {}
    return resolveFlowVariables(flow, globalVariables)
  }, [flow, globalVariables])

  return {
    flow,
    globalVariables,
    resolvedVariables,
    isLoading: !flow || !globalVariables,
  }
}
```

### 3. Form State Hook

```typescript
// Pattern: Form state + validation + submission
export const useFlowSettingsForm = (initialValues: FlowSettings) => {
  const [values, setValues] = useState(initialValues)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  const validate = useCallback(() => {
    const newErrors: Record<string, string> = {}
    if (!values.name?.trim()) newErrors.name = "Name is required"
    if (values.endpoint_name && !/^[a-z0-9_-]+$/.test(values.endpoint_name)) {
      newErrors.endpoint_name = "Must be lowercase alphanumeric with hyphens or underscores"
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }, [values])

  const handleChange = useCallback((field: string, value: any) => {
    setValues((prev) => ({ ...prev, [field]: value }))
    // Clear error on field change
    setErrors((prev) => {
      const next = { ...prev }
      delete next[field]
      return next
    })
  }, [])

  const handleSubmit = useCallback(
    async (onSubmit: (values: FlowSettings) => Promise<void>) => {
      if (!validate()) return
      setIsSubmitting(true)
      try {
        await onSubmit(values)
      } finally {
        setIsSubmitting(false)
      }
    },
    [values, validate],
  )

  return { values, errors, isSubmitting, handleChange, handleSubmit }
}
```

### 4. Modal State Hook

```typescript
// Pattern: Multiple modal management
type ModalType = "edit" | "delete" | "duplicate" | "export" | null

export const useModalState = <T = any>() => {
  const [activeModal, setActiveModal] = useState<ModalType>(null)
  const [modalData, setModalData] = useState<T | null>(null)

  const openModal = useCallback((type: ModalType, data?: T) => {
    setActiveModal(type)
    setModalData(data ?? null)
  }, [])

  const closeModal = useCallback(() => {
    setActiveModal(null)
    setModalData(null)
  }, [])

  return {
    activeModal,
    modalData,
    openModal,
    closeModal,
    isOpen: useCallback(
      (type: ModalType) => activeModal === type,
      [activeModal],
    ),
  }
}
```

### 5. Toggle/Boolean Hook

```typescript
// Pattern: Boolean state with convenience methods
export const useToggle = (initialValue = false) => {
  const [value, setValue] = useState(initialValue)

  const toggle = useCallback(() => setValue((v) => !v), [])
  const setTrue = useCallback(() => setValue(true), [])
  const setFalse = useCallback(() => setValue(false), [])

  return [value, { toggle, setTrue, setFalse, set: setValue }] as const
}

// Usage
const [isExpanded, { toggle, setTrue: expand, setFalse: collapse }] = useToggle()
```

### 6. Keyboard Shortcut Hook

Langflow has keyboard shortcut support. Extract shortcut handling to hooks.

```typescript
// Pattern: Keyboard shortcut registration
export const useFlowShortcuts = (handlers: {
  onSave?: () => void
  onUndo?: () => void
  onRedo?: () => void
  onDelete?: () => void
}) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isModKey = event.metaKey || event.ctrlKey

      if (isModKey && event.key === "s") {
        event.preventDefault()
        handlers.onSave?.()
      } else if (isModKey && event.key === "z" && !event.shiftKey) {
        event.preventDefault()
        handlers.onUndo?.()
      } else if (isModKey && event.key === "z" && event.shiftKey) {
        event.preventDefault()
        handlers.onRedo?.()
      } else if (event.key === "Delete" || event.key === "Backspace") {
        handlers.onDelete?.()
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [handlers])
}
```

## Testing Extracted Hooks

After extraction, test hooks in isolation using `@testing-library/react`:

```typescript
// use-canvas-state.test.ts
import { act, renderHook } from "@testing-library/react"
import { useCanvasState } from "./use-canvas-state"

describe("useCanvasState", () => {
  it("should initialize with empty state", () => {
    const { result } = renderHook(() =>
      useCanvasState({
        flowData: undefined,
        fitViewOnLoad: false,
      }),
    )

    expect(result.current.nodes).toEqual([])
    expect(result.current.edges).toEqual([])
    expect(result.current.viewport).toEqual({ x: 0, y: 0, zoom: 1 })
  })

  it("should sync flow data to canvas state", () => {
    const flowData = {
      nodes: [{ id: "node-1", type: "genericNode", position: { x: 0, y: 0 }, data: {} }],
      edges: [{ id: "edge-1", source: "node-1", target: "node-2" }],
    }

    const { result } = renderHook(() =>
      useCanvasState({
        flowData: flowData as any,
        fitViewOnLoad: false,
      }),
    )

    expect(result.current.nodes).toEqual(flowData.nodes)
    expect(result.current.edges).toEqual(flowData.edges)
  })

  it("should update nodes via setNodes", () => {
    const { result } = renderHook(() =>
      useCanvasState({
        flowData: undefined,
        fitViewOnLoad: false,
      }),
    )

    act(() => {
      result.current.setNodes([
        { id: "new-node", type: "genericNode", position: { x: 100, y: 200 }, data: {} } as any,
      ])
    })

    expect(result.current.nodes).toHaveLength(1)
    expect(result.current.nodes[0].id).toBe("new-node")
  })
})
```

## Anti-Patterns to Avoid

### Do Not Wrap Store Selectors

```typescript
// Do not create hooks that just forward store selectors
const useNodes = () => useFlowStore((state) => state.nodes)
const useEdges = () => useFlowStore((state) => state.edges)

// Instead, use selectors directly in the component
const Component = () => {
  const nodes = useFlowStore((state) => state.nodes)
  const edges = useFlowStore((state) => state.edges)
}
```

### Do Not Wrap Single API Calls

```typescript
// Do not create thin wrappers around UseRequestProcessor queries
const useGetFlow = (flowId: string) => {
  const { query } = UseRequestProcessor()
  return query(["useGetFlow", flowId], () => api.get(`${getURL("FLOWS")}/${flowId}`))
}

// These already exist in controllers/API/queries/ - use them directly
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow"
```

### Do Extract Orchestration Hooks

```typescript
// Orchestrating multiple queries and derived state is a valid hook extraction
const useFlowBuildState = (flowId: string) => {
  const { data: flow } = useGetFlow({ id: flowId })
  const { data: builds } = useGetBuilds({ flowId })
  const isBuilding = useFlowStore((state) => state.isBuilding)

  const lastBuild = useMemo(
    () => builds?.sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0],
    [builds],
  )

  const buildProgress = useMemo(() => {
    if (!isBuilding) return null
    // ... compute progress from build state
  }, [isBuilding, builds])

  return { flow, lastBuild, isBuilding, buildProgress }
}
```
