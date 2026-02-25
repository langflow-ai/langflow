import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

type DeploymentCreationState = "creating" | "success" | "error";

type DeploymentCreationStatusViewProps = {
  state: DeploymentCreationState;
  deploymentName: string;
  deploymentType: "agent" | "mcp" | null;
  onBack: () => void;
  onPrimaryAction?: () => void;
};

const getPrimaryActionLabel = (deploymentType: "agent" | "mcp" | null) => {
  if (deploymentType === "agent") {
    return "Test Agent";
  }
  if (deploymentType === "mcp") {
    return "Test MCP Server";
  }
  return null;
};

export const DeploymentCreationStatusView = ({
  state,
  deploymentName,
  deploymentType,
  onBack,
  onPrimaryAction,
}: DeploymentCreationStatusViewProps) => {
  const primaryActionLabel = getPrimaryActionLabel(deploymentType);

  return (
    <div className="flex h-full items-center justify-center rounded-xl border bg-muted/20 p-6">
      <div className="w-full max-w-2xl rounded-xl border bg-background p-8 shadow-sm">
        <div className="flex flex-col items-center text-center">
          <div className="relative mb-4">
            <div
              className={
                state === "creating"
                  ? "h-14 w-14 rounded-full border-2 border-primary/20 border-t-primary animate-spin"
                  : "hidden"
              }
            />
            {state !== "creating" && (
              <div
                className={`flex h-14 w-14 items-center justify-center rounded-full ${
                  state === "success"
                    ? "bg-primary/10 text-primary"
                    : "bg-destructive/10 text-destructive"
                }`}
              >
                <ForwardedIconComponent
                  name={state === "success" ? "Check" : "CircleAlert"}
                  className="h-6 w-6"
                />
              </div>
            )}
          </div>

          <h2 className="text-xl font-semibold">
            {state === "creating" && "Creating Deployment"}
            {state === "success" && "Deployment Ready"}
            {state === "error" && "Deployment Failed"}
          </h2>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            {state === "creating" &&
              `Setting up "${deploymentName}" and preparing runtime configuration.`}
            {state === "success" &&
              `Deployment "${deploymentName}" was created successfully.`}
            {state === "error" &&
              "We could not create this deployment. Review your provider credentials and configuration, then try again."}
          </p>

          {state === "creating" && (
            <div className="mt-6 flex w-full max-w-lg flex-col gap-2">
              <div className="h-2 rounded-full bg-muted">
                <div className="h-2 w-2/3 animate-pulse rounded-full bg-primary/70" />
              </div>
              <div className="h-2 rounded-full bg-muted">
                <div className="h-2 w-1/2 animate-pulse rounded-full bg-primary/50" />
              </div>
            </div>
          )}

          <div className="mt-8 flex items-center gap-3">
            <Button variant="outline" onClick={onBack}>
              Back to Deployments
            </Button>
            {state === "success" && primaryActionLabel && onPrimaryAction && (
              <Button onClick={onPrimaryAction}>{primaryActionLabel}</Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
