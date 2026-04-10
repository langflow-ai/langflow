import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { Deployment } from "../types";

interface TestDeploymentModal {
  testTarget: { id: string; name: string } | null;
  testProviderId: string;
  open: boolean;
  handleTestDeployment: (deployment: Deployment) => void;
  handleTestFromStepper: (
    deployment: { id: string; name: string },
    providerId: string,
  ) => void;
  close: () => void;
  setOpen: (open: boolean) => void;
}

export function useTestDeploymentModal(): TestDeploymentModal {
  const [testTarget, setTestTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [testProviderId, setTestProviderId] = useState("");

  const location = useLocation();
  const navigate = useNavigate();

  // Auto-open test modal when navigated from canvas deploy button.
  // navigate() replaces state with {}, so the guard prevents re-entry.
  useEffect(() => {
    const state = location.state as {
      testDeployment?: { id: string; name: string };
      testProviderId?: string;
    } | null;
    if (state?.testDeployment && state?.testProviderId) {
      setTestTarget(state.testDeployment);
      setTestProviderId(state.testProviderId);
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, navigate]);

  const handleTestDeployment = useCallback((deployment: Deployment) => {
    setTestTarget(deployment);
    setTestProviderId(deployment.provider_account_id ?? "");
  }, []);

  const handleTestFromStepper = useCallback(
    (deployment: { id: string; name: string }, providerId: string) => {
      setTestTarget(deployment);
      setTestProviderId(providerId);
    },
    [],
  );

  const close = useCallback(() => {
    setTestTarget(null);
    setTestProviderId("");
  }, []);

  const setOpen = useCallback((open: boolean) => {
    if (!open) {
      setTestTarget(null);
      setTestProviderId("");
    }
  }, []);

  return {
    testTarget,
    testProviderId,
    open: !!testTarget,
    handleTestDeployment,
    handleTestFromStepper,
    close,
    setOpen,
  };
}
