import { ParameterRenderComponent } from "@/components/core/parameterRenderComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getCustomParameterTitle } from "@/customization/components/custom-parameter";
import useFlowStore from "@/stores/flowStore";
import { InputFieldType } from "@/types/api";
import { useState } from "react";

interface NodeDialogProps {
  open: boolean;
  onClose: () => void;
  dialogInputs: any;
  nodeId: string;
  name: string;
}

// Add back the ValueObject interface
interface ValueObject {
  value: string;
}

export const NodeDialog: React.FC<NodeDialogProps> = ({
  open,
  onClose,
  dialogInputs,
  nodeId,
  name,
}) => {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);

  // Destructure to avoid deep optional chaining
  const { fields, functionality } = dialogInputs || {};
  const nodeData = fields?.data?.node;
  const template = nodeData?.template || {};

  const [payloadValues, setPayloadValues] = useState<Record<string, string>>(
    {},
  );

  /**
   * Updates the value for a given field in the node template.
   */
  const updateNodeValue = (value: string | ValueObject, fieldKey: string) => {
    const newValue = typeof value === "object" ? value.value : value;
    const targetNode = nodes.find((node) => node.id === nodeId);
    if (!targetNode || !name) return;

    // Update the value in the node's template
    targetNode.data.node.template[name].dialog_inputs.fields.data.node.template[
      fieldKey
    ].value = newValue;
    setNode(nodeId, targetNode);
    setPayloadValues((prev) => ({ ...prev, [fieldKey]: newValue }));
  };

  /**
   * Resets all values and closes the dialog.
   */
  const handleCloseDialog = () => {
    setPayloadValues({});
    const targetNode = nodes.find((node) => node.id === nodeId);
    if (targetNode && name) {
      const nodeTemplate = targetNode.data.node.template;
      Object.keys(template).forEach((key) => {
        nodeTemplate[name].dialog_inputs.fields.data.node.template[key].value =
          "";
      });
      setNode(nodeId, targetNode);
    }
    onClose();
  };

  /**
   * Handles sending the payload state using mutateTemplate.
   */
  const handleSendPayload = () => {
    console.log(payloadValues);

    handleCloseDialog();
  };

  return (
    <Dialog open={open} onOpenChange={handleCloseDialog}>
      <DialogContent className="max-w-[700px] gap-2 px-1 py-6">
        <DialogHeader className="px-5 pb-3">
          <DialogTitle>
            <div className="flex items-center">
              <span className="pb-2">{nodeData?.display_name}</span>
            </div>
          </DialogTitle>
          <DialogDescription>
            <div className="flex items-center gap-2">
              {nodeData?.description}
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-5 overflow-y-auto px-5">
          {Object.entries(template).map(([fieldKey, fieldValue]) => (
            <div key={fieldKey}>
              <div>
                {getCustomParameterTitle({
                  title:
                    (fieldValue as { display_name: string })?.display_name ??
                    "",
                  nodeId,
                  isFlexView: false,
                })}
              </div>
              <ParameterRenderComponent
                handleOnNewValue={(value: string) =>
                  updateNodeValue(value, fieldKey)
                }
                name={fieldKey}
                nodeId={nodeId}
                templateData={fieldValue as Partial<InputFieldType>}
                templateValue={payloadValues[fieldKey] || ""}
                editNode={false}
                handleNodeClass={() => {}}
                nodeClass={nodeData}
                disabled={false}
                placeholder=""
                isToolMode={false}
              />
            </div>
          ))}
        </div>

        <DialogFooter className="px-5 pt-3">
          <Button variant="secondary" onClick={handleCloseDialog}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSendPayload}>
            {functionality}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default NodeDialog;
