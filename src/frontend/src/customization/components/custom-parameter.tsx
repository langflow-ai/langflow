import type { ComponentProps } from "react";
import { useTranslation } from "react-i18next";
import type { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { ParameterRenderComponent } from "@/components/core/parameterRenderComponent";
import type { NodeInfoType } from "@/components/core/parameterRenderComponent/types";
import { useIsFlowReadOnly } from "@/contexts/permissionsContext";
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
  inspectionPanel: boolean;
  editNode: boolean;
  handleNodeClass: ComponentProps<
    typeof ParameterRenderComponent
  >["handleNodeClass"];
  nodeClass: APIClassType;
  placeholder?: string;
  isToolMode?: boolean;
  nodeInformationMetadata?: NodeInfoType;
  proxy: { field: string; id: string } | undefined;
}) {
  const { t } = useTranslation();
  const edges = useFlowStore((state) => state.edges);
  const currentFlowId = useFlowStore((state) => state.currentFlow?.id);
  const isReadOnly = useIsFlowReadOnly(currentFlowId);

  const disabled =
    edges.some(
      (edge) =>
        edge.targetHandle ===
        scapedJSONStringfy(proxy ? { ...inputId, proxy } : inputId),
    ) || isToolMode;

  return (
    <div
      data-testid="parameter-permission-gate"
      className={cn(
        "w-full min-w-0",
        isReadOnly && "pointer-events-none opacity-60",
      )}
      inert={isReadOnly}
      aria-disabled={isReadOnly}
      title={isReadOnly ? t("version.readOnly") : undefined}
    >
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
        disabled={disabled}
        placeholder={placeholder}
        isToolMode={isToolMode}
        nodeInformationMetadata={nodeInformationMetadata}
      />
    </div>
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
