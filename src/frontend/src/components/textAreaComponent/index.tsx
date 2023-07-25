import { useEffect } from "react";
import { TypeModal } from "../../constants/enums";
import GenericModal from "../../modals/genericModal";
import { TextAreaComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";

export default function TextAreaComponent({
  value,
  onChange,
  disabled,
  editNode = false,
}: TextAreaComponentType) {
  // Clear text area
  useEffect(() => {
    if (disabled) {
      onChange("");
    }
  }, [disabled]);

  return (
    <div className={disabled ? "pointer-events-none w-full " : " w-full"}>
      <div className="flex w-full items-center">
        <input
          value={value}
          className={
            (editNode
              ? " input-edit-node "
              : " input-primary " + (disabled ? " input-disable" : "")) +
            " nopan nodrag noundo nocopy w-full"
          }
          placeholder={"Type something..."}
          onChange={(e) => {
            onChange(e.target.value);
          }}
        />
        <div>
          <GenericModal
            type={TypeModal.TEXT}
            buttonText="Finishing Editing"
            modalTitle="Edit Text"
            value={value}
            setValue={(t: string) => {
              onChange(t);
            }}
          >
            {!editNode && (
              <IconComponent
                name="ExternalLink"
                className={
                  "icons-parameters-comp" +
                  (disabled ? " text-ring" : " hover:text-accent-foreground")
                }
              />
            )}
          </GenericModal>
        </div>
      </div>
    </div>
  );
}
