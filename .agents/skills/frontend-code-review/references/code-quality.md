# Rule Catalog -- Code Quality

Update this file when adding, editing, or removing Code Quality rules so the catalog remains accurate.

## Use `cn()` for conditional class names

IsUrgent: True
Category: Code Quality

### Description

All conditional CSS class logic must use the `cn()` utility from `@/utils` instead of manual string concatenation, template literals, or ternary expressions that build class strings. The `cn()` function wraps `clsx` and `tailwind-merge`, ensuring proper deduplication and conflict resolution of Tailwind classes.

### Suggested Fix

```tsx
// Wrong -- manual concatenation
<div className={`px-4 ${isActive ? "text-primary" : "text-muted-foreground"}`}>

// Wrong -- ternary without cn()
<div className={isActive ? "px-4 text-primary" : "px-4 text-muted-foreground"}>

// Right
import { cn } from "@/utils/utils";

<div className={cn("px-4", isActive ? "text-primary" : "text-muted-foreground")}>
```

## Tailwind-first styling

IsUrgent: True
Category: Code Quality

### Description

Favor Tailwind CSS utility classes for all styling. Do not introduce new CSS modules or custom CSS files unless a Tailwind combination cannot achieve the required styling. Keeping styles in Tailwind improves consistency, reduces bundle size, and simplifies maintenance. The project uses Tailwind v3 with a custom theme configuration.

Why this matters: Introducing custom CSS files creates a parallel styling system that falls out of sync with Tailwind tokens. When the design team changes a border color, they update the CSS variable in `index.css` — but your CSS module keeps the old hardcoded color. Custom CSS also bypasses Tailwind's purging, increasing bundle size. In Langflow, with 300+ components sharing a design system, inconsistent styling compounds fast.

### Suggested Fix

```tsx
// Wrong -- adding a CSS module for simple styling
import styles from "./Button.module.css";
<div className={styles.container}>

// Right -- Tailwind utilities
<div className="flex items-center gap-2 rounded-md border px-4 py-2">
```

## Use design tokens instead of raw Tailwind colors

IsUrgent: True
Category: Code Quality

### Description

**Never use raw Tailwind color classes** like `text-red-500`, `bg-blue-100`, `border-gray-300`, etc. The project defines a complete design token system via CSS custom properties in `src/frontend/src/style/index.css` and maps them to Tailwind classes in `tailwind.config.mjs`. These tokens support both light and dark mode automatically. Using raw colors bypasses the theme system, breaks dark mode, and creates visual inconsistency.

### Available Design Token Classes

**Core semantic colors** (use these for general UI):

| Purpose | Text | Background | Border |
|---------|------|------------|--------|
| Primary text/bg | `text-foreground` | `bg-background` | `border-border` |
| Primary action | `text-primary` | `bg-primary` | — |
| Primary action text | `text-primary-foreground` | — | — |
| Secondary | `text-secondary-foreground` | `bg-secondary` | — |
| Muted/subtle | `text-muted-foreground` | `bg-muted` | — |
| Destructive/danger | `text-destructive` | `bg-destructive` | — |
| Accent | `text-accent-foreground` | `bg-accent` | — |
| Cards | `text-card-foreground` | `bg-card` | — |
| Popovers | `text-popover-foreground` | `bg-popover` | — |
| Tooltips | `text-tooltip-foreground` | `bg-tooltip` | — |
| Input fields | — | — | `border-input` |
| Focus rings | — | — | `ring-ring` |
| Placeholder | `text-placeholder-foreground` | — | — |

**Status colors** (for build state, node status, alerts):

| Status | Class |
|--------|-------|
| Success | `bg-success-background`, `text-success-foreground` |
| Error | `bg-error-background`, `text-error-foreground`, `bg-error` |
| Info | `bg-info-background`, `text-info-foreground` |
| Warning | `bg-warning`, `text-warning-foreground` |
| Status indicators | `bg-status-green`, `bg-status-red`, `bg-status-yellow`, `bg-status-blue`, `bg-status-gray` |

**Accent colors** (for highlights, badges, categories):

| Accent | Background | Foreground |
|--------|------------|------------|
| Emerald | `bg-accent-emerald` | `text-accent-emerald-foreground` |
| Indigo | `bg-accent-indigo` | `text-accent-indigo-foreground` |
| Blue | `bg-accent-blue` | `text-accent-blue-foreground` |
| Pink | `bg-accent-pink` | `text-accent-pink-foreground` |
| Amber | `bg-accent-amber` | `text-accent-amber-foreground` |

**Data type colors** (for flow node field types):

