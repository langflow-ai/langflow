import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { TextAreaComponentType } from "../../types/components";
import GenericModal from "../../modals/genericModal";
import { TypeModal } from "../../utils";
import { INPUT_STYLE } from "../../constants";
import { ExternalLink } from "lucide-react";

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
        disabled ? "pointer-events-none w-full cursor-not-allowed" : " w-full"
      }
    >
      <div className="flex w-full items-center">
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
              ? "form-input block w-full cursor-pointer truncate rounded-md border border-ring pb-0.5 pt-0.5   text-ring shadow-sm placeholder:text-center sm:text-sm" +
                INPUT_STYLE
              : "block w-full truncate rounded-md border border-ring px-3 py-2 text-ring shadow-sm sm:text-sm" +
                (disabled ? " bg-input" : "")
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
          {!editNode && <ExternalLink className="h-6 w-6 hover:text-ring " />}
        </button>
      </div>
    </div>
  );
}
