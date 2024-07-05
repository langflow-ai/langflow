import { useEffect, useState } from "react";
import CodeAreaModal from "../../modals/codeAreaModal";
import { CodeAreaComponentType } from "../../types/components";

import IconComponent from "../genericIconComponent";

export default function CodeAreaComponent({
  value,
  onChange,
  disabled,
  editNode = false,
  nodeClass,
  dynamic,
  setNodeClass,
  id = "",
  readonly = false,
  open,
  setOpen,
}: CodeAreaComponentType) {
  const [myValue, setMyValue] = useState(
    typeof value == "string" ? value : JSON.stringify(value),
  );
  useEffect(() => {
    if (disabled && myValue !== "") {
      setMyValue("");
      onChange("", undefined, true);
    }
  }, [disabled]);

  useEffect(() => {
    setMyValue(typeof value == "string" ? value : JSON.stringify(value));
  }, [value]);

  return (
    <div className={disabled ? "pointer-events-none w-full" : "w-full"}>
      <CodeAreaModal
        open={open}
        setOpen={setOpen}
        readonly={readonly}
        dynamic={dynamic}
        value={myValue}
        nodeClass={nodeClass}
        setNodeClass={setNodeClass!}
        setValue={(value: string) => {
          setMyValue(value);
          onChange(value);
        }}
      >
        <div className="flex w-full items-center gap-3">
          <span
            id={id}
            data-testid={id}
            className={
              editNode
                ? "input-edit-node input-dialog"
                : (disabled ? "input-disable input-ring " : "") +
                  " primary-input text-muted-foreground"
            }
          >
            {myValue !== "" ? myValue : "Type something..."}
          </span>
          {!editNode && (
            <IconComponent
              name="ExternalLink"
              className={
                "icons-parameters-comp shrink-0" +
                (disabled ? " text-ring" : " hover:text-accent-foreground")
              }
            />
          )}
        </div>
      </CodeAreaModal>
    </div>
  );
}
