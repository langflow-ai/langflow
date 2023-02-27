import { AlertProvider } from "./alertContext";
import { LocationProvider } from "./locationContext";
import PopUpProvider from "./popUpContext";
import { TabsProvider } from "./tabsContext";
import { TypesProvider } from "./typesContext";

export default function ContextWrapper({ children }) {
  //element to wrap all context
  return (
    <>
      <LocationProvider>
        <PopUpProvider>
          <TypesProvider>
            <TabsProvider>
              <AlertProvider>{children}</AlertProvider>
            </TabsProvider>
          </TypesProvider>
        </PopUpProvider>
      </LocationProvider>
    </>
  );
}
