import { ReactNode } from "react";
import { BrowserRouter } from "react-router-dom";
import { ReactFlowProvider } from "reactflow";
import { TooltipProvider } from "../components/ui/tooltip";
import { ApiInterceptor } from "../controllers/API/api";
import { AuthProvider } from "./authContext";

export default function ContextWrapper({ children }: { children: ReactNode }) {
  //element to wrap all context
  return (
    <>
      <BrowserRouter>
        <AuthProvider>
          <TooltipProvider>
            <ReactFlowProvider>
              <ApiInterceptor />
              {children}
            </ReactFlowProvider>
          </TooltipProvider>
        </AuthProvider>
      </BrowserRouter>
    </>
  );
}
