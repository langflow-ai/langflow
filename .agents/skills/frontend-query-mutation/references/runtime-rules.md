# Runtime Rules

## Table of Contents

- Conditional queries
- Cache invalidation
- Query key conventions
- `mutate` vs `mutateAsync`
- Error handling
- Streaming requests
- UseRequestProcessor defaults

## Conditional Queries

Use the `enabled` option to conditionally run queries. Langflow hooks pass through `options` to `UseRequestProcessor`, which passes them to `useQuery`.

```typescript
// Pattern: Disable query when not authenticated
export const useGetGlobalVariables: useQueryFunctionType<
  undefined,
  GlobalVariable[]
> = (options?) => {
  const { query } = UseRequestProcessor()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  const getGlobalVariablesFn = async (): Promise<GlobalVariable[]> => {
    if (!isAuthenticated) return []
    const res = await api.get(`${getURL("VARIABLES")}/`)
    return res.data
  }

  return query(["useGetGlobalVariables"], getGlobalVariablesFn, {
    refetchOnWindowFocus: false,
    enabled: isAuthenticated && (options?.enabled ?? true),
    ...options,
  })
}
```

```typescript
// Pattern: Disable query when required param is missing
export const useGetFlow: useQueryFunctionType<{ id: string }, FlowResponse> = (
  params,
  options?,
) => {
  const { query } = UseRequestProcessor()

  const getFlowFn = async (): Promise<FlowResponse> => {
    const res = await api.get(`${getURL("FLOWS")}/${params.id}`)
    return res.data
  }

  return query(["useGetFlow", params.id], getFlowFn, {
    enabled: !!params.id && (options?.enabled ?? true),
    ...options,
  })
}
```

```typescript
// Pattern: Consumer disables query via options
const { data: flow } = useGetFlow(
  { id: flowId },
  { enabled: showFlowDetails },
)
```

Rules:
- Always check `options?.enabled ?? true` when combining with other conditions, so consumers can also disable the query.
- Guard early in the query function when auth or required data might be missing.
- Do not use non-null assertions on params to work around missing data; use `enabled` instead.

## Cache Invalidation

Bind invalidation in the mutation hook definition. Components should only add UI feedback (toasts, navigation) in call-site callbacks, not decide which queries to invalidate.

### Invalidation via onSettled

The `UseRequestProcessor.mutate()` wrapper already calls `queryClient.invalidateQueries({ queryKey: mutationKey })` in its default `onSettled`. For additional invalidation, extend `onSettled`:

```typescript
export const usePostAddFlow: useMutationFunctionType<
  undefined,
  PostAddFlowPayload
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor()
  const myCollectionId = useFolderStore((state) => state.myCollectionId)

  const postAddFlowFn = async (payload: PostAddFlowPayload): Promise<any> => {
    const response = await api.post(`${getURL("FLOWS")}/`, payload)
    return response.data
  }

  return mutate(["usePostAddFlow"], postAddFlowFn, {
    onSettled: (response) => {
      if (response) {
        queryClient.refetchQueries({
          queryKey: ["useGetRefreshFlowsQuery", { get_all: true, header_flows: true }],
        })
        queryClient.refetchQueries({
          queryKey: ["useGetFolder", response.folder_id ?? myCollectionId],
        })
      }
    },
    ...options,  // Consumer options come LAST
  })
}
```

### Invalidation Patterns

```typescript
// Broad invalidation: all queries for a domain
queryClient.invalidateQueries({ queryKey: ["useGetFlows"] })

// Specific invalidation: single cache entry
queryClient.invalidateQueries({ queryKey: ["useGetFlow", flowId] })

// Refetch instead of invalidate when you need data immediately
queryClient.refetchQueries({ queryKey: ["useGetFolder", folderId] })
```

### Component-side callbacks are for UI only

```typescript
// Component only adds UI behavior
const { mutate: addFlow } = usePostAddFlow()

const handleCreate = () => {
  addFlow(flowData, {
    onSuccess: (response) => {
      // UI-only: navigate, show toast
      navigate(`/flow/${response.id}`)
      setSuccessData({ title: "Flow created successfully" })
    },
    onError: (error) => {
      setErrorData({
        title: "Failed to create flow",
        list: [error.message],
      })
    },
  })
}
```

