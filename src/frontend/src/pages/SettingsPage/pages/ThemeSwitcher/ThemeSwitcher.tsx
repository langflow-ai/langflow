import { useThemeStore } from "@/stores/themeStore";
import clsx from "clsx";
import { X } from "lucide-react"; // optional, if you want an icon-based version

const themes = [
  { name: "none", color: "transparent", label: "No Theme" },
  { name: "light", color: "#ffffff" },
  { name: "dark", color: "#0f0e11" },
  { name: "purple", color: "#7e22ce" },
  { name: "contrast", color: "#ff9900" },
  { name: "teal", color: "#14b8a6" },
  { name: "blue", color: "#2563eb" },
  { name: "green", color: "#22c55e" },
  { name: "red", color: "#ef4444" },
];

export default function ThemeSwitcher() {
  const { theme, setTheme } = useThemeStore();

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-[var(--tx-primary)]">
        Theme
      </span>

      <div className="flex flex-wrap gap-2">
        {themes.map((t) => (
          <button
            key={t.name}
            onClick={() => setTheme(t.name as any)}
            title={t.label || t.name}
            className={clsx(
              "w-8 h-8 rounded-md border flex items-center justify-center transition-all duration-200 shadow-sm",
              theme === t.name ? "border-2 border-primary" : "border-border"
            )}
            style={{
              backgroundColor: t.name === "none" ? "transparent" : t.color,
            }}
          >
            {t.name === "none" ? (
              // Inline SVG for better performance than importing a component
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                strokeWidth="1"
                className="text-destructive"
              >
                {/* <rect x="2.5" y="2.5" width="15" height="15" rx="2" ry="2" /> */}
                <line x1="4" y1="16" x2="16" y2="4" />
              </svg>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}
