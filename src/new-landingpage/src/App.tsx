import { useAuth } from "@clerk/clerk-react";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import { LANDING_BASENAME } from "./landingRoutes";
import NewLandingPageLogin from "./NewLandingPageLogin";
import OrganizationOnboarding from "./OrganizationOnboarding";
import "./App.css";
import DashboardPage from "./DashboardPage";
import { useCookies } from "react-cookie";
import {
  hasWorkspaceSession,
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_REFRESH_TOKEN,
} from "./session";

const features = [
  "Visual builder for complex AI flows",
  "One-click deployment",
  "Extensible component catalog",
  "Bring your own keys and data",
];

function LandingHero() {
  return (
    <main className="hero">
      <section>
        <p className="eyebrow">Introducing</p>
        <h1>Langflow Landing Page</h1>
        <p className="description">
          This lightweight Vite application is served from <code>/new/landingpage</code> and helps demonstrate how nginx can multiplex
          between Langflow and standalone marketing pages inside a single container image.
        </p>
        <div className="cta-row">
          <Link className="cta" to="/login">
            Log in
          </Link>
          <a className="secondary" href="https://github.com/langflow-ai/langflow" target="_blank" rel="noreferrer">
            Visit GitHub
          </a>
          <a className="secondary" href="https://docs.langflow.org" target="_blank" rel="noreferrer">
            Explore Docs
          </a>
        </div>
      </section>
      <section className="feature-card">
        <h2>Why Langflow?</h2>
        <ul>
          {features.map((feature) => (
            <li key={feature}>{feature}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}

function RootRoute() {
  const { isSignedIn } = useAuth();
  const [cookies] = useCookies([LANGFLOW_ACCESS_TOKEN, LANGFLOW_REFRESH_TOKEN]);

  console.log("[App] RootRoute render", { isSignedIn });

  if (isSignedIn) {
    const workspaceReady = hasWorkspaceSession(cookies);
    const destination = workspaceReady ? "/dashboard" : "/organization";

    console.log("[App] Redirecting signed-in user from root", {
      workspaceReady,
      destination,
    });

    return <Navigate to={destination} replace />;
  }

  return <LandingHero />;
}

export default function App() {
  console.log(`[App] App mounted with basename ${LANDING_BASENAME}`);

  return (
    <BrowserRouter basename={LANDING_BASENAME}>
      <Routes>
        <Route path="/" element={<RootRoute />} />
        <Route path="/login" element={<NewLandingPageLogin />} />
        <Route path="/organization" element={<OrganizationOnboarding />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}