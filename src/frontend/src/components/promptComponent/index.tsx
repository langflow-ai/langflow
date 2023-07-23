import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import GenericModal from "../../modals/genericModal";
import { TextAreaComponentType } from "../../types/components";
import { TypeModal } from "../../utils";

import { ExternalLink } from "lucide-react";
import { typesContext } from "../../contexts/typesContext";
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
  const [myValue, setMyValue] = useState(value);
  const { openPopUp } = useContext(PopUpContext);
  const { reactFlowInstance } = useContext(typesContext);
  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);

  useEffect(() => {
    setMyValue(value);
    if (value !== "" && !editNode) {
      postValidatePrompt(field_name, value, nodeClass).then((apiReturn) => {
        if (apiReturn.data) {
          setNodeClass(apiReturn.data.frontend_node);
          // need to update reactFlowInstance to re-render the nodes.
        }
      });
    }
  }, [value, reactFlowInstance]);

  // useEffect(() => {
  //   if (value !== "" && myValue !== value && reactFlowInstance) {
  //     // only executed once
  //     setMyValue(value);
  //     postValidatePrompt(field_name, value, nodeClass)
  //       .then((apiReturn) => {
  //         if (apiReturn.data) {
  //           setNodeClass(apiReturn.data.frontend_node);
  //           // need to update reactFlowInstance to re-render the nodes.
  //           reactFlowInstance.setEdges(
  //             _.cloneDeep(reactFlowInstance.getEdges())
  //           );
  //         }
  //       })
  //       .catch((error) => {});
  //   }
  // }, [reactFlowInstance, field_name, myValue, nodeClass, setNodeClass, value]);

  return (
    <div className={disabled ? "pointer-events-none w-full " : " w-full"}>
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
                nodeClass={nodeClass}
                setNodeClass={setNodeClass}
              />
            );
          }}
          className={
            editNode
              ? "input-edit-node input-dialog"
              : (disabled ? " input-disable text-ring " : "") +
                " input-primary text-muted-foreground "
          }
        >
          {myValue !== "" ? myValue : "Type your prompt here"}
        </span>
        <button
          onClick={() => {
            openPopUp(
              <GenericModal
                field_name={field_name}
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
          {!editNode && (
            <ExternalLink
              strokeWidth={1.5}
              className={
                "icons-parameters-comp" +
                (disabled ? " text-ring" : " hover:text-accent-foreground")
              }
            />
          )}
        </button>
      </div>
    </div>
  );
}
