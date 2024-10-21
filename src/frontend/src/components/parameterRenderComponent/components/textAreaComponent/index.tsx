import { RECEIVING_INPUT_VALUE } from "@/constants/constants";
import ComponentTextModal from "@/modals/textAreaModal";
import { useDarkStore } from "@/stores/darkStore";
import { cn } from "../../../../utils/utils";
import IconComponent from "../../../genericIconComponent";
import { Button } from "../../../ui/button";
import { getBackgroundStyle } from "../../helpers/get-gradient-class";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { getTextAreaContentClasses } from "../../helpers/get-textarea-content-class";
import { InputProps, TextAreaComponentType } from "../../types";

const textAreaContentClasses = {
  base: "overflow-hidden text-clip whitespace-nowrap",
  editNode: "input-edit-node input-dialog",
  normal: "primary-input text-muted-foreground",
  disabled: "disabled-state",
  password: "password",
};

const externalLinkIconClasses = {
  gradient: "absolute right-7 h-5 w-10",
  background: "absolute right-[0.9px] h-5 w-9 rounded-l-xl",
  icon: "icons-parameters-comp absolute right-3 h-4 w-4 shrink-0",
  editNodeTop: "top-1",
  normalTop: "top-2.5",
};

const passwordToggleClasses =
  "side-bar-button-size absolute right-10 top-1/2 mb-px -translate-y-1/2 text-muted-foreground hover:text-current";

export default function TextAreaComponent({
  value,
  disabled,
  handleOnNewValue,
  editNode = false,
  id = "",
  password,
  updateVisibility,
}: InputProps<string, TextAreaComponentType>): JSX.Element {
  const isDark = useDarkStore((state) => state.dark);

  const renderTextAreaContent = () => (
    <span
      id={id}
      data-testid={id}
      className={getTextAreaContentClasses({
        editNode,
        disabled,
        password,
        value,
        textAreaContentClasses,
      })}
    >
      {value !== "" ? value : getPlaceholder(disabled, "Type something...")}
    </span>
  );

  const renderIcon = () => (
    <>
      <div
        className={cn(
          externalLinkIconClasses.gradient,
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.normalTop,
        )}
        style={getBackgroundStyle(disabled, isDark) as React.CSSProperties}
        aria-hidden="true"
      />
      <div
        className={cn(
          externalLinkIconClasses.background,
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.normalTop,
          isDark ? "bg-black" : "bg-white",
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
            : externalLinkIconClasses.normalTop,
          disabled ? "text-placeholder" : "text-foreground",
        )}
      />
    </>
  );

  const renderPasswordToggle = () => {
    if (!password) return null;

    return (
      <Button
        unstyled
        tabIndex={-1}
        className={passwordToggleClasses}
        onClick={(event) => {
          event.preventDefault();
          if (updateVisibility) updateVisibility();
        }}
      >
        <IconComponent name={password ? "EyeOff" : "Eye"} className="h-4 w-4" />
      </Button>
    );
  };

  return (
    <div className={cn("w-full", disabled && "pointer-events-none")}>
      <ComponentTextModal
        changeVisibility={updateVisibility}
        value={value}
        setValue={(newValue) => handleOnNewValue({ value: newValue })}
        disabled={disabled}
        password={password}
      >
        <Button unstyled className="w-full">
          <div className="relative w-full">
            {renderTextAreaContent()}
            {renderPasswordToggle()}
            {renderIcon()}
          </div>
        </Button>
      </ComponentTextModal>
    </div>
  );
}
