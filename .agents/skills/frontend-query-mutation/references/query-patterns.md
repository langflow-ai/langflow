# Query and Mutation Patterns

## Table of Contents

- Intent
- Directory structure
- Query hook structure
- Mutation hook structure
- URL constants
- Query keys
- Type signatures
- Anti-patterns

## Intent

- Keep API hooks in `controllers/API/queries/{domain}/` organized by domain.
- Use `UseRequestProcessor` for consistent behavior across all hooks.
- Use the shared `api` Axios instance for all REST calls.
- Type hooks with `useQueryFunctionType` or `useMutationFunctionType` from `types/api/`.

## Directory Structure

```text
controllers/API/
  api.tsx                          # Axios instance, interceptors, streaming
  helpers/
    constants.ts                   # URL constants and getURL()
  services/
    request-processor.ts           # UseRequestProcessor hook
  queries/
    flows/
      use-get-flow.ts
      use-get-refresh-flows-query.ts
      use-post-add-flow.ts
      use-delete-delete-flows.ts
      use-get-download-flows.ts
      index.ts
    folders/
      use-get-folder.ts
      use-get-folders.ts
      use-post-folders.ts
      use-patch-folders.ts
      use-delete-folders.ts
      index.ts
    variables/
      use-get-global-variables.ts
      use-post-global-variables.ts
      use-patch-global-variables.ts
      index.ts
    auth/
      use-get-autologin.ts
      use-post-login-user.ts
      use-post-logout.ts
      use-post-refresh-access.ts
      index.ts
    messages/
      use-get-messages.ts
      use-get-messages-polling.ts
      use-delete-messages.ts
      index.ts
```

### Naming Convention

- **Queries**: `use-get-{resource}.ts` (e.g., `use-get-flow.ts`, `use-get-global-variables.ts`)
- **Create mutations**: `use-post-{resource}.ts` (e.g., `use-post-add-flow.ts`)
- **Update mutations**: `use-patch-{resource}.ts` (e.g., `use-patch-global-variables.ts`)
- **Delete mutations**: `use-delete-{resource}.ts` (e.g., `use-delete-messages.ts`)
- **Other mutations**: `use-{action}-{resource}.ts` (e.g., `use-rename-session.ts`)

## Query Hook Structure

Every query hook follows this structure:

```typescript
import type { UseQueryResult } from "@tanstack/react-query"
import type { useQueryFunctionType } from "@/types/api"
import { api } from "../../api"
import { getURL } from "../../helpers/constants"
import { UseRequestProcessor } from "../../services/request-processor"

// 1. Define the response type (or import from types/)
interface GlobalVariable {
  id: string
  name: string
  value: string
  type: string
}

// 2. Export the hook typed with useQueryFunctionType
export const useGetGlobalVariables: useQueryFunctionType<
  undefined,
  GlobalVariable[]
> = (options?) => {
  // 3. Get query helper from UseRequestProcessor
  const { query } = UseRequestProcessor()

  // 4. Define the query function using the api Axios instance
  const getGlobalVariablesFn = async (): Promise<GlobalVariable[]> => {
    const res = await api.get(`${getURL("VARIABLES")}/`)
    return res.data
  }

  // 5. Return the query result
  const queryResult: UseQueryResult<GlobalVariable[], Error> = query(
    ["useGetGlobalVariables"],
    getGlobalVariablesFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  )

  return queryResult
}
```

### Query Hook with Parameters

When a query takes parameters, use the first type argument:

```typescript
export const useGetFolder: useQueryFunctionType<
  { id: string },
  FolderResponse
> = (params, options?) => {
  const { query } = UseRequestProcessor()

  const getFolderFn = async (): Promise<FolderResponse> => {
    const res = await api.get(`${getURL("FOLDERS")}/${params.id}`)
    return res.data
  }

  return query(["useGetFolder", params.id], getFolderFn, {
    ...options,
  })
}
```

### Important: Some "get" Hooks Use Mutation

In the Langflow codebase, some hooks named `use-get-*` (e.g., `useGetFlow`) are actually **mutation hooks** typed with `useMutationFunctionType`. This happens when the "get" operation is triggered imperatively (on demand) rather than declaratively (on mount/re-render). Check the actual type signature before following the query pattern — if a hook uses `mutate` from `UseRequestProcessor`, follow the Mutation Hook Structure below instead.

### Query Hook with Store Updates

