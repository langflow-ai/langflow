import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import type { DeploymentType } from "../../constants";

type ProviderOption = {
  key: string;
  label: string;
  icon: string;
};

const PROVIDERS: ProviderOption[] = [
  { key: "watsonx", label: "watsonx Orchestrate", icon: "Bot" },
  { key: "aws", label: "AWS Lambda", icon: "Box" },
  { key: "azure", label: "Azure Functions", icon: "CircleDot" },
  { key: "gcp", label: "Google Cloud Run", icon: "Cloud" },
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
    <div className="flex h-full w-full flex-col gap-6 overflow-y-auto">
      {/* Provider selection */}
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">
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
                className={`flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors ${
                  isSelected
                    ? "border-2 border-foreground"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <ForwardedIconComponent
                  name={provider.icon}
                  className={`h-8 w-8 ${
                    isSelected ? "text-foreground" : "text-muted-foreground"
                  }`}
                />
                <span className="text-sm font-medium">{provider.label}</span>
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-muted-foreground" />
                  Not connected
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Credentials description */}
      <p className="text-sm text-muted-foreground">
        Configure your {activeProvider?.label ?? "provider"} credentials below.
        Sign in or sign up to{" "}
        <span className="font-semibold text-foreground">
          find your credentials
        </span>
        .
      </p>

      {/* API Key */}
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">
          API Key <span className="text-destructive">*</span>
        </span>
        <Input
          type="password"
          placeholder="Enter your API key"
          value={deploymentName}
          onChange={(e) => setDeploymentName(e.target.value)}
        />
      </div>

      {/* Service Instance URL */}
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">
          Service Instance URL <span className="text-destructive">*</span>
        </span>
        <Input
          placeholder="https://api.example.com"
          value={deploymentDescription}
          onChange={(e) => setDeploymentDescription(e.target.value)}
        />
      </div>
    </div>
  );
};
