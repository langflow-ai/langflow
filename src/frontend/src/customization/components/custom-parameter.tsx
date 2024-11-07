import { ParameterRenderComponent } from "@/components/parameterRenderComponent";
import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { APIClassType, InputFieldType } from "@/types/api";
import { cn } from "@/utils/utils";

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
  isFlexView,
}: {
  title: string;
  isFlexView: boolean;
}) {
  return (
    <div className={cn(isFlexView && "max-w-56 truncate")}>
      <span
        data-testid={`title-${title.toLocaleLowerCase()}`}
        className="text-[13px]"
      >
        {title}
      </span>
    </div>
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