| Type | Background | Foreground |
|------|------------|------------|
| String | `bg-datatype-yellow` | `text-datatype-yellow-foreground` |
| Number | `bg-datatype-blue` | `text-datatype-blue-foreground` |
| Boolean | `bg-datatype-lime` | `text-datatype-lime-foreground` |
| List | `bg-datatype-purple` | `text-datatype-purple-foreground` |
| Dict | `bg-datatype-indigo` | `text-datatype-indigo-foreground` |
| Object | `bg-datatype-gray` | `text-datatype-gray-foreground` |
| Error | `bg-datatype-red` | `text-datatype-red-foreground` |
| Message | `bg-datatype-emerald` | `text-datatype-emerald-foreground` |

**Sticky note colors**:
`bg-note-amber`, `bg-note-neutral`, `bg-note-rose`, `bg-note-blue`, `bg-note-lime`

**Other tokens**:
`bg-canvas` (flow canvas background), `text-node-ring` (node selection ring), `bg-code-background` / `text-code-foreground` (code blocks), `bg-hover` (hover state), `text-hard-zinc`, `bg-smooth-red`, `text-placeholder`

### Suggested Fix

```tsx
// Wrong -- raw Tailwind colors (breaks dark mode, no theme consistency)
<span className="text-red-500">Error</span>
<div className="bg-gray-100 border-gray-300">
<span className="text-blue-600">Link</span>
<div className="bg-green-50 text-green-800">Success</div>

// Right -- design tokens (automatic dark mode, theme-consistent)
<span className="text-destructive">Error</span>
<div className="bg-muted border-border">
<span className="text-accent-blue-foreground">Link</span>
<div className="bg-success-background text-success-foreground">Success</div>

// Wrong -- hardcoded hex or rgb values
<div style={{ color: "#ef4444" }}>
<div className="text-[#2563eb]">

// Right -- use CSS variable if no Tailwind class exists
<div className="text-status-red">
<div className="text-status-blue">
```

### When Raw Colors Are Acceptable

Raw Tailwind colors are only acceptable when:
1. Building a one-off demo or prototype (tag with `// TODO: replace with design token`)
2. The color is truly static and theme-independent (extremely rare)
3. An exact design spec requires a color with no matching token — in that case, **add a new CSS variable** to `src/frontend/src/style/index.css` (both `:root` and `.dark` variants) and register it in `tailwind.config.mjs` instead of using the raw color inline

## Class name ordering for overridable components

IsUrgent: False
Category: Code Quality

### Description

When a component accepts a `className` prop, always place it last inside `cn()` so downstream consumers can override or extend the component's default styling. The component's own classes come first, then the incoming `className`.

### Suggested Fix

```tsx
import { cn } from "@/utils/utils";

const Card = ({ className }: { className?: string }) => {
  return (
    <div className={cn("rounded-lg border bg-background p-4 shadow-sm", className)}>
      {/* content */}
    </div>
  );
};
```

Why: If the component's own classes come after `className`, a consumer passing `className='bg-destructive'` gets silently overridden by the component's `bg-background`. The consumer's intent is lost. By placing `className` last in `cn()`, Tailwind Merge resolves conflicts in favor of the consumer.

## Strong TypeScript typing -- no `any`

IsUrgent: True
Category: Code Quality

### Description

Never use `any` as a type annotation. Using `any` disables TypeScript's ability to catch type mismatches at compile time — bugs that would be caught by the compiler instead crash in production. In Langflow, flow data structures are deeply nested (`NodeDataType.node.template[fieldName].value`); an `any` at any level silently allows accessing non-existent properties, causing 'Cannot read properties of undefined' in the canvas. Use `unknown` with type guards for genuinely unknown data, or specific types/generics for everything else.

### Suggested Fix

```ts
// Wrong
function processData(data: any) { ... }

// Right
function processData(data: Record<string, unknown>) { ... }

// Right -- with type guard
function processData(data: unknown) {
  if (isFlowData(data)) { ... }
}
```

## Biome formatting conventions

IsUrgent: False
Category: Code Quality

### Description

The project uses Biome (not ESLint/Prettier) for linting and formatting. Follow Biome conventions: double quotes for strings, 2-space indentation, trailing commas in multi-line structures. Run `biome check` or `biome format` to verify compliance. Do not add ESLint or Prettier configuration files.

### Suggested Fix

```ts
// Wrong -- single quotes, 4-space indent
const name = 'flow'
const config = {
    key: 'value'
}

// Right -- double quotes, 2-space indent, trailing comma
const name = "flow";
const config = {
  key: "value",
};
```

## Prefer Radix UI primitives for accessible components

IsUrgent: False
Category: Code Quality

### Description

