import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import Loading from "@/components/ui/loading";
import { cn } from "@/utils/utils";

type DeploymentPhase = "deploying" | "deployed";

interface StepDeployStatusProps {
  phase: DeploymentPhase;
  deploymentName?: string;
  loadingTitle?: string;
  loadingDescription?: string;
  doneTitle?: string;
  doneDescription?: string;
}

export default function StepDeployStatus({
  phase,
  deploymentName,
  loadingTitle,
  loadingDescription,
  doneTitle,
  doneDescription,
}: StepDeployStatusProps) {
  const { t } = useTranslation();
  const isDeploying = phase === "deploying";

  const resolvedLoadingTitle = loadingTitle ?? t("deployments.deployingTitle");
  const resolvedLoadingDescription =
    loadingDescription ?? t("deployments.deployingDescription");
  const resolvedDoneTitle = doneTitle ?? t("deployments.deploymentSuccessful");
  const resolvedDoneDescription =
    doneDescription ??
    (deploymentName
      ? t("deployments.deploymentLiveNamed", { name: deploymentName })
      : t("deployments.deploymentLive"));

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 py-10">
      <div className="relative flex items-center justify-center">
        <div
          className={cn(
            "flex h-20 w-20 items-center justify-center rounded-full transition-colors duration-500",
            isDeploying ? "bg-accent-indigo/10" : "bg-accent-emerald/10",
          )}
        >
          {isDeploying ? (
            <Loading size={36} className="text-accent-indigo-foreground" />
          ) : (
            <ForwardedIconComponent
              name="CircleCheck"
              className="h-9 w-9 text-accent-emerald animate-in zoom-in-50 duration-300"
            />
          )}
        </div>
        {isDeploying && (
          <div className="absolute h-20 w-20 animate-ping rounded-full bg-accent-indigo/10" />
        )}
      </div>

      <div className="flex flex-col items-center gap-2 text-center">
        <h3 className="text-xl font-semibold">
          {isDeploying ? resolvedLoadingTitle : resolvedDoneTitle}
        </h3>
        <p className="max-w-xs text-sm text-muted-foreground">
          {isDeploying ? resolvedLoadingDescription : resolvedDoneDescription}
        </p>
      </div>

      {isDeploying && (
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent-indigo"
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
