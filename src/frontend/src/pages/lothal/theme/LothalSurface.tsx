// The lothal "surface": a themed container that scopes the dockyard design
// system to everything it wraps. It applies `data-theme` (light/dark) and
// `data-density` to a `.lothal-surface` element — the CSS variables in
// lothal-theme.css resolve only inside this subtree, so the rest of Langflow
// keeps its own theme. Provides `useLothalTheme()` for toggling.

import {
  type CSSProperties,
  createContext,
  type ReactNode,
  useContext,
  useMemo,
  useState,
} from "react";
import "./lothal-theme.css";

export type LothalThemeMode = "light" | "dark";
export type LothalDensity = "compact" | "regular" | "comfy";

type LothalThemeContextValue = {
  theme: LothalThemeMode;
  density: LothalDensity;
  setTheme: (theme: LothalThemeMode) => void;
  setDensity: (density: LothalDensity) => void;
  toggleTheme: () => void;
};

const LothalThemeContext = createContext<LothalThemeContextValue | null>(null);

export function useLothalTheme(): LothalThemeContextValue {
  const ctx = useContext(LothalThemeContext);
  if (!ctx) {
    throw new Error("useLothalTheme must be used within a <LothalSurface>");
  }
  return ctx;
}

export function LothalSurface({
  children,
  defaultTheme = "dark",
  defaultDensity = "regular",
  className,
  style,
}: {
  children: ReactNode;
  /** Dark is the design default. */
  defaultTheme?: LothalThemeMode;
  defaultDensity?: LothalDensity;
  className?: string;
  style?: CSSProperties;
}) {
  const [theme, setTheme] = useState<LothalThemeMode>(defaultTheme);
  const [density, setDensity] = useState<LothalDensity>(defaultDensity);

  const value = useMemo<LothalThemeContextValue>(
    () => ({
      theme,
      density,
      setTheme,
      setDensity,
      toggleTheme: () =>
        setTheme((current) => (current === "dark" ? "light" : "dark")),
    }),
    [theme, density],
  );

  return (
    <LothalThemeContext.Provider value={value}>
      <div
        className={className ? `lothal-surface ${className}` : "lothal-surface"}
        data-theme={theme}
        data-density={density}
        style={style}
      >
        <div className="lothal-surface__content">{children}</div>
      </div>
    </LothalThemeContext.Provider>
  );
}
