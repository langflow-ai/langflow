import { AlertProvider } from "./alertContext";
import { LocationProvider } from "./locationContext";
import PopUpProvider from "./popUpContext";

export default function ContextWrapper({ children }) {
  return (
    <>
      <LocationProvider>
        <PopUpProvider>
          <AlertProvider>{children}</AlertProvider>
        </PopUpProvider>
      </LocationProvider>
    </>
  );
}
