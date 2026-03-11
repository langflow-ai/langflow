import type { ReactNode } from "react";
import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";

export type StepProviderOption = {
  key: string;
  label: string;
  tool?: string;
  icon?: string;
  iconNode?: ReactNode;
  requiresAccountId?: boolean;
};

const DEFAULT_PROVIDERS: StepProviderOption[] = [
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

export type StepProviderValue = {
  selectedProvider?: string;
  apiKey: string;
  serviceUrl: string;
  accountId?: string;
};

export type StepProviderChangeHandlers = {
  setSelectedProvider?: (value: string) => void;
  setApiKey: (value: string) => void;
  setServiceUrl: (value: string) => void;
  setAccountId?: (value: string) => void;
};

export type StepProviderConfig = {
  providerOptions?: StepProviderOption[];
  providerLabel?: string;
  apiKeyLabel?: string;
  apiKeyPlaceholder?: string;
  serviceUrlLabel?: string;
  serviceUrlPlaceholder?: string;
  showProviderStatus?: boolean;
  providerGridClassName?: string;
  hideFieldsUntilProviderSelected?: boolean;
  accountIdLabel?: string;
  accountIdPlaceholder?: string;
};

const DEFAULT_CONFIG: Required<StepProviderConfig> = {
  providerOptions: DEFAULT_PROVIDERS,
  providerLabel: "Choose Provider",
  apiKeyLabel: "API Key",
  apiKeyPlaceholder: "Enter your API key",
  serviceUrlLabel: "Service Instance URL",
  serviceUrlPlaceholder: "https://api.example.com",
  showProviderStatus: true,
  providerGridClassName: "grid-cols-4 gap-3",
  hideFieldsUntilProviderSelected: false,
  accountIdLabel: "Account ID (optional)",
  accountIdPlaceholder: "Provider account/tenant id",
};

type StepProviderProps = {
  value: StepProviderValue;
  onChange: StepProviderChangeHandlers;
  config?: StepProviderConfig;
};

export const StepProvider = ({
  value,
  onChange,
  config,
}: StepProviderProps) => {
  const resolvedConfig = {
    ...DEFAULT_CONFIG,
    ...config,
    providerOptions: config?.providerOptions ?? DEFAULT_CONFIG.providerOptions,
  };
  const {
    providerOptions,
    providerLabel,
    apiKeyLabel,
    apiKeyPlaceholder,
    serviceUrlLabel,
    serviceUrlPlaceholder,
    showProviderStatus,
    providerGridClassName,
    hideFieldsUntilProviderSelected,
    accountIdLabel,
    accountIdPlaceholder,
  } = resolvedConfig;

  const [internalSelectedProvider, setInternalSelectedProvider] =
    useState<string>(providerOptions[0]?.key ?? "");

  const selectedProvider =
    value.selectedProvider ||
    internalSelectedProvider ||
    providerOptions[0]?.key ||
    "";
  const setSelectedProvider = (nextSelectedProvider: string) => {
    if (onChange.setSelectedProvider) {
      onChange.setSelectedProvider(nextSelectedProvider);
      return;
    }
    setInternalSelectedProvider(nextSelectedProvider);
  };

  const activeProvider =
    providerOptions.find((p) => p.key === selectedProvider) ??
    providerOptions[0];

  const showCredentialsSection =
    !hideFieldsUntilProviderSelected || Boolean(selectedProvider);

  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-y-auto py-3">
      <div className="flex flex-col">
        <span className="text-sm font-medium pb-2">
          {providerLabel} <span className="text-destructive">*</span>
        </span>
        <div className={`grid ${providerGridClassName}`}>
          {providerOptions.map((provider) => {
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
                    {provider.iconNode ? (
                      provider.iconNode
                    ) : (
                      <ForwardedIconComponent
                        name={provider.icon ?? "Cloud"}
                        className={`h-8 w-8 ${
                          isSelected
                            ? "text-foreground"
                            : "text-muted-foreground"
                        }`}
                      />
                    )}
                    <div className="flex flex-col my-1 text-left">
                      <span className="text-sm font-medium">
                        {provider.label}
                      </span>
                      {provider.tool && (
                        <span className="text-xs text-muted-foreground">
                          {provider.tool}
                        </span>
                      )}
                    </div>
                  </div>

                  {showProviderStatus && (
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-muted-foreground" />
                      Not connected
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {showCredentialsSection && (
        <>
          <div className="flex flex-col ">
            <span className="text-sm font-medium pb-2">
              {apiKeyLabel} <span className="text-destructive">*</span>
            </span>
            <Input
              type="password"
              placeholder={apiKeyPlaceholder}
              className="bg-muted"
              value={value.apiKey}
              onChange={(e) => onChange.setApiKey(e.target.value)}
            />
          </div>

          <div className="flex flex-col ">
            <span className="text-sm font-medium pb-2">
              {serviceUrlLabel} <span className="text-destructive">*</span>
            </span>
            <Input
              placeholder={serviceUrlPlaceholder}
              value={value.serviceUrl}
              className="bg-muted"
              onChange={(e) => onChange.setServiceUrl(e.target.value)}
            />
          </div>

          {activeProvider?.requiresAccountId && onChange.setAccountId && (
            <div className="flex flex-col ">
              <span className="text-sm font-medium pb-2">{accountIdLabel}</span>
              <Input
                placeholder={accountIdPlaceholder}
                value={value.accountId ?? ""}
                className="bg-muted"
                onChange={(e) => onChange.setAccountId?.(e.target.value)}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
};
