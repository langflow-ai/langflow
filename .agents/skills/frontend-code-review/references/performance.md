# Rule Catalog -- Performance

Update this file when adding, editing, or removing Performance rules so the catalog remains accurate.

## @xyflow/react data usage

IsUrgent: True
Category: Performance

### Description

When working with the flow graph powered by @xyflow/react v12, use `useNodes()` and `useEdges()` hooks for rendering UI that displays node/edge data. For callbacks that mutate or read node/edge state imperatively (e.g., inside event handlers), use `useReactFlow()` or `useStoreApi()` to access the store directly. Avoid pulling the full node/edge arrays in callbacks, as this creates unnecessary subscriptions and re-renders.

### Suggested Fix

```tsx
// Wrong -- subscribes to all node changes in a callback-only context
function MyPanel() {
  const nodes = useNodes();
  const handleExport = () => {
    const data = nodes.map((n) => n.data);
    exportFlow(data);
  };
  return <button onClick={handleExport}>Export</button>;
}

// Right -- use store API for imperative access
function MyPanel() {
  const { getNodes } = useReactFlow();
  const handleExport = () => {
    const data = getNodes().map((n) => n.data);
    exportFlow(data);
  };
  return <button onClick={handleExport}>Export</button>;
}
```

## Complex prop memoization with `useMemo`

IsUrgent: True
Category: Performance

### Description

Wrap complex prop values (objects, arrays, computed structures) in `useMemo` before passing them to child components. Without memoization, a new reference is created on every render, causing children wrapped in `React.memo` to re-render unnecessarily. This is especially critical in the flow canvas where hundreds of nodes may be rendered simultaneously.

### Suggested Fix

```tsx
// Wrong -- new object on every render
<GenericNode
  config={{
    template: data.node.template,
    display_name: data.node.display_name,
  }}
/>

// Right -- stable reference
const config = useMemo(
  () => ({
    template: data.node.template,
    display_name: data.node.display_name,
  }),
  [data.node.template, data.node.display_name],
);

<GenericNode config={config} />
```

## Avoid re-renders with `React.memo` and `useCallback`

IsUrgent: True
Category: Performance

### Description

Use `React.memo` for components that receive stable props and should not re-render when their parent re-renders. Use `useCallback` for callback functions passed as props to memoized children. This is critical for node components on the canvas: GenericNode and its sub-components should be memoized to avoid cascading re-renders when the flow state changes.

### Suggested Fix

```tsx
// Wrong -- inline callback causes child re-render
function ParentNode({ id }: { id: string }) {
  return (
    <ChildComponent
      onUpdate={(value: string) => updateNodeField(id, value)}
    />
  );
}

// Right -- stable callback reference
function ParentNode({ id }: { id: string }) {
  const handleUpdate = useCallback(
    (value: string) => updateNodeField(id, value),
    [id],
  );
  return <ChildComponent onUpdate={handleUpdate} />;
}

const ChildComponent = React.memo(({ onUpdate }: Props) => {
  // ...
});
```

## Lazy loading for heavy pages

IsUrgent: False
Category: Performance

### Description

Use `React.lazy()` with `<Suspense>` for route-level code splitting of heavy pages (flow editor, settings, store, etc.). This reduces the initial bundle size and improves first-load performance. Route definitions should use lazy imports rather than static imports for page components.

### Suggested Fix

```tsx
// Wrong -- static import of heavy page
import FlowEditor from "@/pages/FlowEditor";

// Right -- lazy loaded
const FlowEditor = React.lazy(() => import("@/pages/FlowEditor"));

<Suspense fallback={<LoadingSpinner />}>
  <FlowEditor />
</Suspense>
```

## No expensive operations in render functions

IsUrgent: True
Category: Performance

### Description

Do not perform expensive computations (deep object traversals, array sorting/filtering of large datasets, JSON parsing, regex on large strings) directly in the render body of a component. Move these into `useMemo` with appropriate dependencies, or into event handlers / effects if they produce side effects. The flow canvas may trigger frequent re-renders; keeping the render path lightweight is critical.

### Suggested Fix

