import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import type { DeploymentType } from "../../constants";

type ProviderOption = {
  key: string;
  label: string;
  tool: string;
  icon: string;
};

const PROVIDERS: ProviderOption[] = [
  {
    key: "watsonx",
    label: "Watsonx",
    tool: "Orchestrate",
    icon: "WatsonxOrchestrate",
  },
  { key: "aws", label: "AWS", tool: "Lambda", icon: "AWS" },
  { key: "azure", label: "Azure", tool: "Functions", icon: "Azure" },
  { key: "gcp", label: "Google", tool: "Cloud Run", icon: "Google" },
];

type StepProviderProps = {
  deploymentName: string;
  setDeploymentName: (v: string) => void;
  deploymentDescription: string;
  setDeploymentDescription: (v: string) => void;
  deploymentType: DeploymentType;
  setDeploymentType: (v: DeploymentType) => void;
};

export const StepProvider = ({
  deploymentName,
  setDeploymentName,
  deploymentDescription,
  setDeploymentDescription,
}: StepProviderProps) => {
  const [selectedProvider, setSelectedProvider] = useState<string>(
    PROVIDERS[0].key,
  );

  const activeProvider = PROVIDERS.find((p) => p.key === selectedProvider);

  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-y-auto py-3">
      {/* Provider selection */}
      <div className="flex flex-col">
        <span className="text-sm font-medium pb-2">
          Choose Provider <span className="text-destructive">*</span>
        </span>
        <div className="grid grid-cols-4 gap-3">
          {PROVIDERS.map((provider) => {
            const isSelected = selectedProvider === provider.key;
            return (
              <button
                key={provider.key}
                type="button"
                onClick={() => setSelectedProvider(provider.key)}
                className={`rounded-lg border p-3 bg-muted transition-colors h-[100px] ${
                  isSelected
                    ? "border-2 border-foreground"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <div className="h-full flex flex-col justify-between">
                  <div className="flex flex-row gap-3 justify-start items-center">
                    <ForwardedIconComponent
                      name={provider.icon}
                      className={`h-8 w-8 ${
                        isSelected ? "text-foreground" : "text-muted-foreground"
                      }`}
                    />
                    <div className="flex flex-col my-1 text-left">
                      <span className="text-sm font-medium">
                        {provider.label}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {provider.tool}
                      </span>
                    </div>
                  </div>

                  <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-muted-foreground" />
                    Not connected
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Credentials description */}
      <p className="text-sm text-muted-foreground">
        Configure your provider credentials below. Sign in or sign up to{" "}
        <span className="font-semibold text-foreground">
          find your credentials
        </span>
        .
      </p>

      {/* API Key */}
      <div className="flex flex-col ">
        <span className="text-sm font-medium pb-2">
          API Key <span className="text-destructive">*</span>
        </span>
        <Input
          type="password"
          placeholder="Enter your API key"
          className="bg-muted"
          value={deploymentName}
          onChange={(e) => setDeploymentName(e.target.value)}
        />
      </div>

      {/* Service Instance URL */}
      <div className="flex flex-col ">
        <span className="text-sm font-medium pb-2">
          Service Instance URL <span className="text-destructive">*</span>
        </span>
        <Input
          placeholder="https://api.example.com"
          value={deploymentDescription}
          className="bg-muted"
          onChange={(e) => setDeploymentDescription(e.target.value)}
        />
      </div>
    </div>
  );
};
