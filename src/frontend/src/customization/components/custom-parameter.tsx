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
  placeholder,
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
  placeholder?: string;
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
      placeholder={placeholder}
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
  return (
    <span
      data-testid={`title-${title.toLocaleLowerCase()}`}
      className="text-[13px]"
    >
      {title}
    </span>
  );
}

export function CustomParameterLabel({
  name,
  nodeId,
  templateValue,
  nodeClass,
}: {
  name: string;
  nodeId: string;
  templateValue: any;
  nodeClass: APIClassType;
}) {
  return <></>;
}
