import type { ReactNode } from "react";

export interface CustomModelProvidersEmptyStateProps {
  children: ReactNode;
  kind: "providers" | "models";
  show: boolean;
}

// OSS pass-through. Enterprise replaces this seam with provider/model empty
// states and uses `show` to decide whether to replace the supplied content.
export default function CustomModelProvidersEmptyState({
  children,
}: CustomModelProvidersEmptyStateProps) {
  return <>{children}</>;
}
