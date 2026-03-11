import type { DeploymentType, EnvVar } from "../../constants";

type SelectedItem = { name: string };

type StepReviewProps = {
  deploymentType: DeploymentType;
  deploymentName: string;
  deploymentDescription: string;
  selectedItems: SelectedItem[];
  envVars: EnvVar[];
  providerName?: string;
  selectedAgentName?: string;
};

export const StepReview = ({
  deploymentType,
  deploymentName,
  deploymentDescription,
  selectedItems,
  envVars,
  providerName,
  selectedAgentName,
}: StepReviewProps) => {
  void envVars;

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-full flex-col gap-4 rounded-lg border border-border bg-muted p-5">
        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted-foreground">
            Deployment Name
          </span>
          <span className="text-sm font-semibold">
            {deploymentName || "—"}
          </span>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted-foreground">Description</span>
          <span className="text-sm font-semibold">
            {deploymentDescription || "—"}
          </span>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted-foreground">
            Deployment Type
          </span>
          <span className="text-sm font-semibold">
            {deploymentType === "MCP" ? "MCP Server" : deploymentType}
          </span>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted-foreground">Provider</span>
          <span className="text-sm font-semibold">
            {providerName || "—"}
          </span>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted-foreground">Agent</span>
          <span className="text-sm font-semibold">
            {selectedAgentName || "—"}
          </span>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted-foreground">Flows</span>
          {selectedItems.length > 0 ? (
            <ul className="flex flex-col gap-0.5">
              {selectedItems.map(({ name }) => (
                <li key={name} className="text-sm font-semibold">
                  {name}
                </li>
              ))}
            </ul>
          ) : (
            <span className="text-sm font-semibold">—</span>
          )}
        </div>
      </div>
    </div>
  );
};
