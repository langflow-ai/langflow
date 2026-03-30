type DeploymentPhase = "deploying" | "deployed";

interface StepDeployStatusProps {
  phase: DeploymentPhase;
}

export default function StepDeployStatus({ phase }: StepDeployStatusProps) {
  return (
    <div className="flex flex-col gap-6 py-4">
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">Status</span>
        <div className="rounded-md border border-border bg-muted/30 px-4 py-3">
          <div className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${
                phase === "deploying"
                  ? "animate-pulse bg-blue-500"
                  : "bg-green-500"
              }`}
            />
            <span
              className={`text-sm ${
                phase === "deploying" ? "text-blue-500" : "text-green-500"
              }`}
            >
              {phase === "deploying" ? "Deploying..." : "Deployed"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
