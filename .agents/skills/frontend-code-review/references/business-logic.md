# Rule Catalog -- Business Logic

Update this file when adding, editing, or removing Business Logic rules so the catalog remains accurate.

## Custom node components must not import stores directly outside the provider tree

IsUrgent: True
Category: Business Logic

### Description

File path pattern of node components: `src/frontend/src/CustomNodes/GenericNode/` and sub-components.

GenericNode and its child components render inside the @xyflow/react canvas, which has its own React context. These components may also render in contexts where certain store providers are not available (e.g., preview panels, template views). Directly importing and calling Zustand store hooks that depend on a specific provider context can cause blank screens or runtime errors when the component mounts outside that provider.

### Suggested Fix

Use the store hooks that are available globally (like `useFlowStore`, `useTypesStore`) or pass data as props from the parent that has provider access. If imperative store access is needed, use the store's `getState()` method which does not require a provider.

```tsx
// Wrong -- may fail outside provider tree
import { useSpecialContext } from "@/contexts/specialContext";

function NodeField() {
  const { config } = useSpecialContext(); // crashes if provider missing
  return <div>{config.label}</div>;
}

// Right -- use props or global store
function NodeField({ config }: { config: FieldConfig }) {
  return <div>{config.label}</div>;
}
```

## Flow state management: use `flowStore` for current flow state

IsUrgent: True
Category: Business Logic

### Description

The current flow's state (nodes, edges, flow metadata) is managed through `useFlowStore` (located in `src/frontend/src/stores/flowStore.ts`). Always use this store for reading and modifying the active flow. Do not create parallel state tracking for flow data, and do not cache flow state in component-local state unless there is a specific performance reason (document it if so).

### Suggested Fix

```tsx
// Wrong -- local state duplicating flow data
const [nodes, setNodes] = useState(initialNodes);

// Right -- use the flow store
const nodes = useFlowStore((state) => state.nodes);
const setNodes = useFlowStore((state) => state.setNodes);
```

## API interceptor patterns: do not duplicate auth/retry logic

IsUrgent: True
Category: Business Logic

### Description

The Axios HTTP client in `src/frontend/src/controllers/API/` is configured with interceptors that handle authentication headers, token refresh, retry logic, and error normalization. Do not duplicate any of this logic in individual API call sites or components. Use the configured Axios instance (via the API controller helpers) for all backend requests. Do not create new Axios instances or use raw `fetch()` for API calls to the Langflow backend.

### Suggested Fix

```tsx
// Wrong -- raw fetch with manual auth
const response = await fetch("/api/v1/flows", {
  headers: { Authorization: `Bearer ${token}` },
});

// Wrong -- new Axios instance bypassing interceptors
const client = axios.create({ baseURL: "/api/v1" });
const response = await client.get("/flows");

// Right -- use the project's API utilities
import { api } from "@/controllers/API/api";

const response = await api.get("/flows");
```

## Component data-testid patterns

IsUrgent: False
Category: Business Logic

### Description

Interactive components must include `data-testid` attributes following the project's established naming conventions. This is critical for E2E test stability. The primary patterns are:

- Input fields: `popover-anchor-input-{name}` (generated via `StrRenderComponent` -> `InputComponent` -> `CustomInputPopover`)
- Buttons: descriptive kebab-case, e.g., `edit-fields-button`, `playground-btn-flow-io`
- Sidebar items: `sidebar-nav-{item}`, `sidebar-add-sticky-note-button`
- Node-related: `title-{display_name}`, `handle-{id}`

When adding new interactive elements, follow the existing patterns. When modifying elements that have `data-testid`, preserve the attribute and its value to avoid breaking E2E tests.

### Suggested Fix

```tsx
// Wrong -- missing data-testid on interactive element
<button onClick={handleSave}>Save</button>

// Right -- includes data-testid
<button data-testid="save-flow-button" onClick={handleSave}>Save</button>
```

## Global variables: understand `load_from_db` and `value` pattern

IsUrgent: True
Category: Business Logic

### Description

Template fields in starter projects use the `load_from_db` + `value` pattern to reference global variables. When `load_from_db: true` and `value` is set to a key like `"OPENAI_API_KEY"`, the field displays a badge (via `InputGlobalComponent`) instead of a text input. The actual input element (`<input>`) does not exist in the DOM when a global variable is selected.

