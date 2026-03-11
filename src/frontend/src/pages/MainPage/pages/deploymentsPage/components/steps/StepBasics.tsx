import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { DeploymentType } from "../../constants";

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
  <div className="flex h-full w-full flex-col gap-6 overflow-y-auto py-3">
    <div className="flex flex-col">
      <span className="text-sm font-medium pb-2">
        Name Deployment <span className="text-destructive">*</span>
      </span>
      <Input
        placeholder="e.g., Production Sales Agent"
        className="bg-muted"
        value={deploymentName}
        onChange={(e) => setDeploymentName(e.target.value)}
      />
    </div>
    <div className="flex flex-col">
      <span className="text-sm font-medium pb-2">Description</span>
      <Textarea
        placeholder="Describe what this deployment does..."
        value={deploymentDescription}
        onChange={(e) => setDeploymentDescription(e.target.value)}
        rows={3}
        className="resize-none placeholder:text-placeholder-foreground bg-muted"
      />
    </div>
    <div className="flex min-h-0 flex-1 flex-col">
      <span className="text-sm font-medium pb-2">
        Deployment Type <span className="text-destructive">*</span>
      </span>
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
            type="button"
            onClick={() => setDeploymentType(type)}
            className={`rounded-lg border p-4 bg-muted transition-colors ${
              deploymentType === type
                ? "border-2 border-foreground"
                : "border-border hover:border-muted-foreground"
            }`}
          >
            <div className="flex flex-col h-full">
              <div className="flex flex-row justify-start items-center mb-3">
                <div className="flex-shrink-0 border bg-muted-foreground/10 rounded-lg p-2 mr-3">
                  <ForwardedIconComponent
                    name={icon}
                    className={`h-6 w-6 ${
                      deploymentType === type
                        ? "text-foreground"
                        : "text-muted-foreground"
                    }`}
                  />
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-medium">{label}</span>
                </div>
              </div>
              <p className="text-sm text-muted-foreground text-left">
                {description}
              </p>
            </div>
          </button>
        ))}
      </div>
    </div>
  </div>
);
