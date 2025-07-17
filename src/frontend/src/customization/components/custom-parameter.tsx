import type { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { ParameterRenderComponent } from "@/components/core/parameterRenderComponent";
import type { NodeInfoType } from "@/components/core/parameterRenderComponent/types";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType, InputFieldType } from "@/types/api";
import type { targetHandleType } from "@/types/flow";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";

export function CustomParameterComponent({
  handleOnNewValue,
  name,
  nodeId,
  inputId,
  templateData,
  templateValue,
  editNode,
  handleNodeClass,
  nodeClass,
  placeholder,
  isToolMode = false,
  nodeInformationMetadata,
  proxy,
}: {
  handleOnNewValue: handleOnNewValueType;
  name: string;
  nodeId: string;
  inputId: targetHandleType;
  templateData: Partial<InputFieldType>;
  templateValue: any;
  editNode: boolean;
  handleNodeClass: (value: any, code?: string, type?: string) => void;
  nodeClass: APIClassType;
  placeholder?: string;
  isToolMode?: boolean;
  nodeInformationMetadata?: NodeInfoType;
  proxy: { field: string; id: string } | undefined;
}) {
  const edges = useFlowStore((state) => state.edges);

  const disabled =
    edges.some(
      (edge) =>
        edge.targetHandle ===
        scapedJSONStringfy(proxy ? { ...inputId, proxy } : inputId),
    ) || isToolMode;

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
      isToolMode={isToolMode}
      nodeInformationMetadata={nodeInformationMetadata}
    />
  );
}

export function getCustomParameterTitle({
  title,
  nodeId,
  isFlexView,
  required,
}: {
  title: string;
  nodeId: string;
  isFlexView: boolean;
  required?: boolean;
}) {
  return (
    <div className={cn(isFlexView && "max-w-56 truncate")}>
      <span
        data-testid={`title-${title.toLocaleLowerCase()}`}
        className="text-mmd"
      >
        {title}
      </span>
      {required && <span className="text-red-500">*</span>}
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