## Query Key Conventions

```typescript
// Base key: hook name
["useGetGlobalVariables"]

// Parameterized key: hook name + params
["useGetFlow", flowId]
["useGetFolder", folderId]

// Complex key: hook name + param object
["useGetRefreshFlowsQuery", { get_all: true, header_flows: true }]
["useGetMessages", { flowId, sessionId }]
["useGetBuilds", { flowId }]

// Mutation key: hook name (used for automatic invalidation by UseRequestProcessor)
["usePostAddFlow"]
["useDeleteMessages"]
```

Rules:
- First element is always the hook name as a string.
- Keep mutation keys matching the hook name.
- `UseRequestProcessor.mutate()` auto-invalidates the `mutationKey` on settled.
- Additional invalidation targets must be explicitly added in `onSettled`.

## `mutate` vs `mutateAsync`

Prefer `mutate` by default. Use `mutateAsync` only when Promise semantics are truly required.

Rules:
- Event handlers should call `mutate(...)` with `onSuccess` or `onError`.
- Every `await mutateAsync(...)` must be wrapped in `try/catch`.
- Do not use `mutateAsync` when callbacks already express the flow clearly.

```typescript
// Default: use mutate with callbacks
const { mutate: deleteFlow } = useDeleteFlow()

const handleDelete = () => {
  deleteFlow(flowId, {
    onSuccess: () => {
      navigate("/flows")
      setSuccessData({ title: "Flow deleted" })
    },
    onError: (error) => {
      setErrorData({ title: "Delete failed", list: [error.message] })
    },
  })
}

// Exception: Promise semantics needed for sequential operations
const handleDuplicateAndOpen = async () => {
  try {
    const newFlow = await duplicateFlow.mutateAsync(flowData)
    await renameFlow.mutateAsync({ id: newFlow.id, name: `${flowData.name} (copy)` })
    navigate(`/flow/${newFlow.id}`)
  } catch (error) {
    setErrorData({
      title: "Failed to duplicate flow",
      list: [error instanceof Error ? error.message : "Unknown error"],
    })
  }
}
```

## Error Handling

### API Interceptor Handles Auth Errors

The `ApiInterceptor` in `controllers/API/api.tsx` automatically handles:
- **401 Unauthorized**: Attempts token refresh via `useRefreshAccessToken`, then retries the request.
- **403 Forbidden**: Same auth error flow as 401.
- **After 3+ auth errors**: Logs the user out automatically.
- **500 errors**: Clears build vertex state in the flow store.

You do not need to handle 401/403 errors in individual hooks or components.

### Mutation Error Handling

Handle errors at the call site for user-facing feedback:

```typescript
const { mutate: saveFlow } = useSaveFlow()

const handleSave = () => {
  saveFlow(flowData, {
    onError: (error) => {
      setErrorData({
        title: "Failed to save flow",
        list: [error.response?.data?.detail ?? error.message],
      })
    },
  })
}
```

### Query Error Handling

For queries, React Query's retry logic (5 retries with exponential backoff via `UseRequestProcessor`) handles transient failures. For permanent errors, use `onError` in options or error boundaries:

```typescript
const { data, error, isError } = useGetFlow(
  { id: flowId },
  {
    retry: false, // Override default retry for known-missing resources
    onError: (error) => {
      if (error.response?.status === 404) {
        navigate("/flows")
      }
    },
  },
)
```

## Streaming Requests

Langflow uses `performStreamingRequest()` from `controllers/API/api.tsx` for build and chat streaming. This uses the browser `fetch` API (not Axios) with Server-Sent Events (SSE) parsing.

### Streaming Architecture

```typescript
import { performStreamingRequest } from "@/controllers/API/api"

const buildController = new AbortController()

await performStreamingRequest({
  method: "POST",
  url: `${baseURL}/api/v1/build/${flowId}/flow`,
  body: { inputs, files },
  buildController,
  onData: async (event) => {
    // Process individual SSE events
    // Return true to continue, false to abort
    return true
  },
  onDataBatch: async (events) => {
    // Process batch of events from a single chunk (more efficient)
    // Return true to continue, false to abort
    return true
  },
  onError: (statusCode) => {
    // Handle HTTP error status
  },
  onNetworkError: (error) => {
    // Handle network-level errors
  },
})
```

