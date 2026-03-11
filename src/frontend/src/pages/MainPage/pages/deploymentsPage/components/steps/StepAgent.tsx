import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { ChevronDown } from "lucide-react";
import { useState } from "react";

type CheckpointAttachItem = {
  id: string;
  name: string;
  updatedDate: string;
};

type FlowAttachItem = {
  flowId: string;
  flowName: string;
  checkpoints: CheckpointAttachItem[];
};

type StepAgentProps = {
  selectedItems: Set<string>;
  toggleItem: (id: string) => void;
  flows: FlowAttachItem[];
};

type AgentMode = "existing" | "new";

export const StepAgent = ({
  selectedItems,
  toggleItem,
  flows,
}: StepAgentProps) => {
  const [agentMode, setAgentMode] = useState<AgentMode>("existing");
  const selectedAgentId = Array.from(selectedItems)[0] ?? "";

  const handleAgentChange = (flowId: string) => {
    if (selectedAgentId) {
      toggleItem(selectedAgentId);
    }
    if (flowId) {
      toggleItem(flowId);
    }
  };

  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-y-auto py-3">
      <div className="flex flex-col">
        <span className="text-sm font-medium pb-2">
          Choose Agent Mode<span className="text-destructive">*</span>
        </span>

        <RadioGroup
          value={agentMode}
          onValueChange={(v) => setAgentMode(v as AgentMode)}
          className="grid gap-3"
        >
          <label
            htmlFor="mode-existing"
            className={`flex cursor-pointer items-center gap-4 rounded-lg border p-4 transition-colors bg-muted ${agentMode === "existing"
                ? "border-primary"
                : "border-border hover:border-muted-foreground"
              }`}
          >
            <RadioGroupItem value="existing" id="mode-existing" />
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold">Use Existing Agent</span>
              <span className="text-sm text-muted-foreground">
                Select an agent that&apos;s already been created
              </span>
            </div>
          </label>

          <label
            htmlFor="mode-new"
            className={`flex cursor-pointer items-center gap-4 rounded-lg border p-4 transition-colors bg-muted ${agentMode === "new"
                ? "border-primary"
                : "border-border hover:border-muted-foreground"
              }`}
          >
            <RadioGroupItem value="new" id="mode-new" />
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold">Create New Agent</span>
              <span className="text-sm text-muted-foreground">
                Define a new agent with specific settings
              </span>
            </div>
          </label>
        </RadioGroup>
      </div>

      {agentMode === "existing" && (
        <div className="flex flex-col">
          <span className="text-sm font-medium pb-2">
            Choose Agent <span className="text-destructive">*</span>
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-muted px-4 py-2 text-sm text-primary ring-offset-background hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <span
                  className={selectedAgentId ? "" : "text-muted-foreground"}
                >
                  {flows.find((f) => f.flowId === selectedAgentId)?.flowName ??
                    "Select an agent"}
                </span>
                <ChevronDown className="h-4 w-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              className="w-[var(--radix-dropdown-menu-trigger-width)]"
            >
              {flows.map((flow) => (
                <DropdownMenuItem
                  key={flow.flowId}
                  onSelect={() => handleAgentChange(flow.flowId)}
                >
                  {flow.flowName}
                </DropdownMenuItem>
              ))}
              {flows.length === 0 && (
                <DropdownMenuItem disabled>
                  No agents available
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}
    </div>
  );
};