Many Langflow queries update Zustand stores as a side effect within the query function:

```typescript
export const useGetGlobalVariables: useQueryFunctionType<
  undefined,
  GlobalVariable[]
> = (options?) => {
  const { query } = UseRequestProcessor()

  // Access store setters
  const setGlobalVariablesEntries = useGlobalVariablesStore(
    (state) => state.setGlobalVariablesEntries,
  )

  const getGlobalVariablesFn = async (): Promise<GlobalVariable[]> => {
    const res = await api.get(`${getURL("VARIABLES")}/`)
    // Update store as side effect of fetching
    setGlobalVariablesEntries(res.data.map((entry) => entry.name))
    return res.data
  }

  return query(["useGetGlobalVariables"], getGlobalVariablesFn, {
    refetchOnWindowFocus: false,
    ...options,
  })
}
```

## Mutation Hook Structure

Every mutation hook follows this structure:

```typescript
import type { UseMutationResult } from "@tanstack/react-query"
import type { useMutationFunctionType } from "@/types/api"
import { api } from "../../api"
import { getURL } from "../../helpers/constants"
import { UseRequestProcessor } from "../../services/request-processor"

// 1. Define the payload type
interface PostAddFlowPayload {
  name: string
  data: ReactFlowJsonObject
  description: string
  folder_id: string
}

// 2. Export the hook typed with useMutationFunctionType
export const usePostAddFlow: useMutationFunctionType<
  undefined,       // Params (undefined if none)
  PostAddFlowPayload  // Variables (mutation payload)
> = (options?) => {
  // 3. Get mutate helper and queryClient from UseRequestProcessor
  const { mutate, queryClient } = UseRequestProcessor()

  // 4. Define the mutation function using the api Axios instance
  const postAddFlowFn = async (payload: PostAddFlowPayload): Promise<any> => {
    const response = await api.post(`${getURL("FLOWS")}/`, {
      name: payload.name,
      data: payload.data,
      description: payload.description,
      folder_id: payload.folder_id || null,
    })
    return response.data
  }

  // 5. Return the mutation with cache invalidation in onSettled
  // NOTE: Place hook-specific options (onSettled, retry) BEFORE ...options
  // so consumers can override them if needed. This matches the codebase convention.
  const mutation: UseMutationResult<any, any, PostAddFlowPayload> = mutate(
    ["usePostAddFlow"],
    postAddFlowFn,
    {
      onSettled: (response) => {
        if (response) {
          // Invalidate related queries so they refetch
          queryClient.refetchQueries({
            queryKey: ["useGetRefreshFlowsQuery", { get_all: true, header_flows: true }],
          })
          queryClient.refetchQueries({
            queryKey: ["useGetFolder", response.folder_id],
          })
        }
      },
      ...options,  // Consumer options come LAST (can override onSettled, retry, etc.)
    },
  )

  return mutation
}
```

### Delete Mutation Example

```typescript
export const useDeleteMessages: useMutationFunctionType<undefined, string[]> = (
  options?,
) => {
  const { mutate, queryClient } = UseRequestProcessor()

  const deleteMessagesFn = async (messageIds: string[]): Promise<void> => {
    await api.delete(`${getURL("MESSAGES")}/`, {
      data: messageIds,
    })
  }

  const mutation = mutate(["useDeleteMessages"], deleteMessagesFn, {
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["useGetMessages"] })
    },
    ...options,
  })

  return mutation
}
```

### Patch Mutation Example

```typescript
export const usePatchGlobalVariables: useMutationFunctionType<
  undefined,
  { id: string; name: string; value: string; type: string }
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor()

  const patchGlobalVariablesFn = async (payload: {
    id: string
    name: string
    value: string
    type: string
  }): Promise<GlobalVariable> => {
    const response = await api.patch(
      `${getURL("VARIABLES")}/${payload.id}`,
      payload,
    )
    return response.data
  }

  const mutation = mutate(["usePatchGlobalVariables"], patchGlobalVariablesFn, {
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["useGetGlobalVariables"] })
    },
    retry: false,
    ...options,
  })

  return mutation
}
```

## URL Constants

All API paths are defined in `controllers/API/helpers/constants.ts`:

```typescript
export const URLs = {
  FLOWS: "flows",
  FOLDERS: "projects",
  VARIABLES: "variables",
  MESSAGES: "monitor/messages",
  BUILDS: "monitor/builds",
  API_KEY: "api_key",
  FILES: "files",
  // ...
} as const
```

