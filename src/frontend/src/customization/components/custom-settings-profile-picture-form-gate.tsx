import type { ReactNode } from "react";

export interface CustomSettingsProfilePictureFormGateProps {
  children: ReactNode;
}

export default function CustomSettingsProfilePictureFormGate({
  children,
}: CustomSettingsProfilePictureFormGateProps): ReactNode {
  return <>{children}</>;
}
