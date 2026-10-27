import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import Loading from "@/components/ui/loading";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import { useUtilityStore } from "@/stores/utilityStore";

/** Evals pages exist only when the server enables the feature flag. */
export default function EvalsRoute({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  // Undefined until the server's flags arrive, which is after the first render when the page is opened by its address.
  const enabled = useUtilityStore((state) => state.featureFlags.evals);
  if (enabled === undefined)
    return <Loading aria-label={t("common.loading")} />;
  return enabled === true ? children : <CustomNavigate replace to="/flows" />;
}
