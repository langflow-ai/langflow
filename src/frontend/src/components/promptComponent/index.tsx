import PromptModal from "@/modals/promptModal";
import { useEffect } from "react";
import { PromptAreaComponentType } from "../../types/components";
import { cn } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";

export default function PromptAreaComponent({
  field_name,
  setNodeClass,
  nodeClass,
  value,
  onChange,
  disabled,
  editNode = false,
  id = "",
  readonly = false,
}: PromptAreaComponentType): JSX.Element {
  useEffect(() => {
    if (disabled && value !== "") {
      onChange("", undefined, true);
    }
  }, [disabled]);

  const renderPromptText = () => (
    <span
      id={id}
      data-testid={id}
      className={cn(
        editNode
          ? "input-edit-node input-dialog"
          : "primary-input text-muted-foreground",
        disabled && !editNode && "input-disable text-ring",
      )}
    >
      {value !== "" ? value : "Type your prompt here..."}
    </span>
  );

  const renderExternalLinkIcon = () => {
    if (editNode) return null;

    return (
      <IconComponent
        id={id}
        name="ExternalLink"
        className={cn(
          "icons-parameters-comp shrink-0",
          disabled ? "text-ring" : "hover:text-accent-foreground",
        )}
      />
    );
  };

  return (
    <div className={cn("w-full", disabled && "pointer-events-none")}>
      <PromptModal
        id={id}
        field_name={field_name}
        readonly={readonly}
        value={value}
        setValue={onChange}
        nodeClass={nodeClass}
        setNodeClass={setNodeClass}
      >
        <Button unstyled className="w-full">
          <div className="flex w-full items-center gap-3">
            {renderPromptText()}
            {renderExternalLinkIcon()}
          </div>
        </Button>
      </PromptModal>
    </div>
  );
}