This has implications for:
- **Component rendering**: Do not assume an input element exists when `load_from_db` is true and a global variable is set.
- **E2E tests**: `getByTestId("popover-anchor-input-api_key")` will not find an element when a global variable badge is displayed.
- **Templates affected**: Market Research, Price Deal Finder, Research Agent have `load_from_db: true` with global variable values.

### Suggested Fix

When writing components that interact with template fields, check the `load_from_db` state:

```tsx
// Wrong -- assumes input always exists
const apiKeyInput = data.node.template.api_key;
// Directly rendering an <input> without checking load_from_db

// Right -- handle both states
if (field.load_from_db && field.value) {
  // Render global variable badge
  return <GlobalVariableBadge name={field.value} />;
}
// Render normal input
return <InputComponent value={field.value} onChange={handleChange} />;
```

## Inspection panel: use `enableInspectPanel` before accessing panel elements

IsUrgent: True
Category: Business Logic

### Description

The inspection panel (added in the panel migration from the old edit modal pattern) must be explicitly enabled before its elements are accessible. In E2E tests and in code that interacts with the panel programmatically:

1. Call `enableInspectPanel(page)` before attempting to access `edit-fields-button` or other panel controls.
2. Click a node to select it, then use `edit-fields-button` to toggle field editing.
3. The old `openAdvancedOptions(page)` / `closeAdvancedOptions(page)` pattern is deprecated.
4. The `editNode` flag is always `false`; `-edit` suffix testids no longer exist.

This rule is especially important when writing or modifying E2E tests that interact with node configuration.

## Node field visibility rules

IsUrgent: False
Category: Business Logic

### Description

Node fields have different visibility rules depending on where they are rendered. Understanding these rules is critical when modifying field display logic:

- **Canvas view**: Shows non-advanced, non-hidden fields. Controlled by `isCanvasVisible()` in `src/frontend/src/CustomNodes/helpers/parameter-filtering.ts`.
- **Inspection panel**: Shows only advanced fields. Controlled by `shouldRenderInspectionPanelField()` in the same file.
- **`showNode` flag**: Defaults to `true`. When set to `false`, fields receive the `hidden` CSS class rather than being removed from the DOM.

When adding new fields or modifying visibility logic, ensure both canvas and inspection panel rendering paths are considered.

### Suggested Fix

```tsx
// Wrong -- only checking one visibility context
if (!field.advanced) {
  return <FieldComponent />;
}

// Right -- check the appropriate visibility function for the context
import { isCanvasVisible, shouldRenderInspectionPanelField } from "@/CustomNodes/helpers/parameter-filtering";

// In canvas context
if (isCanvasVisible(field)) {
  return <FieldComponent />;
}

// In inspection panel context
if (shouldRenderInspectionPanelField(field)) {
  return <FieldComponent />;
}
```

## Customization layer usage

IsUrgent: False
Category: Business Logic

### Description

Langflow has a customization layer in `src/frontend/src/customization/` that allows overriding default behaviors and components. When adding new features that may need to be customized (e.g., branding, feature flags, custom components), use the customization layer rather than hardcoding values. Check `src/frontend/src/customization/` for existing customization points before adding new ones.

## React Hook Form + Zod for form validation

IsUrgent: False
Category: Business Logic

### Description

Forms that require validation should use React Hook Form with Zod schemas. Do not implement manual form state tracking or validation logic when React Hook Form can handle it. Define Zod schemas for form data types and use `zodResolver` to integrate them with React Hook Form.

### Suggested Fix

```tsx
// Wrong -- manual form state and validation
const [name, setName] = useState("");
const [error, setError] = useState("");

const handleSubmit = () => {
  if (!name) {
    setError("Name is required");
    return;
  }
  // submit
};

// Right -- React Hook Form + Zod
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const schema = z.object({
  name: z.string().min(1, "Name is required"),
});

type FormData = z.infer<typeof schema>;

function MyForm() {
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = (data: FormData) => {
    // submit
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register("name")} />
      {errors.name && <span>{errors.name.message}</span>}
    </form>
  );
}
```