When building interactive UI elements (dialogs, dropdowns, tooltips, popovers, tabs, etc.), use Radix UI primitives via the shadcn-ui wrappers in `components/ui/`. Custom implementations of these patterns consistently miss: keyboard navigation (arrow keys in dropdowns), focus trapping (Tab stays inside dialogs), screen reader announcements (ARIA live regions), and Escape key handling. Rebuilding these from scratch introduces accessibility regressions that affect keyboard-only and screen reader users. Langflow is used by enterprise teams that may require WCAG compliance — every custom dropdown without proper focus management is a compliance risk.

### Suggested Fix

```tsx
// Wrong -- custom dropdown implementation
const [open, setOpen] = useState(false);
<div onBlur={() => setOpen(false)}>
  <button onClick={() => setOpen(!open)}>Menu</button>
  {open && <div className="absolute">{/* items */}</div>}
</div>

// Right -- use shadcn/Radix DropdownMenu
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

<DropdownMenu>
  <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
  <DropdownMenuContent>
    <DropdownMenuItem>Item 1</DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>
```

## State management: Zustand for client, React Query for server

IsUrgent: True
Category: Code Quality

### Description

Use Zustand stores (in `src/frontend/src/stores/`) for client-side UI state and TanStack React Query (via hooks in `src/frontend/src/controllers/API/`) for server state (data fetching, caching, mutations). Do not store fetched server data in Zustand; let React Query manage it. Do not use React Query for purely client-side state.

### Suggested Fix

```ts
// Wrong -- storing fetched data in Zustand
const useFlowStore = create((set) => ({
  flows: [],
  fetchFlows: async () => {
    const data = await api.getFlows();
    set({ flows: data });
  },
}));

// Right -- React Query for server state
const useFlows = () => {
  return useQueryFunctionType<FlowType[]>(["flows"], api.getFlows);
};

// Right -- Zustand for client UI state
const useFlowStore = create((set) => ({
  selectedNodeId: null,
  setSelectedNodeId: (id: string | null) => set({ selectedNodeId: id }),
}));
```

## No `console.log` in production code

IsUrgent: True
Category: Code Quality

### Description

Do not leave `console.log`, `console.warn`, or `console.error` statements in production code. Biome enforces this rule. Use proper error handling, error boundaries, or toast notifications for user-facing errors. If logging is truly needed for debugging, remove it before committing.

Why: `console.log` in production code writes to the browser's developer console. In Langflow, component data often includes API keys stored in global variables — a `console.log(data)` accidentally leaks credentials to anyone who opens DevTools. Biome catches this at lint time; if Biome is not catching it, the linting step was skipped.

## Prefer `const` and immutable patterns

IsUrgent: False
Category: Code Quality

### Description

Use `const` by default. Only use `let` when reassignment is genuinely needed. Never use `var`. Prefer immutable update patterns (spread operator, `map`, `filter`) over mutation when working with arrays and objects, especially in state updates.

### Suggested Fix

```ts
// Wrong
let items = getItems();
items.push(newItem);
setState({ items });

// Right
const items = getItems();
setState({ items: [...items, newItem] });
```

Why: Mutation creates invisible dependencies between code paths. If function A mutates an array that function B reads, changing A's behavior silently breaks B with no compile error. React also relies on reference equality for re-renders — mutating an object in state doesn't trigger a re-render because `oldObj === newObj` is still `true`. Spread/map/filter create new references that React can detect.

## Functional components with hooks only

IsUrgent: True
Category: Code Quality

### Description

All React components must be functional components using hooks. Do not use class components, `React.Component`, or lifecycle methods (`componentDidMount`, etc.). Use `useEffect`, `useState`, `useMemo`, `useCallback`, and custom hooks instead.

Why: Class components have a larger API surface (lifecycle methods, `this` binding, constructor), making them harder to test and reason about. Hooks compose better — a custom hook can combine state, effects, and context without nesting HOCs. The entire Langflow codebase uses functional components; introducing a class component breaks consistency and forces other developers to context-switch between paradigms.

## Early returns for guard clauses

IsUrgent: False
Category: Code Quality

### Description

Use early returns to handle edge cases and guard conditions at the top of functions and components. This reduces nesting, improves readability, and makes the main logic path clear.

Deep nesting increases cognitive load: each additional level of indentation requires the reader to hold one more condition in working memory. Studies show that code with 3+ nesting levels has significantly higher defect rates. Guard clauses at the top make preconditions explicit and keep the main logic at the lowest indentation — the 'happy path' is visually clear.

### Suggested Fix

```tsx
// Wrong -- deeply nested
function NodeComponent({ data }: NodeProps) {
  if (data) {
    if (data.node) {
      if (data.node.template) {
        return <div>{/* main content */}</div>;
      }
    }
  }
  return null;
}

// Right -- early returns
function NodeComponent({ data }: NodeProps) {
  if (!data?.node?.template) return null;

  return <div>{/* main content */}</div>;
}
```

