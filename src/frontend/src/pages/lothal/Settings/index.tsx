// Lothal settings (Story B.11) — a real page behind the Dashboard/Workspace
// "Settings" entry, which used to be inert text. Three concerns:
//   • Appearance — theme + density toggles, persisted by LothalSurface so the
//     choice survives reloads (no more reset-on-mount).
//   • Account — who you're signed in as, plus sign-out.
//   • Keys & providers — we don't rebuild Langflow's credential UIs; we link out
//     to them (the GitHub PAT lives in global variables; API keys in api-keys).
//
// Provider/LLM switching is out of scope (Story 0.1's registry is backend env).

import { useNavigate } from "react-router-dom";
import { useLogout } from "@/controllers/API/queries/auth/use-post-logout";
import useAuthStore from "@/stores/authStore";
import { Button, LOTHAL_VERSION, LothalMark, TopBar } from "../components";
import {
  type LothalDensity,
  LothalSurface,
  type LothalThemeMode,
  useLothalTheme,
} from "../theme/LothalSurface";

function ArrowLeft({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M9.5 3.5 5 8l4.5 4.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ExternalGlyph({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M6 3h7v7M13 3 6.5 9.5M11 9.5V13H3V5h3.5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// A titled block with an optional one-line description. The page is a stack of
// these so each concern reads as its own card on the surface.
function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        padding: 22,
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      <div>
        <h2 className="serif" style={{ fontSize: 21 }}>
          {title}
        </h2>
        {description && (
          <p
            style={{
              marginTop: 4,
              fontSize: 13,
              lineHeight: 1.5,
              color: "var(--ink-mute)",
            }}
          >
            {description}
          </p>
        )}
      </div>
      {children}
    </section>
  );
}

// One labelled row inside a section: a left-aligned label/hint and a
// right-aligned control group.
function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        flexWrap: "wrap",
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 14, color: "var(--ink)" }}>{label}</div>
        {hint && (
          <div style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 2 }}>
            {hint}
          </div>
        )}
      </div>
      <div style={{ display: "inline-flex", gap: 8 }}>{children}</div>
    </div>
  );
}

const THEME_OPTIONS: { value: LothalThemeMode; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];
const DENSITY_OPTIONS: LothalDensity[] = ["compact", "regular", "comfy"];

function SettingsView() {
  const navigate = useNavigate();
  const { theme, setTheme, density, setDensity } = useLothalTheme();
  const username = useAuthStore((s) => s.userData?.username);
  const initial = username ? username.charAt(0).toUpperCase() : "?";
  const logout = useLogout();

  const handleLogout = () => {
    logout.mutate(undefined, {
      // Land on the public entry point once the session is cleared. Navigate on
      // settle so a logout-endpoint hiccup still returns the user to "/".
      onSettled: () => navigate("/"),
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <TopBar
        left={
          <span
            style={{ display: "inline-flex", alignItems: "center", gap: 12 }}
          >
            <button
              type="button"
              aria-label="Back to projects"
              onClick={() => navigate("/lothal")}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 28,
                height: 28,
                borderRadius: 7,
                border: "1px solid var(--border)",
                background: "transparent",
                color: "var(--ink-mute)",
                cursor: "pointer",
              }}
            >
              <ArrowLeft />
            </button>
            <span style={{ color: "var(--accent)", display: "inline-flex" }}>
              <LothalMark size={20} />
            </span>
            <span className="serif" style={{ fontSize: 21 }}>
              Settings
            </span>
            <span
              className="mono"
              style={{ fontSize: 11, color: "var(--ink-soft)" }}
            >
              v{LOTHAL_VERSION}
            </span>
          </span>
        }
      />

      <main style={{ flex: 1, overflowY: "auto" }}>
        <div
          style={{
            maxWidth: 720,
            margin: "0 auto",
            padding: "32px 28px 48px",
            display: "flex",
            flexDirection: "column",
            gap: 20,
          }}
        >
          <Section
            title="Appearance"
            description="How the Lothal surface looks. Your choice is saved on this device."
          >
            <Field label="Theme">
              {THEME_OPTIONS.map((opt) => (
                <Button
                  key={opt.value}
                  size="sm"
                  variant={theme === opt.value ? "accent" : "outline"}
                  aria-pressed={theme === opt.value}
                  onClick={() => setTheme(opt.value)}
                >
                  {opt.label}
                </Button>
              ))}
            </Field>
            <Field label="Density">
              {DENSITY_OPTIONS.map((d) => (
                <Button
                  key={d}
                  size="sm"
                  variant={density === d ? "accent" : "outline"}
                  aria-pressed={density === d}
                  onClick={() => setDensity(d)}
                  style={{ textTransform: "capitalize" }}
                >
                  {d}
                </Button>
              ))}
            </Field>
          </Section>

          <Section title="Account">
            <Field
              label={username ?? "Signed in"}
              hint={username ? "Signed in to Lothal" : undefined}
            >
              <span
                aria-hidden
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  background: "var(--accent)",
                  color: "var(--accent-fg)",
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                {initial}
              </span>
            </Field>
            <Field label="Sign out" hint="End your session and return home.">
              <Button
                variant="outline"
                size="sm"
                disabled={logout.isPending}
                onClick={handleLogout}
              >
                {logout.isPending ? "Signing out…" : "Sign out"}
              </Button>
            </Field>
          </Section>

          <Section
            title="Keys & providers"
            description="Credentials live in Langflow's settings. Lothal reads the GitHub token from your global variables; manage API keys there too."
          >
            <Field
              label="Global variables"
              hint="GitHub personal access token and other secrets."
            >
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate("/settings/global-variables")}
              >
                Open
                <ExternalGlyph />
              </Button>
            </Field>
            <Field
              label="API keys"
              hint="Langflow API keys for programmatic access."
            >
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate("/settings/api-keys")}
              >
                Open
                <ExternalGlyph />
              </Button>
            </Field>
          </Section>
        </div>
      </main>
    </div>
  );
}

export default function Settings() {
  return (
    <LothalSurface>
      <SettingsView />
    </LothalSurface>
  );
}
