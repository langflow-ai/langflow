import type { ReactNode } from "react";

export type CustomListResourceType =
  | "flow"
  | "knowledge_base"
  | "variable"
  | "file";

export interface CustomResourceListFilterState<T> {
  /** Rows the page renders, before its own search, sort and pagination. */
  items: T[];
  /** Controls the page places in its toolbar (e.g. an All | Owned switch). */
  tools: ReactNode;
}

// Default seam: OSS shows every item it receives and adds no controls.
export function useCustomResourceListFilter<T>(
  _resourceType: CustomListResourceType,
  items: T[],
  _isOwned: (item: T) => boolean,
): CustomResourceListFilterState<T> {
  return { items, tools: null };
}
