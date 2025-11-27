import "@xyflow/react/dist/style.css";
import { Suspense, useEffect } from "react";
import { RouterProvider } from "react-router-dom";
import { LoadingPage } from "./pages/LoadingPage";
import router from "./routes";
import { SidebarProvider } from "./contexts/sidebarContext";
import { create } from "zustand";
import { useThemeStore } from "./stores/themeStore";

// const THEMES = [
//   "light",
//   "dark",
//   "purple",
//   "contrast",
//   "teal",
//   "blue",
//   "green",
//   "pink",
//   "yellow",
//   "red",
// ];

// interface ThemeState {
//   theme: string;
//   setTheme: (theme: string) => void;
// }

// export const useThemeStore = create<ThemeState>((set) => ({
//   theme: "light",
//   setTheme: (theme) => set({ theme }),
// }));

export default function App() {
  // const theme = useThemeStore((state) => state.theme);
  const theme = useThemeStore((state) => state.theme);

  useEffect(() => {
    const body = document.body;
    const allThemes = [
      "light",
      "dark",
      "purple",
      "contrast",
      "teal",
      "blue",
      "green",
      "pink",
      "yellow",
      "red",
    ];

    body.classList.remove(...allThemes);

    if (theme !== "none") {
      body.classList.add(theme);
    }
  }, [theme]);

  // useEffect(() => {
  //   const body = document.getElementById("body");
  //   if (!body) return;
  //   // cleanly remove any theme class that exists
  //   for (const cls of THEMES) {
  //     if (body.classList.contains(cls)) body.classList.remove(cls);
  //   }

  //   // now add the active theme
  //   body.classList.add(theme);

  //   // 🧹 optional cleanup if remounts happen
  //   // return () => {
  //   //   body.classList.remove(theme);
  //   // };
  // }, [theme]);

  return (
    <SidebarProvider>
      <Suspense fallback={<LoadingPage />}>
        <RouterProvider router={router} />
      </Suspense>
    </SidebarProvider>
  );
}
