import { useEffect } from "react";
import GenericModal from "../../modals/genericModal";
import { TextAreaComponentType } from "../../types/components";

import { ExternalLink } from "lucide-react";
import { postValidatePrompt } from "../../controllers/API";

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
        type={"prompt"}
        value={value}
        value={value}
        buttonText="Check & Save"
        modalTitle="Edit Prompt"
        setValue={(t: string) => {
          onChange(t);
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
                  " input-primary text-muted-foreground "
            }
          >
            {value !== "" ? value : "Type your prompt here..."}
          </span>
          {!editNode && (
            <ExternalLink
              strokeWidth={1.5}
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
