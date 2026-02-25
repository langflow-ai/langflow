import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { DeploymentType, EnvVar } from "../constants";
type SelectedItem = { name: string };

type StepReviewProps = {
  deploymentType: DeploymentType;
  deploymentName: string;
  deploymentDescription: string;
  selectedItems: SelectedItem[];
  envVars: EnvVar[];
};

export const StepReview = ({
  deploymentType,
  deploymentName,
  deploymentDescription,
  selectedItems,
  envVars,
}: StepReviewProps) => {
  const configuredEnvVars = envVars.filter(
    ({ key, value }) => key.trim() !== "" || value.trim() !== "",
  );

  const getObfuscatedValue = (value: string): string =>
    value.trim() ? "********" : "Not set";

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto">
      <div>
        <h3 className="text-base font-semibold">Review & Confirm</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Review your deployment details before creating.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex h-full flex-col rounded-lg bg-muted/40 p-4">
          <p className="mb-3 text-md font-semibold text-primary">Deployment</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
            <dt className="text-muted-foreground">Type</dt>
            <dd className="flex items-center gap-1.5 font-medium">
              <ForwardedIconComponent
                name={deploymentType === "MCP" ? "Mcp" : "Bot"}
                className="h-3.5 w-3.5 text-muted-foreground"
              />
              {deploymentType === "MCP" ? "MCP Server" : deploymentType}
            </dd>
            <dt className="text-muted-foreground">Name</dt>
            <dd className="truncate font-medium">{deploymentName}</dd>
          </dl>
          {deploymentDescription && (
            <div className="mt-2 flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Description</span>
              <p
                className="line-clamp-2 font-medium"
                title={deploymentDescription}
              >
                {deploymentDescription}
              </p>
            </div>
          )}
        </div>
        <div className="rounded-lg bg-muted/40 p-4">
          <p className="mb-3 text-md font-semibold text-primary">
            Attached Flows
          </p>
          {selectedItems.length > 0 ? (
            <ul className="flex flex-col gap-1">
              {selectedItems.map(({ name }) => (
                <li key={name} className="flex items-center gap-2 text-sm">
                  <ForwardedIconComponent
                    name="Workflow"
                    className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                  />
                  <span className="font-medium">{name}</span>
                </li>
              ))}
            </ul>
          ) : (
            <span className="text-sm text-muted-foreground italic">
              None selected
            </span>
          )}
        </div>
      </div>
      <div className="flex-1 rounded-lg bg-muted/40 p-4">
        <p className="mb-3 text-md font-semibold text-primary">Configuration</p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-muted-foreground">Env Variables</dt>
          <dd className="font-medium">
            {configuredEnvVars.length > 0 ? (
              `${configuredEnvVars.length} variable${configuredEnvVars.length > 1 ? "s" : ""}`
            ) : (
              <span className="italic text-muted-foreground">None</span>
            )}
          </dd>
        </dl>
        {configuredEnvVars.length > 0 && (
          <div className="mt-3 max-h-52 space-y-2 overflow-y-auto rounded-md border border-border/70 bg-background/50 p-2">
            {configuredEnvVars.map(({ key, value }, index) => (
              <div
                key={`${key || "env"}-${index}`}
                className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 rounded-sm bg-muted/30 px-2 py-1.5 text-sm"
              >
                <span
                  className="truncate font-medium"
                  title={key || "Unnamed variable"}
                >
                  {key || "Unnamed variable"}
                </span>
                <span className="text-muted-foreground">=</span>
                <span className="truncate text-right font-mono text-muted-foreground">
                  {getObfuscatedValue(value)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
