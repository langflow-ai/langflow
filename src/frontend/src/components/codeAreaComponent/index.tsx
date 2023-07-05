import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import CodeAreaModal from "../../modals/codeAreaModal/v2";
import TextAreaModal from "../../modals/textAreaModal";
import { CodeAreaComponentType, TextAreaComponentType } from "../../types/components";


import { ExternalLink } from "lucide-react";

export default function CodeAreaComponent({
  value,
  onChange,
  disabled,
  editNode = false,
  nodeClass,
  setNodeClass,
  dynamic,
}: CodeAreaComponentType) {
  const [myValue, setMyValue] = useState(value);
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
    <div
      className={
        disabled ? "pointer-events-none w-full cursor-not-allowed" : "w-full"
      }
    >
      <div className="flex w-full items-center">
        <span
          onClick={() => {
            openPopUp(
              <CodeAreaModal
                dynamic={dynamic}
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
              ? "input-edit-node input-dialog "
              : "input-primary input-dialog " + (disabled ? "input-disable" : "")
          }
        >
          {myValue !== "" ? myValue : "Type something..."}
        </span>
        <button
          onClick={() => {
            openPopUp(
              <CodeAreaModal
              dynamic={dynamic}
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
            <ExternalLink strokeWidth={1.5} className="w-6 h-6 hover:text-accent-foreground  ml-3" />
          )}
        </button>
      </div>
    </div>
  );
}
