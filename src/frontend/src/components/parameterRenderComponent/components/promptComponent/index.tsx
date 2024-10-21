import { RECEIVING_INPUT_VALUE } from "@/constants/constants";
import PromptModal from "@/modals/promptModal";
import { useDarkStore } from "@/stores/darkStore";
import { cn } from "../../../../utils/utils";
import IconComponent from "../../../genericIconComponent";
import { Button } from "../../../ui/button";
import { getBackgroundStyle } from "../../helpers/get-gradient-class";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { InputProps, PromptAreaComponentType } from "../../types";

const promptContentClasses = {
  base: "overflow-hidden text-clip whitespace-nowrap",
  editNode: "input-edit-node input-dialog",
  normal: "primary-input text-muted-foreground",
  disabled: "disabled-state",
};

const externalLinkIconClasses = {
  gradient: "absolute right-7 h-5 w-10",
  background: "absolute right-[0.6px] h-5 w-9 rounded-l-xl",
  icon: "icons-parameters-comp absolute right-3 h-4 w-4 shrink-0",
  editNodeTop: "top-1",
  normalTop: "top-2.5",
};

export default function PromptAreaComponent({
  field_name,
  nodeClass,
  handleOnNewValue,
  handleNodeClass,
  value,
  disabled,
  editNode = false,
  id = "",
  readonly = false,
}: InputProps<string, PromptAreaComponentType>): JSX.Element {
  const isDark = useDarkStore((state) => state.dark);

  const renderPromptText = () => (
    <span
      id={id}
      data-testid={id}
      className={cn(
        promptContentClasses.base,
        editNode ? promptContentClasses.editNode : promptContentClasses.normal,
        disabled && !editNode && promptContentClasses.disabled,
      )}
    >
      {value !== ""
        ? value
        : getPlaceholder(disabled, "Type your prompt here...")}
    </span>
  );

  const renderExternalLinkIcon = () => (
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
          disabled && "bg-border",
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

  return (
    <div className={cn("w-full", disabled && "pointer-events-none")}>
      <PromptModal
        id={id}
        field_name={field_name}
        readonly={readonly}
        value={value}
        setValue={(newValue) => handleOnNewValue({ value: newValue })}
        nodeClass={nodeClass}
        setNodeClass={handleNodeClass}
      >
        <Button unstyled className="w-full">
          <div className="relative w-full">
            {renderPromptText()}
            {renderExternalLinkIcon()}
          </div>
        </Button>
      </PromptModal>
    </div>
  );
}
