import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { TextAreaComponentType } from "../../types/components";
import GenericModal from "../../modals/genericModal";
import { TypeModal } from "../../utils";

import { ExternalLink } from "lucide-react";
import { postValidatePrompt } from "../../controllers/API";
import { typesContext } from "../../contexts/typesContext";
import * as _ from "lodash";

export default function PromptAreaComponent({
  setNodeClass,
  nodeClass,
  value,
  onChange,
  disabled,
  editNode = false,
}: TextAreaComponentType) {
  const [myValue, setMyValue] = useState("");
  const { openPopUp } = useContext(PopUpContext);
  const { reactFlowInstance } = useContext(typesContext);

  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);

  useEffect(() => {
    if (value !== "" && myValue !== value && reactFlowInstance) { // only executed once
      setMyValue(value);
      postValidatePrompt(value, nodeClass)
        .then((apiReturn) => {
          if (apiReturn.data) {
            setNodeClass(apiReturn.data.frontend_node);
            // need to update reactFlowInstance to re-render the nodes.
            reactFlowInstance.setEdges(_.cloneDeep(reactFlowInstance.getEdges()));
          }
        })
        .catch((error) => {});
    }
  }, [reactFlowInstance]);

  return (
    <div
      className={
        disabled ? "pointer-events-none w-full cursor-not-allowed" : " w-full"
      }
    >
      <div className="w-full flex items-center">
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
                nodeClass={nodeClass}
                setNodeClass={setNodeClass}
              />
            );
          }}
          className={
            editNode
              ? " input-edit-node " + " input-dialog "
              : (disabled ? " input-disable " : "") + " input-primary " + " input-dialog "
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
                nodeClass={nodeClass}
                setNodeClass={setNodeClass}
              />
            );
          }}
        >
          {!editNode && <ExternalLink strokeWidth={1.5} className="w-6 h-6 hover:text-accent-foreground ml-3" />}
        </button>
      </div>
    </div>
  );
}
