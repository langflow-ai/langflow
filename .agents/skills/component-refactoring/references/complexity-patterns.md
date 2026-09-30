# Complexity Reduction Patterns

This document provides patterns for reducing cognitive complexity in Langflow React components.

## Understanding Complexity

### SonarJS Cognitive Complexity

Langflow does not have automated complexity analysis tools. Assess complexity manually using SonarJS cognitive complexity rules:

- **Total Complexity**: Sum of all functions' complexity in the file
- **Max Complexity**: Highest single function complexity

### What Increases Complexity

| Pattern | Complexity Impact |
|---------|-------------------|
| `if/else` | +1 per branch |
| Nested conditions | +1 per nesting level |
| `switch/case` | +1 per case |
| `for/while/do` | +1 per loop |
| `&&`/`||` chains | +1 per operator |
| Nested callbacks | +1 per nesting level |
| `try/catch` | +1 per catch |
| Ternary expressions | +1 per nesting |

## Pattern 1: Replace Conditionals with Lookup Tables

**Before** (complexity: ~15):

```typescript
const getParameterComponent = (field: InputFieldType) => {
  if (field.type === "str") {
    if (field.multiline) {
      return <TextAreaComponent value={field.value} />
    } else if (field.password) {
      return <PasswordInput value={field.value} />
    } else if (field.options?.length) {
      return <Dropdown options={field.options} value={field.value} />
    } else {
      return <InputComponent value={field.value} />
    }
  }
  if (field.type === "int") {
    return <IntComponent value={field.value} />
  }
  if (field.type === "float") {
    return <FloatComponent value={field.value} />
  }
  if (field.type === "bool") {
    return <ToggleComponent value={field.value} />
  }
  if (field.type === "code") {
    return <CodeAreaComponent value={field.value} />
  }
  return null
}
```

**After** (complexity: ~3):

```typescript
// Define lookup table outside component
const FIELD_TYPE_MAP: Record<string, FC<FieldProps>> = {
  int: IntComponent,
  float: FloatComponent,
  bool: ToggleComponent,
  code: CodeAreaComponent,
  dict: DictComponent,
  file: FileComponent,
}

const getStrVariant = (field: InputFieldType): FC<FieldProps> => {
  if (field.multiline) return TextAreaComponent
  if (field.password) return PasswordInput
  if (field.options?.length) return Dropdown
  return InputComponent
}

// Clean component logic
const getParameterComponent = (field: InputFieldType) => {
  const Component = field.type === "str"
    ? getStrVariant(field)
    : FIELD_TYPE_MAP[field.type]

  if (!Component) return null
  return <Component value={field.value} />
}
```

## Pattern 2: Use Early Returns

**Before** (complexity: ~10):

```typescript
const handleNodeBuild = () => {
  if (isAuthenticated) {
    if (hasValidFlow) {
      if (!isBuilding) {
        if (allInputsConnected) {
          startBuild()
        } else {
          showMissingInputsError()
        }
      } else {
        showBuildInProgressWarning()
      }
    } else {
      showInvalidFlowError()
    }
  } else {
    showAuthError()
  }
}
```

**After** (complexity: ~4):

```typescript
const handleNodeBuild = () => {
  if (!isAuthenticated) {
    showAuthError()
    return
  }

  if (!hasValidFlow) {
    showInvalidFlowError()
    return
  }

  if (isBuilding) {
    showBuildInProgressWarning()
    return
  }

  if (!allInputsConnected) {
    showMissingInputsError()
    return
  }

  startBuild()
}
```

## Pattern 3: Extract Complex Conditions

**Before** (complexity: high):

```typescript
const canRunFlow = (() => {
  if (flow.is_component) {
    return false
  }
  if (!nodes.length) {
    return false
  }
  if (isBuilding) {
    return false
  }
  if (nodes.some((n) => n.data?.node?.error)) {
    return false
  }
  if (
    edges.some(
      (e) =>
        !e.sourceHandle ||
        !e.targetHandle ||
        (e.data?.isInvalid && e.data.isInvalid === true),
    )
  ) {
    return false
  }
  return true
})()
```

**After** (complexity: lower):

```typescript
// Extract to named functions
const hasValidNodes = (nodes: Node[]) => {
  return nodes.length > 0 && !nodes.some((n) => n.data?.node?.error)
}

const hasValidEdges = (edges: Edge[]) => {
  return !edges.some(
    (e) => !e.sourceHandle || !e.targetHandle || e.data?.isInvalid,
  )
}

// Clean main logic
const canRunFlow =
  !flow.is_component &&
  !isBuilding &&
  hasValidNodes(nodes) &&
  hasValidEdges(edges)
```

