import { useEffect } from "react";
import { EDIT_TEXT_MODAL_TITLE } from "../../constants/constants";
import { TypeModal } from "../../constants/enums";
import GenericModal from "../../modals/genericModal";
import { Case } from "../../shared/components/caseComponent";
import { TextAreaComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
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
      onChange("", undefined, true);
    }
  }, [disabled]);

  return (
    <div className={"flex w-full items-center " + (disabled ? "" : "")}>
      <div className="flex w-full items-center gap-3" data-testid={"div-" + id}>
        <Case condition={!editNode}>
          <Input
            id={id}
            data-testid={id}
            value={value}
            disabled={disabled}
            className={editNode ? "input-edit-node w-full" : "w-full"}
            placeholder={"Type something..."}
            onChange={(event) => {
              onChange(event.target.value);
            }}
          />
        </Case>
        <GenericModal
          type={TypeModal.TEXT}
          buttonText="Finish Editing"
          modalTitle={EDIT_TEXT_MODAL_TITLE}
          value={value}
          setValue={(value: string) => {
            onChange(value);
          }}
          disabled={disabled}
        >
          {!editNode ? (
            <div className="flex items-center">
              <Button unstyled>
                <IconComponent
                  strokeWidth={1.5}
                  id={id}
                  name="ExternalLink"
                  className={
                    "icons-parameters-comp shrink-0" +
                    (disabled ? " text-ring" : " hover:text-accent-foreground")
                  }
                />
              </Button>
            </div>
          ) : (
            <Button unstyled className="w-full">
              <div className="flex w-full items-center gap-3">
                <span
                  id={id}
                  data-testid={id}
                  className={
                    editNode
                      ? "input-edit-node input-dialog"
                      : (disabled ? "input-disable text-ring " : "") +
                        " primary-input text-muted-foreground"
                  }
                >
                  {value !== "" ? value : "Type something..."}
                </span>
              </div>
            </Button>
          )}
        </GenericModal>
      </div>
    </div>
  );
}
