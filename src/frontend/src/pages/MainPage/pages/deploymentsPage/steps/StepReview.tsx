import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type {
  ConfigMode,
  DeploymentType,
  KeyFormat,
  VariableScope,
} from "../constants";

type EnvVar = { key: string; value: string };
type SelectedItem = { name: string; kind: "Flow" | "Snapshot" };

type StepReviewProps = {
  deploymentType: DeploymentType;
  deploymentName: string;
  deploymentDescription: string;
  selectedItems: SelectedItem[];
  configMode: ConfigMode;
  configName: string;
  keyFormat: KeyFormat;
  envVars: EnvVar[];
  variableScope: VariableScope;
};

export const StepReview = ({
  deploymentType,
  deploymentName,
  deploymentDescription,
  selectedItems,
  configMode,
  configName,
  keyFormat,
  envVars,
  variableScope,
}: StepReviewProps) => {
  const configModeLabel = {
    reuse: "Reuse existing Config",
    create: "Create new Config",
    modify: "Modify selected Config",
  }[configMode];

  const keyFormatLabel = {
    assisted: "Assisted Prefix",
    auto: "Auto-Prefix",
    manual: "Manual",
  }[keyFormat];

  const scopeLabel =
    variableScope === "coarse"
      ? "Coarse (Shared Config)"
      : "Granular (Per-Flow Config)";

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto">
      <div>
        <h3 className="text-base font-semibold">Review & Confirm</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Review your deployment details before creating.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex h-full flex-col rounded-lg border border-border bg-background p-4">
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
        <div className="rounded-lg border border-border bg-background p-4">
          <p className="mb-3 text-md font-semibold text-primary">
            Attached Items
          </p>
          {selectedItems.length > 0 ? (
            <ul className="flex flex-col gap-1">
              {selectedItems.map(({ name, kind }) => (
                <li key={name} className="flex items-center gap-2 text-sm">
                  <ForwardedIconComponent
                    name={kind === "Flow" ? "Workflow" : "Camera"}
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
      <div className="flex-1 rounded-lg border border-border bg-background p-4">
        <p className="mb-3 text-md font-semibold text-primary">Configuration</p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-muted-foreground">Mode</dt>
          <dd className="font-medium">{configModeLabel}</dd>
          <dt className="text-muted-foreground">Config Name</dt>
          <dd className="font-mono font-medium">{configName}</dd>
          <dt className="text-muted-foreground">Key Format</dt>
          <dd className="font-medium">{keyFormatLabel}</dd>
          <dt className="text-muted-foreground">Env Variables</dt>
          <dd className="font-medium">
            {envVars.length > 0 ? (
              `${envVars.length} variable${envVars.length > 1 ? "s" : ""}`
            ) : (
              <span className="italic text-muted-foreground">None</span>
            )}
          </dd>
          <dt className="text-muted-foreground">Variable Scope</dt>
          <dd className="font-medium">{scopeLabel}</dd>
        </dl>
      </div>
    </div>
  );
};
