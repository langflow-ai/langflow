import { createContext, useEffect, useState } from "react";
import { getRepoStars } from "../controllers/API";
import { darkContextType } from "../types/typesContext";

const initialValue = {
  dark: {},
  setDark: () => {},
  stars: 0,
  setStars: (stars) => 0,
};

export const darkContext = createContext<darkContextType>(initialValue);

export function DarkProvider({ children }) {
  const [dark, setDark] = useState(
    JSON.parse(window.localStorage.getItem("isDark")!) ?? false
  );
  const [stars, setStars] = useState<number>(0);

  useEffect(() => {
    async function fetchStars() {
      const starsCount = await getRepoStars("logspace-ai", "langflow");
      setStars(starsCount);
    }
    fetchStars();
  }, []);

  useEffect(() => {
    if (dark) {
      document.getElementById("body")!.classList.add("dark");
    } else {
      document.getElementById("body")!.classList.remove("dark");
    }
    window.localStorage.setItem("isDark", dark.toString());
  }, [dark]);

  return (
    <darkContext.Provider
      value={{
        setStars,
        stars,
        dark,
        setDark,
      }}
    >
      {children}
    </darkContext.Provider>
  );
}
