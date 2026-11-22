import type { TriggerRead } from "@/controllers/API/queries/triggers";
import { needsAttention } from "./trigger-presentation";

export type TriggerStateFilter =
  | "all"
  | "attention"
  | "pending"
  | "active"
  | "paused"
  | "expired"
  | "needs_reconnect"
  | "error";

export interface TriggerFilters {
  search: string;
  state: TriggerStateFilter;
  provider?: string;
}

const matchesState = (trigger: TriggerRead, state: TriggerStateFilter) => {
  if (state === "all") return true;
  if (state === "attention") return needsAttention(trigger);
  // `dead` renders as Error, so the Error filter includes it.
  if (state === "error")
    return trigger.state === "error" || trigger.state === "dead";
  return trigger.state === state;
};

/**
 * Search matches the flow, the trigger, its kind and provider, and (in the
 * operator view) the owner. Case- and accent-insensitive.
 */
export const filterTriggers = (
  triggers: readonly TriggerRead[],
  { search, state, provider }: TriggerFilters,
): TriggerRead[] => {
  const needle = normalize(search.trim());
  return triggers.filter((trigger) => {
    if (!matchesState(trigger, state)) return false;
    if (provider && trigger.provider !== provider) return false;
    if (!needle) return true;
    return [
      trigger.flow_name,
      trigger.name,
      trigger.kind,
      trigger.provider,
      trigger.owner_username,
    ].some((field) => field && normalize(field).includes(needle));
  });
};

const normalize = (value: string) =>
  value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export const providersOf = (triggers: readonly TriggerRead[]): string[] =>
  Array.from(
    new Set(
      triggers
        .map((trigger) => trigger.provider)
        .filter((provider): provider is string => Boolean(provider)),
    ),
  ).sort();
