---
name: frontend-query-mutation
description: Guide for implementing Langflow frontend query and mutation patterns with Axios and TanStack React Query v5. Trigger when creating or updating API hooks in controllers/API/queries, consuming UseRequestProcessor in components, deciding whether to use useQuery or useMutation, handling conditional queries, cache invalidation, mutation error handling, or migrating legacy API calls to the query hook pattern.
---

# Frontend Query & Mutation

## Intent

- Keep API hooks in `controllers/API/queries/{domain}/` as the organized source of truth.
- Use `UseRequestProcessor` for consistent retry, invalidation, and error handling.
- Use Axios `api` instance for all HTTP calls (never raw `fetch` for REST).
- Use `performStreamingRequest()` for streaming operations (build, chat).
- Keep cache invalidation in mutation `onSettled` callbacks.

## Architecture Overview

Langflow uses **Axios + TanStack React Query v5** for data fetching. There is no oRPC or contract layer. The architecture is:

```
Component
  -> API hook (controllers/API/queries/{domain}/use-{verb}-{resource}.ts)
    -> UseRequestProcessor (controllers/API/services/request-processor.ts)
      -> useQuery / useMutation (TanStack React Query)
        -> queryFn / mutationFn
          -> api.get/post/patch/delete (Axios instance from controllers/API/api.tsx)
```

### Key Files

| File | Purpose |
|------|---------|
| `controllers/API/api.tsx` | Axios instance, `ApiInterceptor` component, `performStreamingRequest()` |
| `controllers/API/services/request-processor.ts` | `UseRequestProcessor` hook wrapping `useQuery`/`useMutation` with retry defaults |
| `controllers/API/helpers/constants.ts` | URL constants (`URLs`) and `getURL()` helper |
| `controllers/API/queries/{domain}/` | Domain-organized query and mutation hooks |
| `types/api/index.ts` | `useQueryFunctionType`, `useMutationFunctionType` type helpers |
| `stores/` | Zustand stores for client-side state |

## Workflow

1. Identify the change surface.
   - Read `references/query-patterns.md` for hook structure, naming, URL patterns, and query/mutation call-site shape.
   - Read `references/runtime-rules.md` for conditional queries, invalidation, error handling, and streaming.
   - Read both references when a task spans hook creation and runtime behavior.
2. Implement the hook following existing patterns.
   - Use `UseRequestProcessor` for `query()` and `mutate()` wrappers.
   - Use the `api` Axios instance for all HTTP calls.
   - Use `getURL()` for constructing API paths.
   - Type the hook with `useQueryFunctionType` or `useMutationFunctionType`.
3. Preserve Langflow conventions.
   - Query keys are arrays with the hook name: `["useGetFlows"]`.
   - Mutations invalidate related queries in `onSettled`.
   - Zustand store updates happen in the query/mutation function, not in components.
   - `UseRequestProcessor` provides default retry (5 for queries, 3 for mutations) with exponential backoff.

## Files Commonly Touched

- `controllers/API/queries/{domain}/use-get-*.ts` (query hooks)
- `controllers/API/queries/{domain}/use-post-*.ts` (create mutations)
- `controllers/API/queries/{domain}/use-patch-*.ts` (update mutations)
- `controllers/API/queries/{domain}/use-delete-*.ts` (delete mutations)
- `controllers/API/helpers/constants.ts` (URL constants)
- `types/api/index.ts` (API type definitions)
- `stores/` (Zustand store updates triggered by queries)

## References

- Use `references/query-patterns.md` for hook structure, naming conventions, directory layout, and anti-patterns.
- Use `references/runtime-rules.md` for conditional queries, invalidation, `mutate` versus `mutateAsync`, error handling, and streaming requests.

Treat this skill as the single query and mutation entry point for Langflow frontend work. Keep detailed rules in the reference files instead of duplicating them in project docs.
