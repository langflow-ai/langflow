import type { ReactNode } from "react";
import type { CustomListResourceType } from "@/customization/hooks/use-custom-resource-list-filter";

export interface CustomResourceAccessLabelProps {
  resourceType: CustomListResourceType;
  resourceId: string;
  isOwned: boolean;
  /** Shown when there is no more precise label (OSS always shows it). */
  fallback?: ReactNode;
}

// OSS no-op beyond the caller's fallback. Enterprise replaces this seam with a
// per-row line saying why the user can see an item they don't own (a direct
// share or a role).
export default function CustomResourceAccessLabel({
  fallback,
}: CustomResourceAccessLabelProps) {
  return fallback ?? null;
}