Use `getURL()` to construct full API paths:

```typescript
import { getURL } from "../../helpers/constants"

// Basic: /api/v1/flows
const url = getURL("FLOWS")

// With params: /api/v1/flows/{flowId}
const url = `${getURL("FLOWS")}/${flowId}`

// With v2 flag: /api/v2/flows
const url = getURL("FLOWS", {}, true)
```

When adding new endpoints, add the constant to `URLs` first, then use `getURL()` in the hook.

## Query Keys

Query keys are arrays that uniquely identify cached data. Langflow conventions:

```typescript
// Hook name as key (no params)
["useGetGlobalVariables"]

// Hook name + params for cache isolation
["useGetFlow", flowId]
["useGetFolder", folderId]

// Hook name + object params for complex queries
["useGetRefreshFlowsQuery", { get_all: true, header_flows: true }]
["useGetMessages", { flowId, sessionId, page }]
```

Rules:
- The first element is always the hook name as a string.
- Additional elements are parameters that differentiate cache entries.
- Use objects for multi-parameter queries.
- Keep keys consistent so invalidation works correctly.

## Type Signatures

### useQueryFunctionType

Used for query hooks. Defined in `types/api/index.ts`:

```typescript
// Without params: useQueryFunctionType<undefined, ResponseType>
// The hook signature becomes: (options?) => UseQueryResult<ResponseType>

// With params: useQueryFunctionType<ParamsType, ResponseType>
// The hook signature becomes: (params, options?) => UseQueryResult<ResponseType>
```

### useMutationFunctionType

Used for mutation hooks:

```typescript
// Without params: useMutationFunctionType<undefined, VariablesType>
// The hook signature becomes: (options?) => UseMutationResult<Data, Error, Variables>

// With params: useMutationFunctionType<ParamsType, VariablesType>
// The hook signature becomes: (params, options?) => UseMutationResult<Data, Error, Variables>
```

## Anti-Patterns

### Do Not Bypass UseRequestProcessor

```typescript
// Do not call useQuery/useMutation directly
const result = useQuery({
  queryKey: ["flows"],
  queryFn: () => api.get("/api/v1/flows"),
})

// Use UseRequestProcessor for consistent retry and error handling
const { query } = UseRequestProcessor()
const result = query(["useGetFlows"], () => api.get(getURL("FLOWS")))
```

### Do Not Bypass the api Instance

```typescript
// Do not use raw axios or fetch for REST calls
const result = await axios.get("/api/v1/flows")
const result = await fetch("/api/v1/flows")

// Use the shared api instance (has interceptors for auth, headers, error handling)
const result = await api.get(`${getURL("FLOWS")}/`)
```

### Do Not Hardcode URLs

```typescript
// Do not hardcode API paths
const result = await api.get("/api/v1/variables/")

// Use getURL() helper
const result = await api.get(`${getURL("VARIABLES")}/`)
```

### Do Not Duplicate Query Keys

```typescript
// Do not use different key strings for the same query
query(["getFlows"], fetchFn)       // in hook A
query(["useGetFlows"], fetchFn)    // in hook B
query(["flows-list"], fetchFn)     // in hook C

// Use one canonical key matching the hook name
query(["useGetFlows"], fetchFn)
```

### Do Not Invalidate from Components

```typescript
// Do not put invalidation logic in components
const Component = () => {
  const queryClient = useQueryClient()
  const { mutate } = useDeleteFlow()

  const handleDelete = () => {
    mutate(flowId, {
      onSuccess: () => {
        // Avoid: invalidation knowledge leaks into component
        queryClient.invalidateQueries({ queryKey: ["useGetFlows"] })
        queryClient.invalidateQueries({ queryKey: ["useGetFolder"] })
      },
    })
  }
}

// Put invalidation in the mutation hook's onSettled
export const useDeleteFlow = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor()

  return mutate(["useDeleteFlow"], deleteFlowFn, {
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["useGetFlows"] })
      queryClient.invalidateQueries({ queryKey: ["useGetFolder"] })
    },
    ...options,  // Consumer options come LAST
  })
}
```

### Do Not Create Thin Wrapper Hooks

```typescript
// Do not create hooks that just re-export an existing query hook
const useFlows = () => {
  return useGetRefreshFlowsQuery({ get_all: true })
}

// Import the existing hook directly where needed
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows"
```
