import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ProviderVariable } from "@/constants/providerConstants";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import { useEffect, useState } from "react";
import MultiselectComponent from "@/components/core/parameterRenderComponent/components/multiselectComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import useAlertStore from "@/stores/alertStore";
import DisconnectWarning from "./DisconnectWarning";
import { Provider } from "./types";

const PROVIDER_KEY_PREVIEW: Record<
  string,
  { prefix: string; totalLength: number }
> = {
  OpenAI: { prefix: "sk-proj-", totalLength: 164 },
  Anthropic: { prefix: "sk-ant-", totalLength: 108 },
  "Google Generative AI": { prefix: "AIza", totalLength: 39 },
  "IBM watsonx": { prefix: "", totalLength: 44 },
};

const getMaskedKeyPreview = (providerName: string): string => {
  const config = PROVIDER_KEY_PREVIEW[providerName] || {
    prefix: "",
    totalLength: 40,
  };
  const maskedLength = Math.max(config.totalLength - config.prefix.length, 8);
  return `${config.prefix}${"•".repeat(maskedLength)}`;
};

export interface ProviderConfigurationFormProps {
  selectedProvider: Provider | null;
  providerVariables: ProviderVariable[];
  variableValues: Record<string, string>;
  isVariableConfigured: (key: string) => boolean;
  getConfiguredValue: (key: string) => string | null;
  onVariableChange: (key: string, value: string) => void;
  onSave: () => void;
  onActivate: () => void;
  onDisconnect: () => void;
  isSaving: boolean;
  isPending: boolean;
  isDeleting: boolean;
  isFetchingModels: boolean;
  validationFailed: boolean;
  validationState: "idle" | "validating" | "valid" | "invalid";
  validationError: string | null;
  canSave: boolean;
  requiresConfiguration: boolean;
  isFetchingAfterDisconnect: boolean;
}

// Generate a stable random placeholder for a given variable type
const getPlaceholder = (variableName: string, provider: string) => {
  const name = variableName.toLowerCase();
  const providerLower = provider.toLowerCase();

  if (providerLower === "ollama" && name.includes("url")) {
    return "http://localhost:11434";
  }

  if (
    name.includes("api key") ||
    name.includes("apikey") ||
    name.includes("token")
  ) {
    if (providerLower.includes("anthropic")) return "sk-ant-...";
    if (providerLower.includes("google")) return "AIza...";
    if (providerLower.includes("openai")) return "sk-...";
  }

  return `Enter your ${variableName}`;
};

