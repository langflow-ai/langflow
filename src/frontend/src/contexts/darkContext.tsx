import { createContext, useEffect, useState } from "react";
import { darkContextType } from "../types/typesContext";

const initialValue = {
  dark: {},
  setDark: () => {},
};

export const darkContext = createContext<darkContextType>(initialValue);

export function DarkProvider({ children }) {
  const [dark, setDark] = useState(
    JSON.parse(window.localStorage.getItem("isDark")) ?? false
  );
  useEffect(() => {
    if (dark) {
      document.getElementById("body").classList.add("dark");
    } else {
      document.getElementById("body").classList.remove("dark");
    }
    window.localStorage.setItem("isDark", dark.toString());
  }, [dark]);
  return (
    <darkContext.Provider
      value={{
        dark,
        setDark,
      }}
    >
      {children}
    </darkContext.Provider>
  );
}
