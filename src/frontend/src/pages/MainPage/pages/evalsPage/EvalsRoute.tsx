import type { ReactNode } from "react";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import { useUtilityStore } from "@/stores/utilityStore";

/** Evals pages exist only when the server enables the feature flag. */
export default function EvalsRoute({ children }: { children: ReactNode }) {
  const enabled = useUtilityStore((state) => state.featureFlags.evals === true);
  return enabled ? children : <CustomNavigate replace to="/flows" />;
}
