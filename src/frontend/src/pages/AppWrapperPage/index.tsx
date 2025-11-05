import { Suspense, lazy } from "react";
import { LoadingPage } from "../LoadingPage";
import { useLocation } from "react-router-dom";
import Landing from "../LandingPage";

const AuthenticatedAppWrapper = lazy(() =>
  import("./components/AuthenticatedAppWrapper").then((module) => ({
    default: module.AuthenticatedAppWrapper,
  })),
);
export function AppWrapperPage() {
  const { pathname } = useLocation();

  // Render the marketing landing page when visitor hits the root route
  // regardless of authentication status
  if (pathname === "/") {
    return <Landing />;
  }

  return (
    <Suspense fallback={<LoadingPage />}>
      <AuthenticatedAppWrapper />
    </Suspense>
  );
}