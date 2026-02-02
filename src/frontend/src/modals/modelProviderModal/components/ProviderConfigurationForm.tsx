import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ProviderVariable } from "@/constants/providerConstants";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import { AnimatePresence, motion } from "framer-motion";
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
  isSaving: boolean;
  isPending: boolean;
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
  isSaving,
  isPending,
  validationFailed,
  validationState,
  validationError,
  canSave,
  requiresConfiguration,
}: ProviderConfigurationFormProps) => {
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
                {variable.description && (
                  <span className="text-[11px] text-muted-foreground/70 mb-1">
                    {variable.description}
                  </span>
                )}
                {variable.options && variable.options.length > 0 ? (
                  // Render dropdown for variables with predefined options
                  <div className="relative">
                    <Select
                      value={
                        variableValues[variable.variable_key] ||
                        (isConfigured
                          ? getConfiguredValue(variable.variable_key) || ""
                          : "")
                      }
                      onValueChange={(value) =>
                        onVariableChange(variable.variable_key, value)
                      }
                    >
                      <SelectTrigger
                        className={cn(
                          "w-full",
                          isConfigured && !hasNewValue && "pr-8",
                        )}
                      >
                        <SelectValue
                          placeholder={`Select ${variable.variable_name}`}
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {variable.options.map((option) => (
                          <SelectItem key={option} value={option}>
                            {option}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {isConfigured && !hasNewValue && (
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-green-500 pointer-events-none">
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
          <Button
            onClick={onSave}
            loading={isSaving}
            disabled={!canSave || isSaving}
            className="mt-2"
          >
            {isSaving
              ? "Saving..."
              : validationFailed
                ? "Retry Save"
                : "Save Configuration"}
          </Button>
        </div>
      ) : (
        <Button
          onClick={onActivate}
          loading={isPending}
          disabled={selectedProvider.is_enabled}
        >
          {selectedProvider.is_enabled
            ? `${selectedProvider.provider} Activated`
            : `Activate ${selectedProvider.provider}`}
        </Button>
      )}
    </div>
  );
};

export default ProviderConfigurationForm;
