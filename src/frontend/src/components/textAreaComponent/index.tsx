import { useEffect } from "react";
import { TypeModal } from "../../constants/enums";
import GenericModal from "../../modals/genericModal";
import { TextAreaComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";
import { Input } from "../ui/input";

export default function TextAreaComponent({
  value,
  onChange,
  disabled,
  editNode = false,
  id = "",
}: TextAreaComponentType): JSX.Element {
  // Clear text area
  useEffect(() => {
    if (disabled && value !== "") {
      onChange("");
    }
  }, [disabled]);

  return (
    <div
      className={
        "flex w-full items-center " + (disabled ? "pointer-events-none" : "")
      }
    >
      <GenericModal
        type={TypeModal.TEXT}
        buttonText="Finishing Editing"
        modalTitle="Edit Text"
        value={value}
        setValue={(value: string) => {
          onChange(value);
        }}
      >
        <div className="flex w-full items-center" data-testid={"div-" + id}>
          <Input
            id={id}
            data-testid={id}
            value={value}
            disabled={disabled}
            className={
              editNode
                ? "input-edit-node pointer-events-none "
                : " pointer-events-none"
            }
            placeholder={"Type something..."}
            onChange={(event) => {
              onChange(event.target.value);
            }}
          />
          {!editNode && (
            <IconComponent
              id={id}
              name="ExternalLink"
              className={
                "icons-parameters-comp" +
                (disabled ? " text-ring" : " hover:text-accent-foreground")
              }
            />
          )}
        </div>
      </GenericModal>
    </div>
  );
}
