import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { LANDING_BASENAME } from "./landingRoutes";
import { useCookies } from "react-cookie";
import {
  ACTIVE_ORG_STORAGE_KEY,
  hasWorkspaceSession,
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_REFRESH_TOKEN,
} from "./session";

export default function DashboardPage() {
  const navigate = useNavigate();
  const [cookies] = useCookies([LANGFLOW_ACCESS_TOKEN, LANGFLOW_REFRESH_TOKEN]);

  // Validate minimal session
  useEffect(() => {
    if (!hasWorkspaceSession(cookies)) {
      // Missing session → go to login
      console.log("[DashboardPage] Missing session, redirecting to", `${LANDING_BASENAME}/login`);
      navigate("/login", { replace: true });
    }
  }, [cookies, navigate]);

  const goToFlows = () => {
    // Main app flow route lives outside the /new/landingpage basename
    console.log("[DashboardPage] Navigating to /flows");
    window.location.assign("/flows");
  };

  return (
    <div
      style={{
        display: "grid",
        placeItems: "center",
        minHeight: "100vh",
        backgroundColor: "#f8fafc",
        padding: "2rem",
      }}
    >
      <div
        style={{
          background: "#ffffff",
          padding: "2rem",
          borderRadius: "1rem",
          maxWidth: "480px",
          width: "100%",
          boxShadow: "0 8px 28px rgba(15, 23, 42, 0.06)",
          textAlign: "center",
        }}
      >
        <h1
          style={{
            fontSize: "1.5rem",
            fontWeight: 700,
            marginBottom: "1rem",
            background: "linear-gradient(90deg, #4f46e5 0%, #38bdf8 80%)",
            WebkitBackgroundClip: "text",
            color: "transparent",
          }}
        >
          Workspace Ready
        </h1>

        <p
          style={{
            color: "#475569",
            lineHeight: "1.5",
            marginBottom: "1.5rem",
          }}
        >
          Your organization is ready to use. Continue to your Langflow workspace
          to start building.
        </p>

        <button
          onClick={goToFlows}
          style={{
            width: "100%",
            background: "linear-gradient(90deg, #4f46e5 0%, #38bdf8 80%)",
            color: "#fff",
            padding: "0.75rem 1rem",
            border: "none",
            borderRadius: "0.75rem",
            fontSize: "1rem",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Continue to Flows
        </button>
      </div>
    </div>
  );
}