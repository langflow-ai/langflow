// Lothal signup page (Epic B.9) — the Lothal-branded account creation that
// replaces Langflow's default signup at "/signup". The login page funnels new
// visitors here via its "Create an account" link, carrying any ?redirect along.
// Account creation does not log the user in, so on success we send them to
// "/login" (preserving ?redirect) where signing in carries them to their
// destination — mirroring B.8's LoginPage.

import { type CSSProperties, type ReactNode, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAddUser } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAlertStore from "@/stores/alertStore";
import type { UserInputType } from "@/types/components";
import { Button, LothalMark } from "../components";
import { LothalSurface } from "../theme/LothalSurface";

// Inputs mirror LoginPage's focus treatment: a border that warms to the accent.
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

/** The account-creation card; assumes a surrounding LothalSurface for tokens. */
function SignUpView() {
  // Capture the redirect once so both the success hop to "/login" and the
  // "Sign in" link can carry it along.
  const [searchParams] = useSearchParams();
  const [redirect] = useState(() => searchParams.get("redirect"));

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const navigate = useCustomNavigate();
  const { mutate } = useAddUser();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const loginHref = redirect
    ? `/login?redirect=${encodeURIComponent(redirect)}`
    : "/login";

  // Match passwords once both have been typed; surfaced inline below the field.
  const [passwordsMatch, setPasswordsMatch] = useState(true);
  useEffect(() => {
    setPasswordsMatch(confirmPassword === "" || password === confirmPassword);
  }, [password, confirmPassword]);

  const canSubmit =
    username.trim() !== "" &&
    password.trim() !== "" &&
    confirmPassword.trim() !== "" &&
    password.trim() === confirmPassword.trim();

  function signUp() {
    const newUser: UserInputType = {
      username: username.trim(),
      password: password.trim(),
    };
    mutate(newUser, {
      onSuccess: (user) => {
        track("User Signed Up", user);
        setSuccessData({
          title: "Account created — sign in to continue.",
        });
        navigate(loginHref);
      },
      onError: (error) => {
        setErrorData({
          title: "Sign up failed",
          list: [
            error?.response?.data?.detail ?? "Could not create your account.",
          ],
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
      {/* Ambient aubergine glow, matching the landing and login. */}
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
          if (!canSubmit) return;
          signUp();
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
            Create your account
          </h1>
          <p style={{ fontSize: 13.5, color: "var(--ink-mute)", margin: 0 }}>
            Join Lothal to start building.
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
              placeholder="Choose a username"
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
                autoComplete="new-password"
                placeholder="Create a password"
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

          <Field label="Confirm password">
            <input
              name="confirmPassword"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              placeholder="Re-enter your password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              onFocus={focusAccent}
              onBlur={blurBorder}
              required
              style={FIELD_STYLE}
            />
            {!passwordsMatch && (
              <span style={{ color: "#e5484d", fontSize: 12 }} role="alert">
                Passwords don't match.
              </span>
            )}
          </Field>
        </div>

        <Button
          variant="accent"
          size="lg"
          type="submit"
          disabled={!canSubmit}
          style={{ width: "100%", justifyContent: "center", marginTop: 2 }}
        >
          Create account
        </Button>

        <p style={{ fontSize: 13, color: "var(--ink-mute)", margin: 0 }}>
          Already have an account?{" "}
          <CustomLink
            to={loginHref}
            style={{ color: "var(--accent)", fontWeight: 500 }}
          >
            Sign in
          </CustomLink>
        </p>
      </form>
    </div>
  );
}

/** Lothal account creation at "/signup" — Lothal theme, dark by default. */
export default function SignUpPage() {
  return (
    <LothalSurface style={{ minHeight: "100vh" }}>
      <SignUpView />
    </LothalSurface>
  );
}
