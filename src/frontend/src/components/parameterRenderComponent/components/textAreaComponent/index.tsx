import { GRADIENT_CLASS } from "@/constants/constants";
import ComponentTextModal from "@/modals/textAreaModal";
import { useDarkStore } from "@/stores/darkStore";
import { useRef, useState } from "react";
import { cn } from "../../../../utils/utils";
import IconComponent from "../../../genericIconComponent";
import { Button } from "../../../ui/button";
import { Input } from "../../../ui/input";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { InputProps, TextAreaComponentType } from "../../types";

const inputClasses = {
  base: ({ isFocused }: { isFocused: boolean }) =>
    `w-full ${isFocused ? "" : "pr-3"}`,
  editNode: "input-edit-node",
  normal: "primary-input text-muted-foreground",
  disabled: "disabled-state",
  password: "password",
};

const externalLinkIconClasses = {
  gradient: ({ disabled }: { disabled: boolean }) =>
    disabled ? "" : "gradient-fade-input",
  background: ({ disabled }: { disabled: boolean }) =>
    disabled ? "" : "background-fade-input",
  icon: "icons-parameters-comp absolute right-3 h-4 w-4 shrink-0 cursor-pointer",
  editNodeTop: "top-1",
  normalTop: "top-[-35px]",
  iconTop: "top-[-30px]",
};

export default function TextAreaComponent({
  value,
  disabled,
  handleOnNewValue,
  editNode = false,
  id = "",
  updateVisibility,
}: InputProps<string, TextAreaComponentType>): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  const getInputClassName = () => {
    return cn(
      inputClasses.base({ isFocused }),
      editNode ? inputClasses.editNode : inputClasses.normal,
      disabled && inputClasses.disabled,
    );
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleOnNewValue({ value: e.target.value });
  };

  const renderIcon = () => (
    <div className={cn(isFocused && "opacity-0")}>
      <div className="relative cursor-pointer">
        <div
          className={cn(
            externalLinkIconClasses.gradient({ disabled }),
            editNode
              ? externalLinkIconClasses.editNodeTop
              : externalLinkIconClasses.normalTop,
          )}
          style={{
            pointerEvents: "none",
            background: isFocused
              ? undefined
              : disabled
                ? "bg-background"
                : GRADIENT_CLASS,
          }}
          aria-hidden="true"
        />
        <div
          className={cn(
            externalLinkIconClasses.background({ disabled }),
            editNode
              ? externalLinkIconClasses.editNodeTop
              : externalLinkIconClasses.normalTop,
            disabled && "bg-secondary",
          )}
          aria-hidden="true"
        />
        <IconComponent
          name={disabled ? "lock" : "Scan"}
          className={cn(
            externalLinkIconClasses.icon,
            editNode
              ? externalLinkIconClasses.editNodeTop
              : externalLinkIconClasses.iconTop,
            disabled ? "text-placeholder" : "text-foreground",
          )}
        />
      </div>
    </div>
  );

  return (
    <div className={cn("relative w-full", disabled && "pointer-events-none")}>
      <Input
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        id={id}
        data-testid={id}
        value={disabled ? "" : value}
        onChange={handleInputChange}
        disabled={disabled}
        className={getInputClassName()}
        placeholder={getPlaceholder(disabled, "Type something...")}
        aria-label={disabled ? value : undefined}
        ref={inputRef}
      />

      <ComponentTextModal
        changeVisibility={updateVisibility}
        value={value}
        setValue={(newValue) => handleOnNewValue({ value: newValue })}
        disabled={disabled}
      >
        {renderIcon()}
      </ComponentTextModal>
    </div>
  );
}
