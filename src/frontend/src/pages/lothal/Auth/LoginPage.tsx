// Lothal login page (Epic B.8) — the Lothal-branded sign-in that replaces
// Langflow's default login at "/login". The landing CTA funnels anonymous
// visitors here via "/login?redirect=/lothal"; on success the redirect param
// (stashed by useSanitizeRedirectUrl) carries them on to the dashboard, while
// a plain sign-in with no redirect lands on "/flows" (see ProtectedLoginRoute).

import { useQueryClient } from "@tanstack/react-query";
import {
  type CSSProperties,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import { useSearchParams } from "react-router-dom";
import { AuthContext } from "@/contexts/authContext";
import { useLoginUser } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
import {
  setRedirectUrl,
  useSanitizeRedirectUrl,
} from "@/hooks/use-sanitize-redirect-url";
import useAlertStore from "@/stores/alertStore";
import type { LoginType } from "@/types/api";
import { Button, LothalMark } from "../components";
import { LothalSurface } from "../theme/LothalSurface";

// Inputs mirror the focus treatment from Dashboard's NewProjectModal: a
// border that warms to the accent on focus.
const FIELD_STYLE: CSSProperties = {
  width: "100%",
  height: 40,
  padding: "0 12px",
  background: "var(--surface)",
  color: "var(--ink)",
  border: "1px solid var(--border-strong)",
  borderRadius: 8,
  fontFamily: "var(--sans)",
  fontSize: 14,
  outline: "none",
  boxSizing: "border-box",
};

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
        width: "100%",
      }}
    >
      <span className="label" style={{ color: "var(--ink-mute)" }}>
        {label}
      </span>
      {children}
    </label>
  );
}

/** The sign-in card; assumes a surrounding LothalSurface for theme tokens. */
function LoginView() {
  // Capture the redirect once on first render, before useSanitizeRedirectUrl's
  // effect strips it from the URL — so the "/signup" link can carry it along.
  const [searchParams] = useSearchParams();
  const [redirect] = useState(() => searchParams.get("redirect"));

  useSanitizeRedirectUrl();

  // Lothal's home is the projects page. With no explicit ?redirect, default the
  // post-login destination to /lothal (the auth guard otherwise falls back to
  // Langflow's /flows). An explicit redirect — e.g. the landing CTA's
  // ?redirect=/lothal — is left untouched, having been stashed above.
  useEffect(() => {
    if (!redirect) setRedirectUrl("/lothal");
  }, [redirect]);

  const { login, clearAuthSession } = useContext(AuthContext);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const queryClient = useQueryClient();
  const { mutate } = useLoginUser();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const signupHref = redirect
    ? `/signup?redirect=${encodeURIComponent(redirect)}`
    : "/signup";

  function signIn() {
    const user: LoginType = {
      username: username.trim(),
      password: password.trim(),
    };
    mutate(user, {
      onSuccess: (data) => {
        clearAuthSession();
        login(data.access_token, "login", data.refresh_token);
        queryClient.clear();
      },
      onError: (error) => {
        setErrorData({
          title: "Sign in failed",
          list: [error?.response?.data?.detail ?? "Could not sign you in."],
        });
      },
    });
  }

  const focusAccent = (e: React.FocusEvent<HTMLInputElement>) => {
    e.currentTarget.style.borderColor = "var(--accent)";
  };
  const blurBorder = (e: React.FocusEvent<HTMLInputElement>) => {
    e.currentTarget.style.borderColor = "var(--border-strong)";
  };

  return (
    <div
      style={{
        position: "relative",
        minHeight: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "48px 24px",
        boxSizing: "border-box",
      }}
    >
      {/* Ambient aubergine glow, matching the landing. */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          zIndex: 0,
          background:
            "radial-gradient(620px 380px at 50% -8%, var(--accent-soft), transparent 62%)",
        }}
      />

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!username.trim() || !password.trim()) return;
          signIn();
        }}
        style={{
          position: "relative",
          zIndex: 1,
          width: "100%",
          maxWidth: 388,
          background: "var(--paper)",
          border: "1px solid var(--border-strong)",
          borderRadius: "var(--radius-lg)",
          padding: 32,
          boxShadow: "0 18px 50px rgba(0, 0, 0, 0.35)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 18,
        }}
      >
        <span style={{ color: "var(--accent)" }}>
          <LothalMark size={34} />
        </span>
        <div
          style={{
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          <h1
            className="serif"
            style={{
              fontSize: 28,
              lineHeight: 1.1,
              letterSpacing: "-0.01em",
              color: "var(--ink)",
              margin: 0,
            }}
          >
            Welcome back
          </h1>
          <p style={{ fontSize: 13.5, color: "var(--ink-mute)", margin: 0 }}>
            Sign in to continue building.
          </p>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 14,
            width: "100%",
            marginTop: 4,
          }}
        >
          <Field label="Username">
            <input
              name="username"
              type="text"
              autoComplete="username"
              placeholder="Your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onFocus={focusAccent}
              onBlur={blurBorder}
              required
              style={FIELD_STYLE}
            />
          </Field>

          <Field label="Password">
            <div style={{ position: "relative", width: "100%" }}>
              <input
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={focusAccent}
                onBlur={blurBorder}
                required
                style={{ ...FIELD_STYLE, paddingRight: 52 }}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                style={{
                  position: "absolute",
                  right: 8,
                  top: "50%",
                  transform: "translateY(-50%)",
                  border: "none",
                  background: "transparent",
                  color: "var(--ink-soft)",
                  fontFamily: "var(--sans)",
                  fontSize: 11.5,
                  cursor: "pointer",
                  padding: "4px 6px",
                }}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </Field>
        </div>

        <Button
          variant="accent"
          size="lg"
          type="submit"
          style={{ width: "100%", justifyContent: "center", marginTop: 2 }}
        >
          Sign in
        </Button>

        <p style={{ fontSize: 13, color: "var(--ink-mute)", margin: 0 }}>
          New to Lothal?{" "}
          <CustomLink
            to={signupHref}
            style={{ color: "var(--accent)", fontWeight: 500 }}
          >
            Create an account
          </CustomLink>
        </p>
      </form>
    </div>
  );
}

/** Lothal sign-in at "/login" — Lothal theme, dark by default. */
export default function LoginPage() {
  return (
    <LothalSurface style={{ minHeight: "100vh" }}>
      <LoginView />
    </LothalSurface>
  );
}
