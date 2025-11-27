import { create } from "zustand";

export type Theme =
  | "none"
  | "light"
  | "dark"
  | "purple"
  | "contrast"
  | "teal"
  | "blue"
  | "green"
  | "pink"
  | "yellow"
  | "red";

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleDarkMode: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: (localStorage.getItem("themePreference") as Theme) || "none",

  setTheme: (theme) => {
    if (theme === "none") {
      localStorage.removeItem("themePreference");
    } else {
      localStorage.setItem("themePreference", theme);
    }
    set({ theme });
  },

  toggleDarkMode: () => {
    const current = get().theme;
    // if theme is "none", start with dark
    const newTheme =
      current === "dark" ? "light" : current === "light" ? "dark" : "dark";

    localStorage.setItem("themePreference", newTheme);
    set({ theme: newTheme });
  },
}));
