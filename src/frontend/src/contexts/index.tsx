import { ReactNode } from "react";
import { ReactFlowProvider } from "reactflow";
import { TooltipProvider } from "../components/ui/tooltip";
import { SSEProvider } from "./SSEContext";
import { AlertProvider } from "./alertContext";
import { DarkProvider } from "./darkContext";
import { LocationProvider } from "./locationContext";
import { TabsProvider } from "./tabsContext";
import { TypesProvider } from "./typesContext";
import { UndoRedoProvider } from "./undoRedoContext";
import { AuthProvider } from "./authContext";

export default function ContextWrapper({ children }: { children: ReactNode }) {
  //element to wrap all context
  return (
    <>
      <TooltipProvider>
        <ReactFlowProvider>
          <DarkProvider>
            <TypesProvider>
              <LocationProvider>
                <AuthProvider>
                <AlertProvider>
                  <SSEProvider>
                    <TabsProvider>
                      <UndoRedoProvider>{children}</UndoRedoProvider>
                    </TabsProvider>
                  </SSEProvider>
                </AlertProvider>
                </AuthProvider>
              </LocationProvider>
            </TypesProvider>
          </DarkProvider>
        </ReactFlowProvider>
      </TooltipProvider>
    </>
  );
}
