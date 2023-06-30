import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { TextAreaComponentType } from "../../types/components";
import GenericModal from "../../modals/genericModal";
import { TypeModal } from "../../utils";
import { INPUT_DIALOG, INPUT_DISABLE, INPUT_EDIT_NODE, INPUT_STYLE } from "../../constants";
import { ExternalLink } from "lucide-react";

export default function TextAreaComponent({
  value,
  onChange,
  disabled,
  editNode = false,
}: TextAreaComponentType) {
  const [myValue, setMyValue] = useState(value);
  const { openPopUp, closePopUp } = useContext(PopUpContext);

  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);

  useEffect(() => {
    setMyValue(value);
  }, [closePopUp]);

  return (
    <div className={disabled ? "pointer-events-none cursor-not-allowed" : ""}>
      <div
        className={
          editNode
            ? "w-full flex items-center"
            : "w-full flex items-center gap-3"
        }
      >
        <span
          onClick={() => {
            openPopUp(
              <GenericModal
                type={TypeModal.TEXT}
                buttonText="Finishing Editing"
                modalTitle="Edit Text"
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
              : INPUT_DIALOG + "px-3 py-2" +
                (disabled ? INPUT_DISABLE : "")
          }
        >
          {myValue !== "" ? myValue : "Type something..."}
        </span>
        <button
          onClick={() => {
            openPopUp(
              <GenericModal
                type={TypeModal.TEXT}
                buttonText="Finishing Editing"
                modalTitle="Edit Text"
                value={myValue}
                setValue={(t: string) => {
                  setMyValue(t);
                  onChange(t);
                }}
              />
            );
          }}
        >
          {!editNode && <ExternalLink className="w-6 h-6 hover:text-ring " />}
        </button>
      </div>
    </div>
  );
}
