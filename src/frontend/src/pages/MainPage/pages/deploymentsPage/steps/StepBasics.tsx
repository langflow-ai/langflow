import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { DeploymentType } from "../constants";

type StepBasicsProps = {
  deploymentName: string;
  setDeploymentName: (v: string) => void;
  deploymentDescription: string;
  setDeploymentDescription: (v: string) => void;
  deploymentType: DeploymentType;
  setDeploymentType: (v: DeploymentType) => void;
};

export const StepBasics = ({
  deploymentName,
  setDeploymentName,
  deploymentDescription,
  setDeploymentDescription,
  deploymentType,
  setDeploymentType,
}: StepBasicsProps) => (
  <div className="flex h-full flex-col gap-5 overflow-y-auto">
    <div>
      <h3 className="text-base font-semibold">Deployment Basics</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Give your deployment a name, description, and choose a deployment type.
      </p>
    </div>
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium">
        Deployment Name <span className="text-destructive">*</span>
      </label>
      <Input
        placeholder="e.g., Production Sales Agent"
        value={deploymentName}
        onChange={(e) => setDeploymentName(e.target.value)}
      />
    </div>
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium">Description</label>
      <Textarea
        placeholder="Describe what this deployment does..."
        value={deploymentDescription}
        onChange={(e) => setDeploymentDescription(e.target.value)}
        rows={6}
        className="resize-none placeholder:text-placeholder-foreground"
      />
    </div>
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <label className="text-sm font-medium">
        Deployment Type <span className="text-destructive">*</span>
      </label>
      <div className="grid h-full grid-cols-2 gap-3">
        {(
          [
            {
              type: "Agent" as DeploymentType,
              label: "Agent",
              icon: "Bot",
              description:
                "Conversational agent with chat interface and tool calling",
            },
            {
              type: "MCP" as DeploymentType,
              label: "MCP Server",
              icon: "Mcp",
              description: "Model Context Protocol server for tool integration",
            },
          ] as const
        ).map(({ type, label, icon, description }) => (
          <button
            key={type}
            onClick={() => setDeploymentType(type)}
            className={`flex h-full flex-col gap-3 rounded-xl border p-4 text-left transition-colors ${
              deploymentType === type
                ? "border-primary bg-background"
                : "border-border hover:border-muted-foreground"
            }`}
          >
            <div
              className={`flex h-9 w-9 items-center justify-center rounded-md ${
                deploymentType === type ? "bg-primary/10" : "bg-muted"
              }`}
            >
              <ForwardedIconComponent
                name={icon}
                className={`h-5 w-5 ${
                  deploymentType === type
                    ? "text-primary"
                    : "text-muted-foreground"
                }`}
              />
            </div>
            <p className="text-sm font-semibold">{label}</p>
            <p className="text-xs text-muted-foreground">{description}</p>
          </button>
        ))}
      </div>
    </div>
  </div>
);
