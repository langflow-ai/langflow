import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { BrowserRouter } from "react-router-dom";
import { ReactFlowProvider } from "reactflow";
import { TooltipProvider } from "../components/ui/tooltip";
import { ApiInterceptor } from "../controllers/API/api";
import { AuthProvider } from "./authContext";

export default function ContextWrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient();
  //element to wrap all context
  return (
    <>
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <TooltipProvider>
              <ReactFlowProvider>
                <ApiInterceptor />
                {children}
              </ReactFlowProvider>
            </TooltipProvider>
          </AuthProvider>
        </QueryClientProvider>
      </BrowserRouter>
    </>
  );
}