## Pattern 4: Replace Chained Ternaries

**Before** (complexity: ~5):

```typescript
const buildStatusIcon = buildStatus === BuildStatus.BUILT
  ? <CheckCircle className="text-green-500" />
  : buildStatus === BuildStatus.BUILDING
    ? <Loader className="animate-spin text-blue-500" />
    : buildStatus === BuildStatus.ERROR
      ? <XCircle className="text-red-500" />
      : <Circle className="text-gray-400" />
```

**After** (complexity: ~2):

```typescript
const BUILD_STATUS_ICONS: Record<BuildStatus, ReactNode> = {
  [BuildStatus.BUILT]: <CheckCircle className="text-green-500" />,
  [BuildStatus.BUILDING]: <Loader className="animate-spin text-blue-500" />,
  [BuildStatus.ERROR]: <XCircle className="text-red-500" />,
  [BuildStatus.IDLE]: <Circle className="text-gray-400" />,
}

const buildStatusIcon = BUILD_STATUS_ICONS[buildStatus] ?? BUILD_STATUS_ICONS[BuildStatus.IDLE]
```

## Pattern 5: Flatten Nested Loops

**Before** (complexity: high):

```typescript
const getConnectedNodes = (flow: FlowType) => {
  const results: ConnectedNode[] = []

  for (const node of flow.data.nodes) {
    if (node.data?.node?.template) {
      for (const [fieldName, field] of Object.entries(node.data.node.template)) {
        if (field.type === "str" && field.load_from_db) {
          for (const variable of globalVariables) {
            if (variable.name === field.value) {
              results.push({
                nodeId: node.id,
                fieldName,
                variableName: variable.name,
              })
            }
          }
        }
      }
    }
  }

  return results
}
```

**After** (complexity: lower):

```typescript
// Use functional approach
const getConnectedNodes = (flow: FlowType) => {
  return flow.data.nodes
    .filter((node) => node.data?.node?.template)
    .flatMap((node) =>
      Object.entries(node.data.node.template)
        .filter(([, field]) => field.type === "str" && field.load_from_db)
        .flatMap(([fieldName, field]) =>
          globalVariables
            .filter((variable) => variable.name === field.value)
            .map((variable) => ({
              nodeId: node.id,
              fieldName,
              variableName: variable.name,
            })),
        ),
    )
}
```

## Pattern 6: Extract Event Handler Logic

**Before** (complexity: high in component):

```typescript
const FlowCanvas = () => {
  const handleNodeDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault()
      const nodeData = JSON.parse(event.dataTransfer.getData("application/json"))

      if (!nodeData || !nodeData.type) return

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      // Validate the node type exists
      const nodeType = types[nodeData.type]
      if (!nodeType) {
        setErrorData({ title: "Invalid node type" })
        return
      }

      // Check for duplicates if component
      if (nodeData.node?.is_component) {
        const existingComponent = nodes.find(
          (n) => n.data.node?.display_name === nodeData.node.display_name,
        )
        if (existingComponent) {
          // 20 more lines of duplicate handling...
        }
      }

      // Create the new node
      const newNode = buildNodeFromData(nodeData, position)
      setNodes((prev) => [...prev, newNode])

      // 20 more lines of post-drop logic...
    },
    [nodes, types, screenToFlowPosition],
  )

  return <div>...</div>
}
```

**After** (complexity: lower):

```typescript
// Extract to hook
const useNodeDrop = (nodes: Node[], types: Record<string, any>) => {
  const validateNodeData = useCallback(
    (nodeData: any): boolean => {
      if (!nodeData?.type) return false
      if (!types[nodeData.type]) return false
      return true
    },
    [types],
  )

  const checkDuplicateComponent = useCallback(
    (nodeData: any): Node | undefined => {
      if (!nodeData.node?.is_component) return undefined
      return nodes.find(
        (n) => n.data.node?.display_name === nodeData.node.display_name,
      )
    },
    [nodes],
  )

  return { validateNodeData, checkDuplicateComponent }
}

// Component becomes cleaner
const FlowCanvas = () => {
  const { validateNodeData, checkDuplicateComponent } = useNodeDrop(nodes, types)

  const handleNodeDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault()
      const nodeData = JSON.parse(event.dataTransfer.getData("application/json"))

      if (!validateNodeData(nodeData)) {
        setErrorData({ title: "Invalid node type" })
        return
      }

      const duplicate = checkDuplicateComponent(nodeData)
      if (duplicate) {
        handleDuplicate(duplicate, nodeData)
        return
      }

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })
      const newNode = buildNodeFromData(nodeData, position)
      setNodes((prev) => [...prev, newNode])
    },
    [validateNodeData, checkDuplicateComponent, screenToFlowPosition],
  )

  return <div>...</div>
}
```

