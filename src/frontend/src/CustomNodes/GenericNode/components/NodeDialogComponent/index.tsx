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
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { getCustomParameterTitle } from "@/customization/components/custom-parameter";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { APIClassType, InputFieldType } from "@/types/api";
import { useState } from "react";

interface NodeDialogProps {
  open: boolean;
  onClose: () => void;
  dialogInputs: any;
  nodeId: string;
  name: string;
  nodeClass: APIClassType;
}

interface ValueObject {
  value: string;
}

export const NodeDialog: React.FC<NodeDialogProps> = ({
  open,
  onClose,
  dialogInputs,
  nodeId,
  name,
  nodeClass,
}) => {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const [isLoading, setIsLoading] = useState(false);

  const { fields, functionality } = dialogInputs || {};
  const nodeData = fields?.data?.node;
  const template = nodeData?.template || {};

  const [payloadValues, setPayloadValues] = useState<Record<string, string>>(
    {},
  );

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: nodeClass,
  });

  /**
   * Updates the value for a given field in the node template.
   */
  const updateNodeValue = (value: string | ValueObject, fieldKey: string) => {
    const newValue = typeof value === "object" ? value.value : value;
    const targetNode = nodes.find((node) => node.id === nodeId);
    if (!targetNode || !name) return;

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
    setIsLoading(false);
    onClose();
  };

  const setNodeClass = (newNode: APIClassType) => {
    const targetNode = nodes.find((node) => node.id === nodeId);
    if (!targetNode) return;

    targetNode.data.node = newNode;
    setNode(nodeId, targetNode);
  };

  const handleErrorData = (newState: {
    title: string;
    list?: Array<string>;
  }) => {
    setErrorData(newState);
    setIsLoading(false);
  };

  /**
   * Handles sending the payload state using mutateTemplate.
   */
  const handleSendPayload = async () => {
    setIsLoading(true);

    await mutateTemplate(
      payloadValues,
      nodeClass,
      setNodeClass,
      postTemplateValue,
      handleErrorData,
      name,
      handleCloseDialog,
      nodeClass.tool_mode,
    );
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
          <Button
            variant="default"
            onClick={handleSendPayload}
            loading={isLoading}
          >
            {functionality}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default NodeDialog;
