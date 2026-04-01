import Loading from "@/components/ui/loading";
import { cn } from "@/utils/utils";

type DeploymentPhase = "deploying" | "deployed";

interface StepDeployStatusProps {
  phase: DeploymentPhase;
  deploymentName?: string;
  isEditMode?: boolean;
}

export default function StepDeployStatus({
  phase,
  deploymentName,
  isEditMode,
}: StepDeployStatusProps) {
  const isDeploying = phase === "deploying";

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 py-10">
      {/* Icon area */}
      <div className="relative flex items-center justify-center">
        <div
          className={cn(
            "flex h-20 w-20 items-center justify-center rounded-full transition-colors duration-500",
            isDeploying ? "bg-blue-500/10" : "bg-accent-emerald/10",
          )}
        >
          {isDeploying ? (
            <Loading size={36} className="text-blue-500" />
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width={36}
              height={36}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-accent-emerald animate-in zoom-in-50 duration-300"
            >
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          )}
        </div>
        {/* Outer ring pulse when deploying */}
        {isDeploying && (
          <div className="absolute h-20 w-20 animate-ping rounded-full bg-blue-500/10" />
        )}
      </div>

      {/* Text */}
      <div className="flex flex-col items-center gap-2 text-center">
        <h3 className="text-xl font-semibold">
          {isDeploying
            ? isEditMode
              ? "Updating…"
              : "Deploying…"
            : isEditMode
              ? "Update successful"
              : "Deployment successful"}
        </h3>
        <p className="max-w-xs text-sm text-muted-foreground">
          {isDeploying
            ? isEditMode
              ? "Your deployment is being updated. This usually takes a few seconds."
              : "Your deployment is being provisioned. This usually takes a few seconds."
            : isEditMode
              ? deploymentName
                ? `"${deploymentName}" has been updated.`
                : "Your deployment has been updated."
              : deploymentName
                ? `"${deploymentName}" is live and ready to use.`
                : "Your deployment is live and ready to use."}
        </p>
      </div>

      {/* Progress dots when deploying */}
      {isDeploying && (
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-1.5 w-1.5 animate-bounce rounded-full bg-blue-500"
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
