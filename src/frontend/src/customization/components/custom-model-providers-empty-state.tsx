import type { ReactNode } from "react";

export interface CustomModelProvidersEmptyStateProps {
  children: ReactNode;
  kind: "providers" | "models";
  show: boolean;
}

export default function CustomModelProvidersEmptyState({
  children,
}: CustomModelProvidersEmptyStateProps) {
  return <>{children}</>;
}
