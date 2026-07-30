import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { GRADIENT_CLASS } from "@/constants/constants";
import QueryModal from "@/modals/queryModal";
import { cn } from "../../../../../utils/utils";
import IconComponent from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import { Input } from "../../../../ui/input";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import type { InputProps, QueryComponentType } from "../../types";
import { getIconName } from "../inputComponent/components/helpers/get-icon-name";

const inputClasses = {
  base: ({ isFocused }: { isFocused: boolean }) =>
    `w-full ${isFocused ? "" : "pr-3"}`,
  editNode: "input-edit-node",
  normal: ({ isFocused }: { isFocused: boolean }) =>
    `primary-input ${isFocused ? "text-primary" : "text-muted-foreground"}`,
  disabled: "disabled-state",
  password: "password",
};

const externalLinkIconClasses = {
  gradient: ({
    disabled,
    editNode,
  }: {
    disabled: boolean;
    editNode: boolean;
  }) =>
    disabled
      ? ""
      : editNode
        ? "gradient-fade-input-edit-node"
        : "gradient-fade-input",
  background: ({
    disabled,
    editNode,
  }: {
    disabled: boolean;
    editNode: boolean;
  }) =>
    disabled
      ? ""
      : editNode
        ? "background-fade-input-edit-node"
        : "background-fade-input",
  icon: "icons-parameters-comp absolute right-3 h-4 w-4 shrink-0",
  editNodeTop: "top-[-1.4rem] h-5",
  normalTop: "top-[-2.1rem] h-7",
  iconTop: "top-[-1.7rem]",
};

export default function QueryComponent({
  value,
  disabled,
  handleOnNewValue,
  editNode = false,
  id = "",
  placeholder,
  isToolMode = false,
  display_name,
  info,
  separator,
  showParameter = true,
}: InputProps<string, QueryComponentType>): JSX.Element | null {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  const getInputClassName = () => {
    return cn(
      inputClasses.base({ isFocused }),
      editNode ? inputClasses.editNode : inputClasses.normal({ isFocused }),
      disabled && inputClasses.disabled,
      isFocused && "pr-10",
    );
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleOnNewValue({ value: e.target.value });
  };

  const renderGradient = () =>
    !disabled &&
    !isFocused && (
      <div
        className={cn(
          externalLinkIconClasses.gradient({
            disabled,
            editNode,
          }),
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
    );

  const renderIcon = () => (
    <IconComponent
      dataTestId={`button_open_text_area_modal_${id}${editNode ? "_advanced" : ""}`}
      name={getIconName(disabled, "", "", false, isToolMode) || "Scan"}
      className={cn(
        "h-4 w-4 cursor-pointer bg-background",
        disabled
          ? "bg-muted text-placeholder-foreground"
          : "bg-background text-foreground",
      )}
    />
  );

  if (!showParameter) {
    return null;
  }

  return (
    <div className={cn("w-full", disabled && "pointer-events-none")}>
      <Input
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        id={id}
        data-testid={id}
        value={disabled ? "" : value}
        onChange={handleInputChange}
        disabled={disabled}
        className={getInputClassName()}
        placeholder={getPlaceholder(disabled, placeholder)}
        aria-label={disabled ? value : undefined}
        ref={inputRef}
        type={"text"}
      />

      <div className="relative w-full">
        {renderGradient()}
        <QueryModal
          title={display_name}
          description={info}
          placeholder={placeholder}
          value={value}
          setValue={(newValue) => handleOnNewValue({ value: newValue })}
          disabled={disabled}
        >
          <Button
            unstyled
            aria-label={t("input.expandTextEditor")}
            className={cn(
              // `before:` pseudo-element pads the touch target out to the
              // WCAG 2.5.8 minimum (24x24) without resizing the visible
              // icon or shifting its position. The button is already
              // `position: absolute` (via externalLinkIconClasses.icon),
              // which is enough to anchor the pseudo-element.
              "flex items-center justify-center before:absolute before:-inset-1 before:content-['']",
              externalLinkIconClasses.icon,
              editNode
                ? externalLinkIconClasses.editNodeTop
                : externalLinkIconClasses.iconTop,
            )}
          >
            {renderIcon()}
          </Button>
        </QueryModal>
      </div>
    </div>
  );
}