const ProviderConfigurationForm = ({
  selectedProvider,
  providerVariables,
  variableValues,
  isVariableConfigured,
  getConfiguredValue,
  onVariableChange,
  onSave,
  onActivate,
  onDisconnect,
  isSaving,
  isPending,
  isDeleting,
  isFetchingModels,
  validationFailed,
  validationState,
  validationError,
  canSave,
  requiresConfiguration,
  isFetchingAfterDisconnect,
}: ProviderConfigurationFormProps) => {
  const [showDisconnectWarning, setShowDisconnectWarning] = useState(false);
  const [editingSecret, setEditingSecret] = useState<Record<string, boolean>>(
    {},
  );

  // True during validation, saving, and the post-save model refetch
  const isLoading =
    isSaving || validationState === "validating" || isFetchingModels;

  const setErrorData = useAlertStore((state) => state.setErrorData);

  useEffect(() => {
    if (validationState === "invalid" && validationError) {
      setErrorData({
        title: "Validation Failed",
        list: [validationError],
      });
    }
  }, [validationState, validationError]);

  const isAlreadyConfigured = providerVariables
    .filter((v) => v.required)
    .every((v) => isVariableConfigured(v.variable_key));

  const isSingleVariableProvider = providerVariables.length === 1;

  if (!selectedProvider) return null;

  return (
    <div className="flex flex-col gap-1 p-4">
      <div className="flex flex-row gap-1 min-w-[300px]">
        <span className="text-[13px] font-semibold mr-auto">
          {isSingleVariableProvider ? (
            <>
              {providerVariables[0].variable_name}
              {providerVariables[0].required && (
                <span className="text-red-500 ml-1">*</span>
              )}
            </>
          ) : (
            `${selectedProvider.provider || "Unknown Provider"} ${requiresConfiguration && " Configuration"}`
          )}
        </span>
      </div>
      <span className="text-[13px] text-muted-foreground pt-1 pb-2">
        {requiresConfiguration ? (
          <>
            Configure your{" "}
            <span
              className="underline cursor-pointer hover:text-primary"
              onClick={() => {
                if (selectedProvider.api_docs_url) {
                  window.open(
                    selectedProvider.api_docs_url,
                    "_blank",
                    "noopener,noreferrer",
                  );
                }
              }}
            >
              {selectedProvider.provider} credentials
            </span>{" "}
            to enable these models
          </>
        ) : (
          <>Activate {selectedProvider.provider} to enable these models</>
        )}
      </span>
      {requiresConfiguration ? (
        <div className="flex flex-col gap-3">
          {providerVariables.map((variable) => {
            const isConfigured = isVariableConfigured(variable.variable_key);
            const hasNewValue = variableValues[variable.variable_key]?.trim();
            const isEditing = editingSecret[variable.variable_key];

            return (
              <div key={variable.variable_key} className="flex flex-col gap-1">
                {!isSingleVariableProvider && (
                  <label className="text-[12px] font-medium text-muted-foreground">
                    {variable.variable_name}
                    {variable.required && (
                      <span className="text-red-500 ml-1">*</span>
                    )}
                  </label>
                )}
                {variable.options && variable.options.length > 0 ? (
                  // Render dropdown for variables with predefined options
                  <div className="relative">
                    <MultiselectComponent
                      id={variable.variable_key}
                      editNode={false}
                      disabled={isSaving || isDeleting}
                      value={
                        variableValues[variable.variable_key]
                          ? [variableValues[variable.variable_key]]
                          : isConfigured &&
                              getConfiguredValue(variable.variable_key)
                            ? [
                                getConfiguredValue(
                                  variable.variable_key,
                                ) as string,
                              ]
                            : []
                      }
                      options={variable.options}
                      combobox={variable.combobox}
                      hideOnSelection={true}
                      handleOnNewValue={(val) => {
                        const newArray = val.value as string[];
                        if (newArray && newArray.length > 0) {
                          onVariableChange(
                            variable.variable_key,
                            newArray[newArray.length - 1],
                          );
                        } else {
                          onVariableChange(variable.variable_key, "");
                        }
                      }}
                    />
                    {!isLoading && (
                      <>
                        {validationState === "invalid" && (
                          <span className="absolute w-4 h-4 right-9 top-1/2 -translate-y-1/2 pointer-events-auto">
                            <ShadTooltip
                              content={validationError}
                              side="top"
                              styleClasses="text-destructive border-destructive"
                            >
                              <div>
                                <ForwardedIconComponent
                                  name="X"
                                  className="h-4 w-4 text-destructive cursor-default"
                                />
                              </div>
                            </ShadTooltip>
                          </span>
                        )}
                        {validationState !== "invalid" &&
                          (validationState === "valid" ||
                            (isConfigured && !hasNewValue)) && (
                            <span className="absolute right-8 top-1/2 -translate-y-1/2 text-green-500 pointer-events-none">
                              <ForwardedIconComponent
                                name="Check"
                                className="h-4 w-4"
                              />
                            </span>
                          )}
                      </>
                    )}
                  </div>
                ) : (
                  // Render input for text/secret variables
                  <Input
                    placeholder={getPlaceholder(
                      variable.variable_name,
                      selectedProvider.provider,
                    )}
                    value={
                      isConfigured &&
                      variable.is_secret &&
                      !isEditing &&
                      !hasNewValue
                        ? getMaskedKeyPreview(selectedProvider.provider)
                        : variable.variable_key in variableValues
                          ? variableValues[variable.variable_key]
                          : isConfigured && !variable.is_secret
                            ? (getConfiguredValue(variable.variable_key) ?? "")
                            : ""
                    }
                    type={
                      variable.is_secret && (isEditing || hasNewValue)
                        ? "password"
                        : "text"
                    }
                    onChange={(e) => {
                      onVariableChange(variable.variable_key, e.target.value);
                    }}
                    onFocus={() => {
                      if (isConfigured && variable.is_secret && !hasNewValue) {
                        setEditingSecret((prev) => ({
                          ...prev,
                          [variable.variable_key]: true,
                        }));
                        onVariableChange(variable.variable_key, "");
                      }
                    }}
                    onBlur={() => {
                      if (!variableValues[variable.variable_key]) {
                        setEditingSecret((prev) => ({
                          ...prev,
                          [variable.variable_key]: false,
                        }));
                      }
                    }}
                    endIcon={
                      !isLoading && validationState === "invalid" ? (
                        <ShadTooltip
                          content={validationError}
                          side="top"
                          styleClasses="text-destructive border-destructive"
                        >
                          <div>
                            <ForwardedIconComponent
                              name="X"
                              className="h-4 w-4 text-destructive cursor-default"
                            />
                          </div>
                        </ShadTooltip>
                      ) : !isLoading &&
                        (validationState === "valid" ||
                          (isConfigured && !hasNewValue && !isEditing)) ? (
                        <ForwardedIconComponent
                          name="Check"
                          className="h-4 w-4 text-green-500 pointer-events-none"
                        />
                      ) : undefined
                    }
                  />
                )}
              </div>
            );
          })}
          {/* Save button */}
          <div className="flex justify-end mt-2 gap-2">
            {selectedProvider.is_enabled && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setShowDisconnectWarning(true)}
                loading={isDeleting || isFetchingAfterDisconnect}
                disabled={isDeleting || isFetchingAfterDisconnect || isSaving}
              >
                Disconnect
              </Button>
            )}
            <Button
              onClick={onSave}
              size="sm"
              loading={isLoading || isFetchingModels}
              disabled={!canSave || isLoading || isFetchingModels}
            >
              {validationFailed
                ? "Retry Save"
                : isAlreadyConfigured
                  ? "Replace Configuration"
                  : "Save Configuration"}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Button
            onClick={onActivate}
            loading={isPending}
            disabled={selectedProvider.is_enabled}
          >
            {selectedProvider.is_enabled
              ? `${selectedProvider.provider} Activated`
              : `Activate ${selectedProvider.provider}`}
          </Button>
          {selectedProvider.is_enabled && (
            <Button
              variant="destructive"
              onClick={() => setShowDisconnectWarning(true)}
              disabled={isDeleting || isPending}
            >
              Deactivate {selectedProvider.provider}
            </Button>
          )}
        </div>
      )}

      <DisconnectWarning
        show={showDisconnectWarning}
        message={
          requiresConfiguration
            ? "Disconnecting an API key will disable all of the provider's models being used in a flow."
            : `Deactivating ${selectedProvider.provider} will disable all of the provider's models being used in a flow.`
        }
        onCancel={() => setShowDisconnectWarning(false)}
        onConfirm={() => {
          onDisconnect();
          setShowDisconnectWarning(false);
        }}
        isLoading={isDeleting}
        className="absolute inset-0 m-4 bg-background z-50 border-destructive border"
      />
    </div>
  );
};

export default ProviderConfigurationForm;
