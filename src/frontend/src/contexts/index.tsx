import { ReactNode } from "react";
import { BrowserRouter } from "react-router-dom";
import { ReactFlowProvider } from "reactflow";
import { TooltipProvider } from "../components/ui/tooltip";
import { ApiInterceptor } from "../controllers/API/api";
import { SSEProvider } from "./SSEContext";
import { AlertProvider } from "./alertContext";
import { AuthProvider } from "./authContext";
import { DarkProvider } from "./darkContext";
import FlowManagerProvider from "./flowManagerContext";
import { FlowsProvider } from "./flowsContext";
import { LocationProvider } from "./locationContext";
import { TypesProvider } from "./typesContext";
import { UndoRedoProvider } from "./undoRedoContext";

export default function ContextWrapper({ children }: { children: ReactNode }) {
  //element to wrap all context
  return (
    <>
      <BrowserRouter>
        <AlertProvider>
          <AuthProvider>
            <TooltipProvider>
              <ReactFlowProvider>
                <DarkProvider>
                  <TypesProvider>
                    <LocationProvider>
                      <ApiInterceptor />
                      <SSEProvider>
                        <FlowsProvider>
                          <UndoRedoProvider>
                            <FlowManagerProvider>
                              {children}
                            </FlowManagerProvider>
                          </UndoRedoProvider>
                        </FlowsProvider>
                      </SSEProvider>
                    </LocationProvider>
                  </TypesProvider>
                </DarkProvider>
              </ReactFlowProvider>
            </TooltipProvider>
          </AuthProvider>
        </AlertProvider>
      </BrowserRouter>
    </>
  );
}
