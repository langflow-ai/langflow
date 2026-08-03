import type { ReactNode } from "react";

export interface CustomLoginFormGateProps {
  children: ReactNode;
}

// OSS no-op: always renders the local username/password form, preserving
// today's behavior. Downstream overlays (e.g. an SSO enterprise layer) can
// wrap this to decide whether the local form should render at all — for
// example, hiding it on the primary login route once an external identity
// provider connection is active, while still showing it on a dedicated
// recovery route. The decision is intentionally left to the override: OSS
// itself has no concept of alternate login methods.
export default function CustomLoginFormGate({
  children,
}: CustomLoginFormGateProps) {
  return <>{children}</>;
}
