// Custom Hook to manage theme logic
import { useDarkStore } from "@/stores/darkStore";
import { useCallback, useEffect, useState } from "react";

const useTheme = () => {
  const [systemTheme, setSystemTheme] = useState(false);
  const setDark = useDarkStore((state) => state.setDark);
  const dark = useDarkStore((state) => state.dark);

  const updateDataThemeAttribute = useCallback((isDark: boolean) => {
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
    }
  }, []);

  const handleSystemTheme = useCallback(() => {
    if (typeof window !== "undefined") {
      const systemDarkMode = window.matchMedia(
        "(prefers-color-scheme: dark)",
      ).matches;
      setDark(systemDarkMode);
    }
  }, [setDark]);

  useEffect(() => {
    const themePreference = localStorage.getItem("themePreference");
    if (themePreference === "light") {
      setDark(false);
      setSystemTheme(false);
    } else if (themePreference === "dark") {
      setDark(true);
      setSystemTheme(false);
    } else if (themePreference === "system") {
      // Only use system theme if explicitly set to "system"
      setSystemTheme(true);
      handleSystemTheme();
    } else {
      // Default to light theme when no preference is stored
      setDark(false);
      setSystemTheme(false);
      localStorage.setItem("themePreference", "light");
    }
  }, [setDark, handleSystemTheme]);

  // Update data-theme attribute whenever dark state changes
  useEffect(() => {
    updateDataThemeAttribute(dark);
  }, [dark, updateDataThemeAttribute]);

  useEffect(() => {
    if (!systemTheme || typeof window === "undefined") {
      return;
    }

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (e: MediaQueryListEvent) => {
      setDark(e.matches);
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => {
      mediaQuery.removeEventListener("change", handleChange);
    };
  }, [systemTheme, setDark]);

  const setThemePreference = (theme: "light" | "dark" | "system") => {
    if (theme === "light") {
      setDark(false);
      setSystemTheme(false);
    } else if (theme === "dark") {
      setDark(true);
      setSystemTheme(false);
    } else if (theme === "system") {
      setSystemTheme(true);
      handleSystemTheme();
    }
    localStorage.setItem("themePreference", theme);
  };

  return { systemTheme, dark, setThemePreference };
};

export default useTheme;
