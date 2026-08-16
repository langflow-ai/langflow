import type { ReactNode } from "react";

export interface CustomLoginSignupPromptProps {
  children: ReactNode;
}

// OSS no-op: always shows the "Don't have an account? Sign Up" block.
// Downstream overlays (e.g. Enterprise) can return null to suppress public
// self-registration on the login page while leaving the OSS route intact.
export default function CustomLoginSignupPrompt({
  children,
}: CustomLoginSignupPromptProps) {
  return <>{children}</>;
}