### Streaming vs REST Decision

| Operation | Method |
|-----------|--------|
| Build flow | `performStreamingRequest()` with SSE |
| Chat interaction | `performStreamingRequest()` with SSE |
| CRUD operations (flows, folders, variables) | Axios `api` instance via query/mutation hooks |
| File upload/download | Axios `api` instance |
| Auth operations | Axios `api` instance |

### Aborting Streams

Use `AbortController` to cancel streaming operations:

```typescript
const buildController = useRef(new AbortController())

const handleStopBuild = () => {
  buildController.current.abort()
  buildController.current = new AbortController()
}
```

## UseRequestProcessor Defaults

The `UseRequestProcessor` hook in `controllers/API/services/request-processor.ts` provides:

### Query Defaults

```typescript
{
  retry: 5,
  retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  // 1s, 2s, 4s, 8s, 16s (capped at 30s)
}
```

### Mutation Defaults

The actual `mutate()` implementation in `request-processor.ts`:

```typescript
function mutate(mutationKey, mutationFn, options = {}) {
  return useMutation({
    mutationKey,
    mutationFn,
    onSettled: (data, error, variables, context) => {
      queryClient.invalidateQueries({ queryKey: mutationKey });
      options.onSettled && options.onSettled(data, error, variables, context);
    },
    ...options,                              // Spreads AFTER the wrapper onSettled
    retry: options.retry ?? 3,               // Comes AFTER the spread
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}
```

**How onSettled actually works (important subtlety):**

1. `UseRequestProcessor.mutate()` defines a wrapper `onSettled` that (a) auto-invalidates the `mutationKey`, then (b) calls the hook's `options.onSettled`.
2. **However**, the `...options` spread comes AFTER the wrapper, so if the hook's `options` object contains its own `onSettled`, it **overrides** the wrapper. This means the auto-invalidation is effectively **skipped** when hooks provide their own `onSettled`.
3. In practice, most hooks DO provide their own `onSettled` with specific refetch/invalidation logic, so the auto-invalidation of the mutation key rarely runs.
4. This is fine because invalidating a mutation key is usually unnecessary — mutations don't have cached entries like queries do.

**Hook convention: place custom `onSettled` BEFORE `...options`:**

```typescript
mutate(["usePostAddFlow"], fn, {
  onSettled: () => { queryClient.refetchQueries(...) },  // Hook-specific invalidation
  retry: false,     // Override default retry if needed
  ...options,       // Consumer options come LAST (can override onSettled, retry, etc.)
})
```

### When to Use `retry: false`

Override the default `retry: 3` with `retry: false` for mutations where retrying would cause problems:

- **Create operations** that are not idempotent (duplicate creation risk)
- **Update operations** on global variables or settings (stale data risk)
- **Delete operations** where the resource may already be gone

```typescript
// Example: POST that creates a resource (not safe to retry)
const mutation = mutate(["usePostGlobalVariables"], postFn, {
  onSettled: () => { queryClient.refetchQueries({ queryKey: ["useGetGlobalVariables"] }) },
  retry: false,
  ...options,
})
```

## Polling Patterns

For queries that need periodic refreshing (build status, messages):

```typescript
export const useGetMessagesPolling: useQueryFunctionType<
  { flowId: string; sessionId: string },
  Message[]
> = (params, options?) => {
  const { query } = UseRequestProcessor()

  const getMessagesFn = async (): Promise<Message[]> => {
    const res = await api.get(
      `${getURL("MESSAGES")}/?flow_id=${params.flowId}&session_id=${params.sessionId}`,
    )
    return res.data
  }

  return query(
    ["useGetMessagesPolling", params.flowId, params.sessionId],
    getMessagesFn,
    {
      refetchInterval: 3000, // Poll every 3 seconds
      refetchIntervalInBackground: false,
      ...options,
    },
  )
}
```
