import { ClerkProvider } from "@clerk/clerk-react";
import { ReactNode } from "react";
import { CLERK_PUBLISHABLE_KEY } from "@/constants/clerk";
import ClerkAuthAdapter from "./clerk-auth-adapter";

export default function ClerkAuthProvider({ children }: { children: ReactNode }) {
  return (
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY}>
      <ClerkAuthAdapter />
      {children}
    </ClerkProvider>
  );
}
