import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import CodeAreaModal from "../../modals/codeAreaModal";
import { TextAreaComponentType } from "../../types/components";

import { ExternalLink } from "lucide-react";

export default function CodeAreaComponent({
  value,
  onChange,
  disabled,
  editNode = false,
  nodeClass,
  setNodeClass,
}: TextAreaComponentType) {
  const [myValue, setMyValue] = useState(
    typeof value == "string" ? value : JSON.stringify(value)
  );
  const { openPopUp } = useContext(PopUpContext);
  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);

  useEffect(() => {
    setMyValue(typeof value == "string" ? value : JSON.stringify(value));
  }, [value]);

  return (
    <div className={disabled ? "pointer-events-none w-full " : " w-full"}>
      <div className="flex w-full items-center">
        <span
          onClick={() => {
            openPopUp(
              <CodeAreaModal
                value={myValue}
                nodeClass={nodeClass}
                setNodeClass={setNodeClass}
                setValue={(t: string) => {
                  setMyValue(t);
                  onChange(t);
                }}
              />
            );
          }}
          className={
            editNode
              ? "input-edit-node input-dialog"
              : (disabled ? " input-disable input-ring " : "") +
                " input-primary text-muted-foreground "
          }
        >
          {myValue !== "" ? myValue : "Type something..."}
        </span>
        <button
          onClick={() => {
            openPopUp(
              <CodeAreaModal
                setNodeClass={setNodeClass}
                value={myValue}
                nodeClass={nodeClass}
                setValue={(t: string) => {
                  setMyValue(t);
                  onChange(t);
                }}
              />
            );
          }}
        >
          {!editNode && (
            <ExternalLink
              strokeWidth={1.5}
              className={
                "icons-parameters-comp" +
                (disabled ? " text-ring" : " hover:text-accent-foreground")
              }
            />
          )}
        </button>
      </div>
    </div>
  );
}
