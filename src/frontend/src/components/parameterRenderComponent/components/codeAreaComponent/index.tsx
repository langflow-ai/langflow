import { useEffect, useState } from "react";
import CodeAreaModal from "../../../../modals/codeAreaModal";
import { cn } from "../../../../utils/utils";

import IconComponent from "../../../genericIconComponent";
import { InputProps } from "../../types";

export default function CodeAreaComponent({
  value,
  handleOnNewValue,
  disabled,
  editNode = false,
  nodeClass,
  handleNodeClass,
  id = "",
}: InputProps<string>) {
  const [componentValue, setComponentValue] = useState(
    typeof value == "string" ? value : JSON.stringify(value),
  );
  useEffect(() => {
    if (disabled && componentValue !== "") {
      setComponentValue("");
      handleOnNewValue({ value: "" });
    }
  }, [disabled]);

  useEffect(() => {
    setComponentValue(typeof value == "string" ? value : JSON.stringify(value));
  }, [value]);

  const handleValueChange = (newValue) => {
    handleOnNewValue({ value: newValue });
  };

  const renderInputText = () => (
    <span
      id={id}
      data-testid={id}
      className={cn(
        editNode
          ? "input-edit-node input-dialog"
          : "primary-input text-muted-foreground",
        disabled && !editNode && "input-disable input-ring",
      )}
    >
      {value !== "" ? value : "Type something..."}
    </span>
  );

  const renderExternalLinkIcon = () => {
    if (editNode) return null;

    return (
      <IconComponent
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
      <CodeAreaModal
        dynamic={false}
        value={value}
        nodeClass={nodeClass}
        setNodeClass={handleNodeClass!}
        setValue={handleValueChange}
      >
        <div className="flex w-full items-center gap-3">
          {renderInputText()}
          {renderExternalLinkIcon()}
        </div>
      </CodeAreaModal>
    </div>
  );
}
