import type { ReactNode } from "react";

export interface CustomSettingsPasswordFormGateProps {
  children: ReactNode;
}

// OSS no-op: always shows the Settings > General password form.
// Downstream overlays can suppress it without changing the community UI.
export default function CustomSettingsPasswordFormGate({
  children,
}: CustomSettingsPasswordFormGateProps) {
  return <>{children}</>;
}
