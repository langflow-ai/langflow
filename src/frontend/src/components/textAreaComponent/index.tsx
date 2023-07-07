import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { TextAreaComponentType } from "../../types/components";
import GenericModal from "../../modals/genericModal";
import { TypeModal, classNames } from "../../utils";

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
    <div className={disabled ? "cursor-not-allowed" : ""}>
      <div
        className={
          (editNode ? "w-full relative top-2" : "flex w-full items-center") +
          (disabled ? " pointer-events-none" : "")
        }
      >

        <input
        value={myValue}
        className={
          editNode
            ? "input-edit-node"
            : "input-primary" + (disabled ? " input-disable " : "")
        }
        placeholder={"Type something..."}
        onChange={(e) => {
          setMyValue(e.target.value);
          onChange(e.target.value);
        }}
      />

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
          {!editNode && (
            <ExternalLink
              strokeWidth={1.5}
              className={
                "ml-3 h-6 w-6" +
                (disabled ? " text-ring" : " hover:text-accent-foreground")
              }
            />
          )}
        </button>
      </div>
    </div>
  );
}
