import { useState } from "react";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import type { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
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
import { track } from "@/customization/utils/analytics";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType, InputFieldType } from "@/types/api";

interface NodeDialogProps {
  open: boolean;
  onClose: () => void;
  dialogInputs: any;
  nodeId: string;
  name: string;
  nodeClass: APIClassType;
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
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

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

  const updateFieldValue = (
    changes: Parameters<handleOnNewValueType>[0],
    fieldKey: string,
  ) => {
    // Handle both legacy string format and new object format
    const newValue =
      typeof changes === "object" && changes !== null ? changes.value : changes;

    const targetNode = nodes.find((node) => node.id === nodeId);
    if (!targetNode || !name) return;

    // Update the main field value
    targetNode.data.node.template[name].dialog_inputs.fields.data.node.template[
      fieldKey
    ].value = newValue;

    // Handle additional properties like load_from_db for InputGlobalComponent
    if (typeof changes === "object" && changes !== null) {
      const fieldTemplate =
        targetNode.data.node.template[name].dialog_inputs.fields.data.node
          .template[fieldKey];

      // Update load_from_db if present (for InputGlobalComponent)
      if ("load_from_db" in changes) {
        fieldTemplate.load_from_db = changes.load_from_db;
      }

      // Handle any other properties that might be needed
      Object.keys(changes).forEach((key) => {
        if (key !== "value" && key in fieldTemplate) {
          fieldTemplate[key] = changes[key];
        }
      });
    }

    setNode(nodeId, targetNode);
    setFieldValues((prev) => ({ ...prev, [fieldKey]: newValue }));

    if (dialogTemplate[fieldKey].real_time_refresh) {
      mutateTemplate(
        { [fieldKey]: newValue },
        nodeId,
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

  const handleSuccessCallback = () => {
    // Check if this is a knowledge base creation
    const isKnowledgeBaseCreation =
      dialogNodeData?.display_name === "Create Knowledge" ||
      dialogNodeData?.name === "create_knowledge_base" ||
      (dialogNodeData?.description &&
        dialogNodeData.description.toLowerCase().includes("knowledge"));

    if (isKnowledgeBaseCreation) {
      // Get the knowledge base name from field values
      const knowledgeBaseName =
        fieldValues["01_new_kb_name"] ||
        fieldValues["new_kb_name"] ||
        "Knowledge Base";

      setSuccessData({
        title: `Knowledge Base "${knowledgeBaseName}" created successfully!`,
      });
    }

    // Only close dialog after success and delay for Astra database tracking
    if (nodeId.toLowerCase().includes("astra") && name === "database_name") {
      const {
        cloud_provider: cloudProvider,
        new_database_name: databaseName,
        ...otherFields
      } = fieldValues;
      track("Database Created", {
        nodeId,
        cloudProvider,
        databaseName,
        ...otherFields,
      });

      setTimeout(() => {
        handleCloseDialog();
      }, 5000);
    } else {
      handleCloseDialog();
    }
  };

  const handleSubmitDialog = async () => {
    // Validate required fields first
    const missingRequiredFields = Object.entries(dialogTemplate)
      .filter(
        ([key, fieldValue]) =>
          (fieldValue as { required: boolean })?.required === true &&
          (!fieldValues[key] ||
            (typeof fieldValues[key] === "string" &&
              fieldValues[key].trim() === "")),
      )
      .map(
        ([fieldKey, fieldValue]) =>
          (fieldValue as { display_name: string })?.display_name || fieldKey,
      );

    if (missingRequiredFields.length > 0) {
      handleErrorData({
        title: "Missing required fields",
        list: missingRequiredFields,
      });
      return;
    }

    setIsLoading(true);

    await mutateTemplate(
      fieldValues,
      nodeId,
      nodeClass,
      setNodeClass,
      postTemplateValue,
      handleErrorData,
      name,
      handleSuccessCallback,
      nodeClass.tool_mode,
    );
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
              <div className="flex items-center gap-2">
                {getCustomParameterTitle({
                  title:
                    (fieldValue as { display_name: string })?.display_name ??
                    "",
                  nodeId,
                  isFlexView: false,
                  required:
                    (fieldValue as { required: boolean })?.required ?? false,
                })}
              </div>
              <ParameterRenderComponent
                handleOnNewValue={(changes) =>
                  updateFieldValue(changes, fieldKey)
                }
                name={fieldKey}
                nodeId={nodeId}
                templateData={fieldValue as Partial<InputFieldType>}
                templateValue={(fieldValue as { value: string })?.value ?? ""}
                editNode={false}
                handleNodeClass={() => {}}
                nodeClass={dialogNodeData}
                disabled={
                  (fieldValue as { disabled: boolean })?.disabled ?? false
                }
                placeholder={
                  (fieldValue as { placeholder: string })?.placeholder ?? ""
                }
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
