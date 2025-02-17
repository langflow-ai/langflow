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
  const [isLoading, setIsLoading] = useState(false);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});

  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: nodeClass,
  });

  const { fields, functionality: submitButtonText } = dialogInputs || {};
  const dialogNodeData = fields?.data?.node;
  const dialogTemplate = dialogNodeData?.template || {};

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

  const updateFieldValue = (value: string | ValueObject, fieldKey: string) => {
    const newValue = typeof value === "object" ? value.value : value;
    const targetNode = nodes.find((node) => node.id === nodeId);
    if (!targetNode || !name) return;

    targetNode.data.node.template[name].dialog_inputs.fields.data.node.template[
      fieldKey
    ].value = newValue;
    setNode(nodeId, targetNode);
    setFieldValues((prev) => ({ ...prev, [fieldKey]: newValue }));

    if (dialogTemplate[fieldKey].real_time_refresh) {
      mutateTemplate(
        { [fieldKey]: newValue },
        nodeClass,
        setNodeClass,
        postTemplateValue,
        handleErrorData,
        name,
      );
    }
  };

  const handleCloseDialog = () => {
    setFieldValues({});
    const targetNode = nodes.find((node) => node.id === nodeId);
    if (targetNode && name) {
      const nodeTemplate = targetNode.data.node.template;
      Object.keys(dialogTemplate).forEach((key) => {
        nodeTemplate[name].dialog_inputs.fields.data.node.template[key].value =
          "";
      });
      setNode(nodeId, targetNode);
    }
    setIsLoading(false);
    onClose();
  };

  const handleSubmitDialog = async () => {
    setIsLoading(true);

    await mutateTemplate(
      fieldValues,
      nodeClass,
      setNodeClass,
      postTemplateValue,
      handleErrorData,
      name,
      handleCloseDialog,
      nodeClass.tool_mode,
    );

    setTimeout(() => {
      handleCloseDialog();
    }, 5000);
  };

  // Render
  return (
    <Dialog open={open} onOpenChange={handleCloseDialog}>
      <DialogContent className="max-w-[700px] gap-2 px-1 py-6">
        <DialogHeader className="px-5 pb-3">
          <DialogTitle>
            <div className="flex items-center">
              <span className="pb-2">{dialogNodeData?.display_name}</span>
            </div>
          </DialogTitle>
          <DialogDescription>
            <div className="flex items-center gap-2">
              {dialogNodeData?.description}
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-5 overflow-y-auto px-5">
          {Object.entries(dialogTemplate).map(([fieldKey, fieldValue]) => (
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
                  updateFieldValue(value, fieldKey)
                }
                name={fieldKey}
                nodeId={nodeId}
                templateData={fieldValue as Partial<InputFieldType>}
                templateValue={fieldValues[fieldKey] || ""}
                editNode={false}
                handleNodeClass={() => {}}
                nodeClass={dialogNodeData}
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
            onClick={handleSubmitDialog}
            loading={isLoading}
          >
            {submitButtonText}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default NodeDialog;
