import type { TriggerListParams } from "./types";

/**
 * Query keys for triggers. The canvas badge and the settings table read the
 * same records, so every mutation invalidates `all` and both converge.
 */
export const triggersKeys = {
  all: ["triggers"] as const,
  lists: () => [...triggersKeys.all, "list"] as const,
  list: (params: TriggerListParams = {}) =>
    [
      ...triggersKeys.lists(),
      params.flowId ?? "*",
      params.scope ?? "mine",
      params.provider ?? "*",
      params.state ?? "*",
      params.limit ?? null,
      params.offset ?? 0,
    ] as const,
  one: (id: string) => [...triggersKeys.all, "one", id] as const,
  events: (id: string) => [...triggersKeys.all, "events", id] as const,
  ingress: (id: string) => [...triggersKeys.all, "ingress", id] as const,
  sessions: (flowId: string, sessionIds: readonly string[]) =>
    [...triggersKeys.all, "sessions", flowId, ...sessionIds] as const,
} as const;
