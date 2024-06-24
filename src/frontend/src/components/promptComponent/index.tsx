import { useEffect } from "react";

import { TypeModal } from "../../constants/enums";
import GenericModal from "../../modals/genericModal";
import { PromptAreaComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
import { useTranslation } from "react-i18next";

export default function PromptAreaComponent({
  field_name,
  setNodeClass,
  nodeClass,
  value,
  onChange,
  disabled,
  editNode = false,
  id = "",
  readonly = false,
}: PromptAreaComponentType): JSX.Element {
  const { t } = useTranslation();
  useEffect(() => {
    if (disabled && value !== "") {
      onChange("", true);
    }
  }, [disabled]);

  return (
    <div className={disabled ? "pointer-events-none w-full" : "w-full"}>
      <GenericModal
        id={id}
        field_name={field_name}
        readonly={readonly}
        type={TypeModal.PROMPT}
        value={value}
        buttonText="Check & Save"
        modalTitle="Edit Prompt"
        setValue={onChange}
        nodeClass={nodeClass}
        setNodeClass={setNodeClass}
      >
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
              {value !== "" ? value : t("Type your prompt here...")}
            </span>
            {!editNode && (
              <IconComponent
                id={id}
                name="ExternalLink"
                className={
                  "icons-parameters-comp shrink-0" +
                  (disabled ? " text-ring" : " hover:text-accent-foreground")
                }
              />
            )}
          </div>
        </Button>
      </GenericModal>
    </div>
  );
}
