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
  loadingTitle = "Deploying...",
  loadingDescription = "Your deployment is being provisioned. This usually takes a few seconds.",
  doneTitle = "Deployment successful",
  doneDescription,
}: StepDeployStatusProps) {
  const isDeploying = phase === "deploying";

  const resolvedDoneDescription =
    doneDescription ??
    (deploymentName
      ? `"${deploymentName}" is live and ready to use.`
      : "Your deployment is live and ready to use.");

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
          {isDeploying ? loadingTitle : doneTitle}
        </h3>
        <p className="max-w-xs text-sm text-muted-foreground">
          {isDeploying ? loadingDescription : resolvedDoneDescription}
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
