import { GRADIENT_CLASS } from "@/constants/constants";
import PromptModal from "@/modals/promptModal";
import { cn } from "../../../../utils/utils";
import IconComponent from "../../../genericIconComponent";
import { Button } from "../../../ui/button";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { InputProps, PromptAreaComponentType } from "../../types";

const promptContentClasses = {
  base: "overflow-hidden text-clip whitespace-nowrap",
  editNode: "input-edit-node input-dialog",
  normal: "primary-input text-muted-foreground",
  disabled: "disabled-state",
};

const externalLinkIconClasses = {
  gradient: ({ disabled }: { disabled: boolean }) =>
    disabled ? "" : "gradient-fade-input",
  background: ({ disabled }: { disabled: boolean }) =>
    disabled ? "" : "background-fade-input",
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
          externalLinkIconClasses.gradient({ disabled }),
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.normalTop,
        )}
        style={{
          pointerEvents: "none",
          background: disabled ? "" : GRADIENT_CLASS,
        }}
        aria-hidden="true"
      />
      <div
        className={cn(
          externalLinkIconClasses.background({ disabled }),
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.normalTop,
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
