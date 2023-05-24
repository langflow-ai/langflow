import { ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline";
import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import TextAreaModal from "../../modals/textAreaModal";
import { TextAreaComponentType } from "../../types/components";

export default function TextAreaComponent({
  value,
  onChange,
  disabled,
}: TextAreaComponentType) {
  const [myValue, setMyValue] = useState(value);
  const { openPopUp } = useContext(PopUpContext);
  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);
  return (
    <div className={disabled ? "pointer-events-none cursor-not-allowed" : ""}>
      <div className="flex w-full items-center gap-3">
        <span
          onClick={() => {
            openPopUp(
              <TextAreaModal
                value={myValue}
                setValue={(t: string) => {
                  setMyValue(t);
                  onChange(t);
                }}
              />
            );
          }}
          className={
            "block w-full truncate rounded-md border border-gray-300 px-3 py-2 text-gray-500 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:border-gray-700 dark:text-gray-100 sm:text-sm" +
            (disabled ? " bg-gray-200" : "")
          }
        >
          {myValue !== "" ? myValue : "Text empty"}
        </span>
        <button onClick={()=>{openPopUp(<TextAreaModal value={myValue} setValue={(t:string) => {setMyValue(t); onChange(t);}}/>)}}>
            <ArrowTopRightOnSquareIcon className="w-6 h-6 hover:text-blue-600 dark:text-gray-300" />
        </button>
      </div>
    </div>
  );
}