```tsx
// Wrong -- sorts on every render
function NodeList({ nodes }: { nodes: NodeType[] }) {
  const sorted = nodes
    .filter((n) => n.data.showNode)
    .sort((a, b) => a.data.node.display_name.localeCompare(b.data.node.display_name));

  return <>{sorted.map((n) => <NodeCard key={n.id} node={n} />)}</>;
}

// Right -- memoized computation
function NodeList({ nodes }: { nodes: NodeType[] }) {
  const sorted = useMemo(
    () =>
      nodes
        .filter((n) => n.data.showNode)
        .sort((a, b) =>
          a.data.node.display_name.localeCompare(b.data.node.display_name),
        ),
    [nodes],
  );

  return <>{sorted.map((n) => <NodeCard key={n.id} node={n} />)}</>;
}
```

## Zustand selector optimization

IsUrgent: True
Category: Performance

### Description

When reading from Zustand stores, always use selectors to subscribe to only the specific slices of state the component needs. Selecting the entire store object causes the component to re-render on every store update, even for unrelated state changes. Langflow has 15+ Zustand stores; careless subscriptions can create cascading performance problems.

### Suggested Fix

```ts
// Wrong -- subscribes to entire store, re-renders on any change
const store = useFlowStore();
const nodes = store.nodes;

// Wrong -- inline object selector creates new reference each render
const { nodes, edges } = useFlowStore((state) => ({
  nodes: state.nodes,
  edges: state.edges,
}));

// Right -- individual selectors for each value
const nodes = useFlowStore((state) => state.nodes);
const edges = useFlowStore((state) => state.edges);

// Right -- use useShallow for multiple values if needed
import { useShallow } from "zustand/react/shallow";

const { nodes, edges } = useFlowStore(
  useShallow((state) => ({ nodes: state.nodes, edges: state.edges })),
);
```

## React Query: proper staleTime and gcTime configuration

IsUrgent: False
Category: Performance

### Description

Configure `staleTime` and `gcTime` (formerly `cacheTime`) appropriately for each query based on how frequently the data changes. Avoid leaving defaults (0ms staleTime) for data that rarely changes (e.g., component type definitions, user settings), as this causes unnecessary refetches. Conversely, do not set excessively long stale times for data that changes frequently (e.g., flow execution status).

### Suggested Fix

```ts
// Wrong -- default staleTime of 0, refetches on every mount
const { data } = useQuery({
  queryKey: ["componentTypes"],
  queryFn: getComponentTypes,
});

// Right -- component types rarely change, cache for 5 minutes
const { data } = useQuery({
  queryKey: ["componentTypes"],
  queryFn: getComponentTypes,
  staleTime: 5 * 60 * 1000,
});
```

## Avoid creating new objects/arrays inline in JSX

IsUrgent: False
Category: Performance

### Description

Do not create new object or array literals directly inside JSX props, especially for configuration objects, data arrays, or callback payloads. Each render creates a new reference, which defeats `React.memo` and `useMemo` optimizations in child components. Extract these to constants outside the component, or memoize them inside the component.

**Note**: Since this project uses Tailwind CSS, inline `style={}` props should be extremely rare. Use Tailwind classes with design tokens instead (see code-quality.md). This rule applies primarily to non-style object props like `config`, `data`, `options`, `columns`, etc.

### Suggested Fix

```tsx
// Wrong -- new config object every render, child re-renders even if data hasn't changed
function FlowSettings({ flowId }: { flowId: string }) {
  return (
    <SettingsPanel
      config={{ flowId, autoSave: true, showMinimap: false }}
    />
  );
}

// Right -- constant outside component for static values
const DEFAULT_SETTINGS = { autoSave: true, showMinimap: false } as const;

function FlowSettings({ flowId }: { flowId: string }) {
  const config = useMemo(
    () => ({ flowId, ...DEFAULT_SETTINGS }),
    [flowId],
  );
  return <SettingsPanel config={config} />;
}

// Wrong -- new array every render
<SelectComponent options={["option1", "option2", "option3"]} />

// Right -- constant outside component
const OPTIONS = ["option1", "option2", "option3"] as const;
<SelectComponent options={OPTIONS} />
```
