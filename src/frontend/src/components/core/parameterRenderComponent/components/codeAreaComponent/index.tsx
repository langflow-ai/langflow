import { GRADIENT_CLASS } from "@/constants/constants";
import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";
import CodeAreaModal from "@/modals/codeAreaModal";
import { cn } from "../../../../../utils/utils";
import IconComponent from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import type { InputProps } from "../../types";

const codeContentClasses = {
  base: "overflow-hidden text-clip whitespace-nowrap",
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
  editNodeTop: "top-[6px]",
  normalTop: "top-2.5",
};

export default function CodeAreaComponent({
  value,
  handleOnNewValue,
  disabled,
  editNode = false,
  nodeClass,
  handleNodeClass,
  id = "",
  placeholder,
}: InputProps<string>) {
  const { data: config } = useGetConfig();
  const allowCustomComponents = config?.allow_custom_components ?? true;
  const isBlocked = !allowCustomComponents;
  const effectiveDisabled = disabled || isBlocked;

  const renderCodeText = () => (
    <span
      id={id}
      data-testid={id}
      className={cn(
        codeContentClasses.base,
        editNode ? codeContentClasses.editNode : codeContentClasses.normal,
        effectiveDisabled && !editNode && codeContentClasses.disabled,
      )}
    >
      {value !== "" ? value : getPlaceholder(effectiveDisabled, placeholder)}
    </span>
  );

  const renderExternalLinkIcon = () => (
    <>
      <div
        className={cn(
          externalLinkIconClasses.gradient({
            disabled: effectiveDisabled,
            editNode,
          }),
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.normalTop,
        )}
        style={{
          pointerEvents: "none",
          background: effectiveDisabled ? "" : GRADIENT_CLASS,
        }}
        aria-hidden="true"
      />
      <div
        className={cn(
          externalLinkIconClasses.background({
            disabled: effectiveDisabled,
            editNode,
          }),
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.normalTop,
          effectiveDisabled && "bg-border",
        )}
        aria-hidden="true"
      />
      <IconComponent
        name={effectiveDisabled ? "lock" : "Scan"}
        className={cn(
          externalLinkIconClasses.icon,
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.normalTop,
          effectiveDisabled ? "text-placeholder-foreground" : "text-foreground",
        )}
      />
    </>
  );

  if (isBlocked) {
    return (
      <div className="w-full pointer-events-none cursor-not-allowed">
        <div className="relative w-full">
          {renderCodeText()}
          {renderExternalLinkIcon()}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "w-full",
        effectiveDisabled && "pointer-events-none cursor-not-allowed",
      )}
    >
      <CodeAreaModal
        dynamic={false}
        value={value}
        nodeClass={nodeClass}
        setNodeClass={handleNodeClass!}
        setValue={(newValue) => handleOnNewValue({ value: newValue })}
      >
        <Button unstyled className="w-full">
          <div className="relative w-full">
            {renderCodeText()}
            {renderExternalLinkIcon()}
          </div>
        </Button>
      </CodeAreaModal>
    </div>
  );
}
