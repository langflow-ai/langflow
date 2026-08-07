import type { ReactNode } from "react";

export interface CustomLoginFormGateProps {
  children: ReactNode;
}

// OSS no-op: always renders the local username/password form.
// Downstream overlays can return null (or alternate UI) to hide the form on
// the primary login route while still showing it on a recovery route.
export default function CustomLoginFormGate({
  children,
}: CustomLoginFormGateProps) {
  return <>{children}</>;
}
