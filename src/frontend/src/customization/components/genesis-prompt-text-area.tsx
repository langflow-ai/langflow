/**
 * Genesis Prompt TextArea Component
 * 
 * A custom TextAreaComponent that integrates with the Genesis Prompt Library.
 * This component is used when a template field has prompt_id set, indicating
 * it's connected to the Genesis Prompt Management system.
 * 
 * It uses the GenesisPromptTextModal instead of the standard ComponentTextModal
 * to provide additional functionality like:
 * - Save to Prompt Library
 * - Submit for Review
 * - Version status display
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { getCurlWebhookCode } from "@/modals/apiModal/utils/get-curl-code";
import GenesisPromptTextModal from "@/modals/genesisPromptTextModal";
import { cn } from "@/utils/utils";
import IconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { getPlaceholder } from "@/components/core/parameterRenderComponent/helpers/get-placeholder-disabled";
import { getIconName } from "@/components/core/parameterRenderComponent/components/inputComponent/components/helpers/get-icon-name";

const inputClasses = {
  base: ({ isFocused, password }: { isFocused: boolean; password: boolean }) =>
    `w-full ${isFocused ? "" : "pr-3"} ${password ? "pr-16" : ""}`,
  editNode: "input-edit-node",
  normal: ({ isFocused }: { isFocused: boolean }) =>
    `primary-input ${isFocused ? "text-primary" : "text-muted-foreground"}`,
  disabled: "disabled-state",
  password: "password",
};

const { protocol, host } = customGetHostProtocol();

const externalLinkIconClasses = {
  gradient: ({
    disabled,
    editNode,
    password,
  }: {
    disabled: boolean;
    editNode: boolean;
    password: boolean;
  }) =>
    disabled || password
      ? ""
      : editNode
      ? "gradient-fade-input-edit-node"
      : "gradient-fade-input",
  icon: "icons-parameters-comp absolute right-3 h-4 w-4 shrink-0",
  editNodeTop: "-top-[37px] h-[36px]",
  normalTop: "top-[-2.1rem] h-7",
  iconTop: "top-[-1.7rem]",
};

export interface GenesisPromptTextAreaProps {
  value: string;
  disabled: boolean;
  handleOnNewValue: (data: { value: string }) => void;
  editNode?: boolean;
  id?: string;
  updateVisibility?: () => void;
  password?: boolean;
  placeholder?: string;
  isToolMode?: boolean;
  // Genesis Prompt specific props
  promptId?: string;
  promptVersion?: number;
  versionStatus?: string;
  onSaveVersion?: (content: string) => void;
  isSavingVersion?: boolean;
  onSubmitForReview?: (comment?: string) => void;
  isSubmittingForReview?: boolean;
  isLoading?: boolean;
}

export default function GenesisPromptTextArea({
  value,
  disabled,
  handleOnNewValue,
  editNode = false,
  id = "",
  updateVisibility,
  password,
  placeholder,
  isToolMode = false,
  promptId,
  promptVersion,
  versionStatus,
  onSaveVersion,
  isSavingVersion,
  onSubmitForReview,
  isSubmittingForReview,
  isLoading = false,
}: GenesisPromptTextAreaProps): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);

  const getInputClassName = () => {
    return cn(
      inputClasses.base({ isFocused, password: password! }),
      editNode ? inputClasses.editNode : inputClasses.normal({ isFocused }),
      disabled && inputClasses.disabled,
      password && !passwordVisible && "text-clip",
      isFocused && "pr-10"
    );
  };

  const renderIcon = () => (
    <div>
      {!disabled && !isFocused && (
        <div
          className={cn(
            externalLinkIconClasses.gradient({
              disabled,
              editNode,
              password: password!,
            }),
            editNode
              ? externalLinkIconClasses.editNodeTop
              : externalLinkIconClasses.normalTop
          )}
          style={{
            pointerEvents: "none",
            background: isFocused
              ? undefined
              : disabled
              ? "bg-background"
              : "",
          }}
          aria-hidden="true"
        />
      )}

      <IconComponent
        dataTestId={`button_open_text_area_modal_${id}${
          editNode ? "_advanced" : ""
        }`}
        name={getIconName(disabled, "", "", false, isToolMode) || "Scan"}
        className={cn(
          "cursor-pointer bg-background",
          externalLinkIconClasses.icon,
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.iconTop,
          disabled
            ? "bg-muted text-placeholder-foreground"
            : "bg-background text-foreground"
        )}
      />
    </div>
  );

  return (
    <div className={cn("w-full", (disabled || isLoading) && "pointer-events-none")}>
      <Input
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        id={id}
        data-testid={id}
        value={isLoading ? "" : disabled ? "" : value}
        onChange={() => {}} // Read-only, changes happen in modal
        disabled={disabled || isLoading}
        className={cn(
          getInputClassName(),
          "cursor-default select-none caret-transparent",
          isLoading && "animate-pulse"
        )}
        placeholder={isLoading ? "Loading..." : getPlaceholder(disabled, placeholder)}
        aria-label={disabled ? value : undefined}
        ref={inputRef}
        type={password ? (passwordVisible ? "text" : "password") : "text"}
        readOnly
      />

      <GenesisPromptTextModal
        changeVisibility={updateVisibility}
        value={value}
        setValue={(newValue) => handleOnNewValue({ value: newValue })}
        disabled={disabled}
        promptId={promptId}
        promptVersion={promptVersion}
        versionStatus={versionStatus}
        onSaveVersion={onSaveVersion}
        isSavingVersion={isSavingVersion}
        onSubmitForReview={onSubmitForReview}
        isSubmittingForReview={isSubmittingForReview}
      >
        <div className="relative w-full">
          {renderIcon()}
        </div>
      </GenesisPromptTextModal>

      {password && !isFocused && (
        <div
          onClick={() => {
            setPasswordVisible(!passwordVisible);
          }}
        >
          <IconComponent
            name={passwordVisible ? "eye" : "eye-off"}
            className={cn(
              externalLinkIconClasses.icon,
              editNode ? "top-[5px]" : "top-[13px]",
              disabled
                ? "text-placeholder"
                : "text-placeholder-foreground hover:text-foreground",
              "right-10"
            )}
          />
        </div>
      )}
    </div>
  );
}
