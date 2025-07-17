import { GradientWrapper } from "@/components/common/GradientWrapper";
import { CustomWrapper } from "@/customization/custom-wrapper";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactFlowProvider } from "@xyflow/react";
import { ReactNode } from "react";
import { TooltipProvider } from "../components/ui/tooltip";
import { ApiInterceptor } from "../controllers/API/api";
import { AuthProvider } from "./authContext";
import { IS_CLERK_AUTH } from "@/clerk/constants";
import { ClerkAuthAdapter } from "@/clerk/auth";

export default function ContextWrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient();
  //element to wrap all context
  return (
    <>
      <CustomWrapper>
        <GradientWrapper>
          <QueryClientProvider client={queryClient}>
            <AuthProvider>
              {IS_CLERK_AUTH && <ClerkAuthAdapter />}
              <TooltipProvider skipDelayDuration={0}>
                <ReactFlowProvider>
                  <ApiInterceptor />
                  {children}
                </ReactFlowProvider>
              </TooltipProvider>
            </AuthProvider>
          </QueryClientProvider>
        </GradientWrapper>
      </CustomWrapper>
    </>
  );
}
