import { ReactNode } from "react";
import { AlertProvider } from "./alertContext";
import { DarkProvider } from "./darkContext";
import { LocationProvider } from "./locationContext";
import PopUpProvider from "./popUpContext";
import { TabsProvider } from "./tabsContext";
import { TypesProvider } from "./typesContext";
import { ReactFlowProvider } from "reactflow";
import { UndoRedoProvider } from "./undoRedoContext";
import { SSEProvider } from "./SSEContext";

export default function ContextWrapper({ children }: { children: ReactNode }) {
  //element to wrap all context
  return (
    <>
      <ReactFlowProvider>
        <DarkProvider>
          <TypesProvider>
            <LocationProvider>
              <AlertProvider>
                <SSEProvider>
                  <TabsProvider>
                    <UndoRedoProvider>
                      <PopUpProvider>{children}</PopUpProvider>
                    </UndoRedoProvider>
                  </TabsProvider>
                </SSEProvider>
              </AlertProvider>
            </LocationProvider>
          </TypesProvider>
        </DarkProvider>
      </ReactFlowProvider>
    </>
  );
}
