import { GRADIENT_CLASS } from "@/constants/constants";
import PromptModal from "@/modals/promptModal";
import { cn } from "../../../../../utils/utils";
import IconComponent from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { InputProps, PromptAreaComponentType } from "../../types";

const promptContentClasses = {
  base: "overflow-hidden text-clip whitespace-nowrap bg-background",
  editNode: "input-edit-node input-dialog",
  normal: "primary-input text-muted-foreground",
  disabled: "disabled-state",
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
        ? "gradient-fade-input-edit-node "
        : "gradient-fade-input ",
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
        ? "background-fade-input-edit-node "
        : "background-fade-input",
  icon: "icons-parameters-comp absolute right-3 h-4 w-4 shrink-0",
  editNodeTop: "top-[0.375rem]",
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
          externalLinkIconClasses.gradient({ disabled, editNode }),
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
          externalLinkIconClasses.background({ disabled, editNode }),
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
          disabled ? "text-placeholder-foreground" : "text-foreground",
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
        <Button
          unstyled
          className="w-full"
          data-testid="button_open_prompt_modal"
        >
          <div className="relative w-full">
            {renderPromptText()}
            {renderExternalLinkIcon()}
          </div>
        </Button>
      </PromptModal>
    </div>
  );
}
