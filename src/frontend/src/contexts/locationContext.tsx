import { createContext, ReactNode, useState } from "react";
import { locationContextType } from "../types/typesContext";

//initial value for location context
const initialValue = {
  //actual
  current: window.location.pathname.replace(/\/$/g, "").split("/"),
  isStackedOpen:
    window.innerWidth > 1024 && window.location.pathname.split("/")[1]
      ? true
      : false,
  setCurrent: () => {},
  setIsStackedOpen: () => {},
  showSideBar: window.location.pathname.split("/")[1] ? true : false,
  setShowSideBar: () => {},
  extraNavigation: { title: "" },
  setExtraNavigation: () => {},
  extraComponent: <></>,
  setExtraComponent: () => {},
};

export const locationContext = createContext<locationContextType>(initialValue);

export function LocationProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState(initialValue.current);
  const [isStackedOpen, setIsStackedOpen] = useState(
    initialValue.isStackedOpen
  );
  const [showSideBar, setShowSideBar] = useState(initialValue.showSideBar);
  const [extraNavigation, setExtraNavigation] = useState({ title: "" });
  const [extraComponent, setExtraComponent] = useState(<></>);
  return (
    <locationContext.Provider
      value={{
        isStackedOpen,
        setIsStackedOpen,
        current,
        setCurrent,
        showSideBar,
        setShowSideBar,
        extraNavigation,
        setExtraNavigation,
        extraComponent,
        setExtraComponent,
      }}
    >
      {children}
    </locationContext.Provider>
  );
}
