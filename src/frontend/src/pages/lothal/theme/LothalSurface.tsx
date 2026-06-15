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
  useEffect,
  useMemo,
  useState,
} from "react";
import "./lothal-theme.css";

// The dockyard fonts load only when a lothal surface actually mounts — the
// rest of Langflow never pays the two Google-Fonts requests. The link is
// injected once (id-guarded) and intentionally never removed: the fonts are
// cached, and removing it would flash unstyled text on the next visit.
const FONTS_LINK_ID = "lothal-fonts";
const FONTS_HREF =
  "https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap";

function ensureLothalFonts() {
  if (document.getElementById(FONTS_LINK_ID)) return;
  const link = document.createElement("link");
  link.id = FONTS_LINK_ID;
  link.rel = "stylesheet";
  link.href = FONTS_HREF;
  document.head.appendChild(link);
}

export type LothalThemeMode = "light" | "dark";
export type LothalDensity = "compact" | "regular" | "comfy";

// Appearance choices persist across mounts/reloads in localStorage so the
// surface doesn't snap back to its defaults every visit. Keys are namespaced to
// the lothal surface; reads are validated against the allowed values (a stale or
// hand-edited value falls back to the default) and wrapped because storage can
// throw in private-mode / sandboxed contexts.
const THEME_KEY = "lothal:theme";
const DENSITY_KEY = "lothal:density";
const THEMES: readonly LothalThemeMode[] = ["light", "dark"];
const DENSITIES: readonly LothalDensity[] = ["compact", "regular", "comfy"];

function readStored<T extends string>(
  key: string,
  allowed: readonly T[],
  fallback: T,
): T {
  try {
    const stored = window.localStorage.getItem(key) as T | null;
    return stored && allowed.includes(stored) ? stored : fallback;
  } catch {
    return fallback;
  }
}

function writeStored(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage unavailable (private mode, quota) — persistence is best-effort.
  }
}

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
  // Seed from localStorage (falling back to the given defaults) so a returning
  // user keeps their last appearance choice.
  const [theme, setThemeState] = useState<LothalThemeMode>(() =>
    readStored(THEME_KEY, THEMES, defaultTheme),
  );
  const [density, setDensityState] = useState<LothalDensity>(() =>
    readStored(DENSITY_KEY, DENSITIES, defaultDensity),
  );

  useEffect(() => {
    ensureLothalFonts();
  }, []);

  const value = useMemo<LothalThemeContextValue>(() => {
    const setTheme = (next: LothalThemeMode) => {
      writeStored(THEME_KEY, next);
      setThemeState(next);
    };
    const setDensity = (next: LothalDensity) => {
      writeStored(DENSITY_KEY, next);
      setDensityState(next);
    };
    return {
      theme,
      density,
      setTheme,
      setDensity,
      toggleTheme: () => setTheme(theme === "dark" ? "light" : "dark"),
    };
  }, [theme, density]);

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
