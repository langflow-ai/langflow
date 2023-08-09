import { useEffect } from "react";

import { TypeModal } from "../../constants/enums";
import { postValidatePrompt } from "../../controllers/API";
import GenericModal from "../../modals/genericModal";
import { TextAreaComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";

export default function PromptAreaComponent({
  field_name,
  setNodeClass,
  nodeClass,
  value,
  onChange,
  disabled,
  editNode = false,
}: TextAreaComponentType) {
  useEffect(() => {
    if (disabled) {
      onChange("");
    }
  }, [disabled]);

  useEffect(() => {
    if (value !== "" && !editNode) {
      postValidatePrompt(field_name, value, nodeClass).then((apiReturn) => {
        if (apiReturn.data) {
          setNodeClass(apiReturn.data.frontend_node);
          // need to update reactFlowInstance to re-render the nodes.
        }
      });
    }
  }, []);

  return (
    <div className={disabled ? "pointer-events-none w-full " : " w-full"}>
      <GenericModal
        type={TypeModal.PROMPT}
        value={value}
        buttonText="Check & Save"
        modalTitle="Edit Prompt"
        setValue={(value: string) => {
          onChange(value);
        }}
        nodeClass={nodeClass}
        setNodeClass={setNodeClass}
      >
        <div className="flex w-full items-center">
          <span
            className={
              editNode
                ? "input-edit-node input-dialog"
                : (disabled ? " input-disable text-ring " : "") +
                  " primary-input text-muted-foreground "
            }
          >
            {value !== "" ? value : "Type your prompt here..."}
          </span>
          {!editNode && (
            <IconComponent
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
