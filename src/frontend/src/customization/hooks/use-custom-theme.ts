// Custom Hook to manage theme logic

import { useEffect, useState } from "react";
import { useDarkStore } from "@/stores/darkStore";

const useTheme = () => {
  const [systemTheme, setSystemTheme] = useState(false);
  const { setDark, dark } = useDarkStore((state) => ({
    setDark: state.setDark,
    dark: state.dark,
  }));

  const handleSystemTheme = () => {
    if (typeof window !== "undefined") {
      const systemDarkMode = window.matchMedia(
        "(prefers-color-scheme: dark)",
      ).matches;
      setDark(systemDarkMode);
    }
  };

  useEffect(() => {
    const themePreference = localStorage.getItem("themePreference");
    if (themePreference === "light") {
      setDark(false);
      setSystemTheme(false);
    } else if (themePreference === "dark") {
      setDark(true);
      setSystemTheme(false);
    } else if (themePreference === "system") {
      // Only use system theme if explicitly set
      setSystemTheme(true);
      handleSystemTheme();
    } else {
      // Default to light theme when no preference is stored
      setDark(false);
      setSystemTheme(false);
      localStorage.setItem("themePreference", "light");
    }
  }, []);

  useEffect(() => {
    if (systemTheme && typeof window !== "undefined") {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      const handleChange = (e) => {
        setDark(e.matches);
      };
      mediaQuery.addEventListener("change", handleChange);
      return () => {
        mediaQuery.removeEventListener("change", handleChange);
      };
    }
  }, [systemTheme]);

  const setThemePreference = (theme) => {
    if (theme === "light") {
      setDark(false);
      setSystemTheme(false);
    } else if (theme === "dark") {
      setDark(true);
      setSystemTheme(false);
    } else {
      setSystemTheme(true);
      handleSystemTheme();
    }
    localStorage.setItem("themePreference", theme);
  };

  return { systemTheme, dark, setThemePreference };
};

export default useTheme;
