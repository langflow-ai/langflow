import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { type Dispatch, type SetStateAction, useState } from "react";
import type { EnvVar } from "../../constants";

type StepConfigurationProps = {
  envVars: EnvVar[];
  setEnvVars: Dispatch<SetStateAction<EnvVar[]>>;
  detectedVarCount: number;
  selectedAgentName?: string;
};

export const StepConfiguration = ({
  envVars,
  setEnvVars,
  detectedVarCount,
  selectedAgentName,
}: StepConfigurationProps) => {
  void setEnvVars;
  void detectedVarCount;
  const [useCurrentFlow, setUseCurrentFlow] = useState(true);
  const [selectedConfig, setSelectedConfig] = useState<string>("");

  const configOptions = envVars
    .filter((v) => v.key.trim() !== "")
    .map((v) => v.key);

  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-y-auto py-3">
      {/* Current Flow card */}
      <button
        type="button"
        onClick={() => setUseCurrentFlow(!useCurrentFlow)}
        className={`flex items-center gap-4 rounded-lg border bg-muted p-4 text-left transition-colors ${useCurrentFlow
            ? "border-primary"
            : "border-border hover:border-muted-foreground"
          }`}
      >
        <Checkbox checked={useCurrentFlow} className="pointer-events-none" />
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-semibold">
            {selectedAgentName || "Current Flow"}
          </span>
          <span className="text-sm text-muted-foreground">v1</span>
        </div>
      </button>

      {/* Select Configuration */}
      <div className="flex flex-col">
        <span className="text-sm font-medium pb-2">
          Select Configuration <span className="text-destructive">*</span>
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-muted px-4 py-2 text-sm text-primary ring-offset-background hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <span className={selectedConfig ? "" : "text-muted-foreground"}>
                {selectedConfig || "Select a configuration"}
              </span>
              <ForwardedIconComponent name="ChevronDown" className="h-4 w-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="start"
            className="w-[var(--radix-dropdown-menu-trigger-width)]"
          >
            {configOptions.length > 0 ? (
              configOptions.map((opt) => (
                <DropdownMenuItem
                  key={opt}
                  onSelect={() => setSelectedConfig(opt)}
                >
                  {opt}
                </DropdownMenuItem>
              ))
            ) : (
              <DropdownMenuItem disabled>
                No configurations available
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>

        <p className="text-sm text-muted-foreground pt-2">
          Choose a configuration with environment variables for this flow
        </p>
      </div>

      {/* Warning banner */}
      {/* {!selectedConfig && (
        <div className="flex items-start gap-3 rounded-lg border border-yellow-600/50 bg-yellow-950/30 p-4">
          <ForwardedIconComponent
            name="AlertTriangle"
            className="mt-0.5 h-5 w-5 shrink-0 text-yellow-500"
          />
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-semibold">
              Configuration Required
            </span>
            <span className="text-sm text-muted-foreground">
              Please select a configuration to continue with the deployment.
            </span>
          </div>
        </div>
      )} */}
    </div>
  );
};
