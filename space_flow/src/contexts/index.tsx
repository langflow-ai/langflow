import { AlertProvider } from "./alertContext";
import { LocationProvider } from "./locationContext";
import PopUpProvider from "./popUpContext";
import { TypesProvider } from "./typesContext";

export default function ContextWrapper({ children }) {
  return (
    <>
      <LocationProvider>
        <PopUpProvider>
          <TypesProvider>
            <AlertProvider>{children}</AlertProvider>
          </TypesProvider>
        </PopUpProvider>
      </LocationProvider>
    </>
  );
}
