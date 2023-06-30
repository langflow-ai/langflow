import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import CodeAreaModal from "../../modals/codeAreaModal";
import TextAreaModal from "../../modals/textAreaModal";
import { TextAreaComponentType } from "../../types/components";
import {
  INPUT_DIALOG,
  INPUT_DISABLE,
  INPUT_EDIT_NODE,
  INPUT_STYLE,
} from "../../constants";
import { ExternalLink } from "lucide-react";

export default function CodeAreaComponent({
  value,
  onChange,
  disabled,
  editNode = false,
}: TextAreaComponentType) {
  const [myValue, setMyValue] = useState(value);
  const { openPopUp } = useContext(PopUpContext);
  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);

  useEffect(() => {
    setMyValue(value);
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
                value={myValue}
                setValue={(t: string) => {
                  setMyValue(t);
                  onChange(t);
                }}
              />
            );
          }}
          className={
            editNode
              ? INPUT_EDIT_NODE + INPUT_DIALOG
              : INPUT_STYLE + INPUT_DIALOG + (disabled ? INPUT_DISABLE : "")
          }
        >
          {myValue !== "" ? myValue : "Type something..."}
        </span>
        <button
          onClick={() => {
            openPopUp(
              <CodeAreaModal
                value={myValue}
                setValue={(t: string) => {
                  setMyValue(t);
                  onChange(t);
                }}
              />
            );
          }}
        >
          {!editNode && (
            <ExternalLink className="ml-3 h-6 w-6  hover:text-ring" />
          )}
        </button>
      </div>
    </div>
  );
}
