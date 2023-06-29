import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import CodeAreaModal from "../../modals/codeAreaModal";
import TextAreaModal from "../../modals/textAreaModal";
import { TextAreaComponentType } from "../../types/components";
import { INPUT_STYLE } from "../../constants";
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
        disabled ? "pointer-events-none cursor-not-allowed w-full" : "w-full"
      }
    >
      <div className="w-full flex items-center">
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
              ? "truncate cursor-pointer placeholder:text-center text-gray-500 block w-full pt-0.5 pb-0.5 form-input dark:bg-gray-900 dark:text-gray-300 dark:border-gray-600 rounded-md border-gray-300 border-1 shadow-sm sm:text-sm" +
                INPUT_STYLE
              : "truncate block w-full text-gray-500 px-3 py-2 rounded-md border border-gray-300 dark:border-gray-700 shadow-sm sm:text-sm" +
                INPUT_STYLE +
                (disabled ? " bg-gray-200" : "")
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
            <ExternalLink className="w-6 h-6 hover:text-ring dark:text-gray-300 ml-3" />
          )}
        </button>
      </div>
    </div>
  );
}