## Use Lucide React for icons

IsUrgent: False
Category: Code Quality

### Description

The project standardizes on Lucide React for icons. Do not import icons from other libraries (heroicons, react-icons, font-awesome, etc.) unless Lucide does not have an equivalent. Check the Lucide icon set first at https://lucide.dev before introducing a new icon dependency.

Why: Multiple icon libraries bloat the bundle (each library ships its own SVG set). Lucide is tree-shakeable — unused icons are removed at build time. Mixing libraries also creates visual inconsistency (different stroke widths, sizing conventions, visual weight). Langflow standardized on Lucide; check https://lucide.dev before adding a new dependency.

### Suggested Fix

```tsx
// Wrong
import { AiOutlineCheck } from "react-icons/ai";

// Right
import { Check } from "lucide-react";
```

## Follow the project's naming and folder conventions

IsUrgent: True
Category: Code Quality

### Description

All **new** frontend code must use **kebab-case** file names with descriptive names. The legacy codebase has mixed conventions (`index.tsx`, camelCase, PascalCase) — do NOT follow those patterns for new code.

**The standard for NEW code:**

- **All files**: kebab-case with a name that describes what the file does. **Never name a file `index.tsx`** — this is a legacy pattern that makes navigation and search harder.
- **Folders**: kebab-case, named after the feature or component.
- **Hooks**: kebab-case with `use-` prefix (`use-add-flow.ts`, `use-debounce.ts`).
- **Stores**: camelCase with "Store" suffix (`flowStore.ts`, `alertStore.ts`) — existing convention, keep it.
- **Types**: kebab-case folders with descriptive file names.

| What | Convention | Example |
|------|-----------|---------|
| Component file | kebab-case, descriptive | `flow-settings-panel.tsx`, `node-input-field.tsx` |
| Component folder | kebab-case | `flow-settings/`, `node-toolbar/` |
| Hook file | kebab-case, `use-` prefix | `use-save-flow.ts`, `use-debounce.ts` |
| Helper file | kebab-case, descriptive | `column-defs.ts`, `format-data.ts` |
| Type file | kebab-case | `flow-types.ts`, `api-types.ts` |
| Store file | camelCase + "Store" | `flowStore.ts` (existing convention) |
| UI component (shadcn) | kebab-case | `dropdown-menu.tsx` (shadcn standard) |

**Never `index.tsx`:**

```
// Wrong (legacy pattern — do NOT use for new code)
my-component/
├── index.tsx          ← ambiguous, hard to find in search/tabs

// Right (new standard)
my-component/
├── my-component.tsx   ← clear, searchable, self-documenting
├── components/
│   ├── sub-part.tsx
│   └── another-part.tsx
├── helpers/
│   ├── column-defs.ts
│   └── format-data.ts
├── hooks/
│   └── use-local-state.ts
└── types/
    └── my-component-types.ts
```

**Key rule: helpers are LOCAL, not centralized.** Each component owns its own `helpers/` folder. Do not create shared helper files in unrelated directories.

### Suggested Fix

```tsx
// Wrong -- index.tsx (legacy pattern)
// src/frontend/src/components/core/myComponent/index.tsx

// Wrong -- centralized helper
// src/frontend/src/helpers/flowHelpers.ts

// Right -- kebab-case, descriptive name, local helpers
// src/frontend/src/components/core/my-component/my-component.tsx
// src/frontend/src/pages/FlowPage/components/flow-sidebar/helpers/format-flow.ts
```

## Use available shadcn components from `components/ui/`

IsUrgent: False
Category: Code Quality

### Description

Before building a custom interactive UI element, check if a shadcn/Radix component already exists in `src/frontend/src/components/ui/`. The project has 39+ base components available:

**Layout & Containers:** `accordion`, `card`, `dialog`, `dialog-with-no-close`, `disclosure`, `popover`, `separator`, `sidebar`, `simple-sidebar`, `tabs`, `tabs-button`

**Forms & Inputs:** `button`, `checkbox`, `input`, `label`, `radio-group`, `select`, `select-custom`, `switch`, `textarea`

**Feedback & Overlay:** `alert`, `badge`, `command`, `context-menu`, `dropdown-menu`, `loading`, `skeleton`, `skeletonGroup`, `tooltip`

**Visual:** `animated-close`, `background-gradient`, `checkmark`, `dot-background`, `refreshButton`, `table`, `text-loop`, `textAnimation`, `TextShimmer`, `xmark`

Do not recreate these patterns manually. Import from `@/components/ui/` instead.
