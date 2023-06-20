import { ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline";
import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { TextAreaComponentType } from "../../types/components";
import GenericModal from "../../modals/genericModal";
import { TypeModal } from "../../utils";
import { INPUT_STYLE } from "../../constants";

export default function PromptAreaComponent({
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
        disabled ? "pointer-events-none cursor-not-allowed w-full" : " w-full"
      }
    >
      <div className="w-full flex items-center gap-3">
        <span
          onClick={() => {
            openPopUp(
              <GenericModal
                type={TypeModal.PROMPT}
                value={myValue}
                buttonText="Check & Save"
                modalTitle="Edit Prompt"
                setValue={(t: string) => {
                  setMyValue(t);
                  onChange(t);
                }}
              />
            );
          }}
          className={
            editNode
              ? "cursor-pointer truncate placeholder:text-center text-medium-gray border-1 block w-full pt-0.5 pb-0.5 form-input dark:bg-high-dark-gray dark:text-medium-low-gray dark:border-medium-dark-gray rounded-md border-medium-low-gray shadow-sm sm:text-sm" +
                INPUT_STYLE
              : "truncate block w-full text-medium-gray px-3 py-2 rounded-md border border-medium-low-gray dark:border-almost-dark-gray shadow-sm sm:text-sm" +
                (disabled ? " bg-light-gray" : "")
          }
        >
          {myValue !== "" ? myValue : "Type your prompt here"}
        </span>
        <button
          onClick={() => {
            openPopUp(
              <GenericModal
                type={TypeModal.PROMPT}
                value={myValue}
                buttonText="Check & Save"
                modalTitle="Edit Prompt"
                setValue={(t: string) => {
                  setMyValue(t);
                  onChange(t);
                }}
              />
            );
          }}
        >
          {!editNode && (
            <ArrowTopRightOnSquareIcon className="w-6 h-6 hover:text-ring dark:text-medium-low-gray" />
          )}
        </button>
      </div>
    </div>
  );
}
