import { ParameterRenderComponent } from "@/components/parameterRenderComponent";
import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { APIClassType, InputFieldType } from "@/types/api";

export function CustomParameterComponent({
  handleOnNewValue,
  name,
  nodeId,
  templateData,
  templateValue,
  editNode,
  handleNodeClass,
  nodeClass,
  disabled,
}: {
  handleOnNewValue: handleOnNewValueType;
  name: string;
  nodeId: string;
  templateData: Partial<InputFieldType>;
  templateValue: any;
  editNode: boolean;
  handleNodeClass: (value: any, code?: string, type?: string) => void;
  nodeClass: APIClassType;
  disabled: boolean;
}) {
  return (
    <ParameterRenderComponent
      handleOnNewValue={handleOnNewValue}
      name={name}
      nodeId={nodeId}
      templateData={templateData}
      templateValue={templateValue}
      editNode={editNode}
      handleNodeClass={handleNodeClass}
      nodeClass={nodeClass}
      disabled={disabled}
    />
  );
}

export function getCustomParameterTitle({
  title,
  nodeId,
}: {
  title: string;
  nodeId: string;
}) {
  return title;
}