## Pattern 7: Reduce Boolean Logic Complexity

**Before** (complexity: ~8):

```typescript
const isNodeDisabled = !isAuthenticated
  || flow.is_component
  || isBuilding
  || node.data?.node?.frozen
  || (node.data?.node?.error && node.data.node.error !== "")
  || (!hasConnectedInputs && node.type !== "genericNode")
  || (isLocked && !isSuperUser)
```

**After** (complexity: ~3):

```typescript
// Extract meaningful boolean functions
const hasNodeError = (node: Node) => {
  return !!node.data?.node?.error && node.data.node.error !== ""
}

const isNodeAccessible = (node: Node, isLocked: boolean, isSuperUser: boolean) => {
  if (isLocked && !isSuperUser) return false
  if (node.data?.node?.frozen) return false
  return true
}

const canInteractWithNode = (node: Node) => {
  if (!isAuthenticated) return false
  if (flow.is_component) return false
  if (isBuilding) return false
  if (hasNodeError(node)) return false
  if (!isNodeAccessible(node, isLocked, isSuperUser)) return false
  if (!hasConnectedInputs && node.type !== "genericNode") return false
  return true
}

const isNodeDisabled = !canInteractWithNode(node)
```

## Pattern 8: Simplify useMemo/useCallback Dependencies

**Before** (complexity: multiple recalculations):

```typescript
const processedNodes = useMemo(() => {
  let result = nodes

  if (searchTerm) {
    result = result.filter(
      (n) =>
        n.data?.node?.display_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        n.data?.type?.toLowerCase().includes(searchTerm.toLowerCase()),
    )
  }

  if (filterByType) {
    result = result.filter((n) => n.data?.type === filterByType)
  }

  if (sortOrder === "name") {
    result = [...result].sort((a, b) =>
      (a.data?.node?.display_name ?? "").localeCompare(b.data?.node?.display_name ?? ""),
    )
  } else if (sortOrder === "type") {
    result = [...result].sort((a, b) =>
      (a.data?.type ?? "").localeCompare(b.data?.type ?? ""),
    )
  }

  return result
}, [nodes, searchTerm, filterByType, sortOrder])
```

**After** (complexity: separated concerns):

```typescript
// Separate filter and sort utilities
const filterNodes = (nodes: Node[], searchTerm: string, filterByType?: string) => {
  let result = nodes

  if (searchTerm) {
    const term = searchTerm.toLowerCase()
    result = result.filter(
      (n) =>
        n.data?.node?.display_name?.toLowerCase().includes(term) ||
        n.data?.type?.toLowerCase().includes(term),
    )
  }

  if (filterByType) {
    result = result.filter((n) => n.data?.type === filterByType)
  }

  return result
}

const SORT_COMPARATORS: Record<string, (a: Node, b: Node) => number> = {
  name: (a, b) =>
    (a.data?.node?.display_name ?? "").localeCompare(b.data?.node?.display_name ?? ""),
  type: (a, b) =>
    (a.data?.type ?? "").localeCompare(b.data?.type ?? ""),
}

const sortNodes = (nodes: Node[], sortOrder: string) => {
  const comparator = SORT_COMPARATORS[sortOrder]
  if (!comparator) return nodes
  return [...nodes].sort(comparator)
}

// Clean component usage
const filteredNodes = useMemo(
  () => filterNodes(nodes, searchTerm, filterByType),
  [nodes, searchTerm, filterByType],
)

const processedNodes = useMemo(
  () => sortNodes(filteredNodes, sortOrder),
  [filteredNodes, sortOrder],
)
```

## Target Metrics After Refactoring

| Metric | Target |
|--------|--------|
| Total Complexity | < 50 |
| Max Function Complexity | < 30 |
| Function Length | < 30 lines |
| Nesting Depth | <= 3 levels |
| Conditional Chains | <= 3 conditions |
