import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ProviderVariable } from "@/constants/providerConstants";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import MultiselectComponent from "@/components/core/parameterRenderComponent/components/multiselectComponent";
import DisconnectWarning from "./DisconnectWarning";
import { Provider } from "./types";

const MASKED_VALUE = "••••••••";

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
  validationFailed: boolean;
  validationState: "idle" | "validating" | "valid" | "invalid";
  validationError: string | null;
  canSave: boolean;
  requiresConfiguration: boolean;
}

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
  validationFailed,
  validationState,
  validationError,
  canSave,
  requiresConfiguration,
}: ProviderConfigurationFormProps) => {
  const [showDisconnectWarning, setShowDisconnectWarning] = useState(false);

  const isAlreadyConfigured = providerVariables
    .filter((v) => v.required)
    .every((v) => isVariableConfigured(v.variable_key));

  if (!selectedProvider) return null;

  return (
    <div className="flex flex-col gap-1 p-4">
      <div className="flex flex-row gap-1 min-w-[300px]">
        <span className="text-[13px] font-semibold mr-auto">
          {selectedProvider.provider || "Unknown Provider"}
          {requiresConfiguration && " Configuration"}
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

            return (
              <div key={variable.variable_key} className="flex flex-col gap-1">
                <label className="text-[12px] font-medium text-muted-foreground">
                  {variable.variable_name}
                  {variable.required && (
                    <span className="text-red-500 ml-1">*</span>
                  )}
                </label>
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
                    {isConfigured && !hasNewValue && (
                      <span className="absolute right-8 top-1/2 -translate-y-1/2 text-green-500 pointer-events-none">
                        <ForwardedIconComponent
                          name="check"
                          className="h-4 w-4"
                        />
                      </span>
                    )}
                  </div>
                ) : (
                  // Render input for text/secret variables
                  <Input
                    placeholder={
                      isConfigured && !hasNewValue
                        ? variable.is_secret
                          ? MASKED_VALUE
                          : `Add ${variable.variable_name.toLowerCase()}`
                        : `Add ${variable.variable_name.toLowerCase()}`
                    }
                    defaultValue={
                      isConfigured
                        ? (variable.is_secret
                            ? MASKED_VALUE
                            : getConfiguredValue(variable.variable_key)) || ""
                        : ""
                    }
                    value={variableValues[variable.variable_key] || ""}
                    type={
                      variable.is_secret && hasNewValue ? "password" : "text"
                    }
                    onChange={(e) => {
                      // Clear masked value on focus/type for secrets
                      const newValue =
                        e.target.value === MASKED_VALUE ? "" : e.target.value;
                      onVariableChange(variable.variable_key, newValue);
                    }}
                    onFocus={() => {
                      // Clear masked value when user focuses on a configured secret field
                      if (isConfigured && variable.is_secret && !hasNewValue) {
                        onVariableChange(variable.variable_key, "");
                      }
                    }}
                    endIcon={isConfigured && !hasNewValue ? "Check" : undefined}
                    endIconClassName={cn(
                      isConfigured && !hasNewValue && "text-green-500",
                    )}
                  />
                )}
              </div>
            );
          })}
          {/* Validation status */}
          <AnimatePresence mode="wait">
            {validationState === "validating" && (
              <motion.div
                key="validating"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="flex items-center gap-2 text-muted-foreground text-xs pb-2">
                  <ForwardedIconComponent
                    name="Loader2"
                    className="h-3 w-3 animate-spin shrink-0"
                  />
                  <span>Validating credentials...</span>
                </div>
              </motion.div>
            )}
            {validationState === "valid" && (
              <motion.div
                key="valid"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="flex items-center gap-2 text-green-600 text-xs pb-2">
                  <ForwardedIconComponent
                    name="Check"
                    className="h-3 w-3 shrink-0"
                  />
                  <span>Credentials validated successfully</span>
                </div>
              </motion.div>
            )}
            {validationState === "invalid" && validationError && (
              <motion.div
                key="invalid"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="flex items-center gap-2 text-destructive text-xs pb-2">
                  <ForwardedIconComponent
                    name="AlertCircle"
                    className="h-3 w-3 shrink-0"
                  />
                  <span>{validationError}</span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          {/* Save button - only enabled when validation passes */}
          <div className="flex justify-end mt-2 gap-2">
            {selectedProvider.is_enabled && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setShowDisconnectWarning(true)}
                disabled={isDeleting || isSaving}
              >
                Disconnect
              </Button>
            )}
            <Button
              onClick={onSave}
              size="sm"
              loading={isSaving}
              disabled={!canSave || isSaving}
            >
              {isSaving
                ? "Saving..."
                : validationFailed
                  ? "Retry Save"
                  : isAlreadyConfigured
                    ? "Replace API Key"
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
