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
  showParameter,
  inspectionPanel = false,
  editNode,
  handleNodeClass,
  nodeClass,
  nodeType,
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
  templateValue: unknown;
  showParameter: boolean;
  inspectionPanel?: boolean;
  editNode: boolean;
  handleNodeClass: (value: unknown, code?: string, type?: string) => void;
  nodeClass: APIClassType;
  nodeType?: string;
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
      showParameter={showParameter}
      inspectionPanel={inspectionPanel}
      handleNodeClass={handleNodeClass}
      nodeClass={nodeClass}
      nodeType={nodeType}
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
  inspectionPanel,
}: {
  title: string;
  nodeId: string;
  isFlexView: boolean;
  required?: boolean;
  inspectionPanel?: boolean;
}) {
  return (
    <div className={cn(isFlexView && "max-w-56 truncate")}>
      <span
        data-testid={`title-${title.toLocaleLowerCase()}`}
        className={cn(
          inspectionPanel
            ? "text-xs font-medium"
            : "text-sm text-secondary-foreground",
        )}
      >
        {title}
      </span>
      {required && <span className="text-destructive">*</span>}
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
  templateValue: unknown;
  nodeClass: APIClassType;
}) {
  return <></>;
}
