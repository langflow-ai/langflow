import { useCallback, useMemo } from "react";
import { AssistantButton } from "@/components/common/assistant";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  CustomParameterComponent,
  CustomParameterLabel,
  getCustomParameterTitle,
} from "@/customization/components/custom-parameter";
import { LANGFLOW_AGENTIC_EXPERIENCE } from "@/customization/feature-flags";
import { useIsAutoLogin } from "@/hooks/use-is-auto-login";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import type { NodeInputFieldComponentType } from "@/types/components";
import { cn } from "@/utils/utils";
import {
  DEFAULT_TOOLSET_PLACEHOLDER,
  FLEX_VIEW_TYPES,
  ICON_STROKE_WIDTH,
} from "@/constants/constants";
import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import NodeInputInfo from "@/CustomNodes/GenericNode/components/NodeInputInfo";

interface InspectionPanelFieldProps
  extends Omit<
    NodeInputFieldComponentType,
    | "colors"
    | "tooltipTitle"
    | "type"
    | "optionalHandle"
    | "colorName"
    | "lastInput"
  > {
  showAdvanced?: boolean;
}

export default function InspectionPanelField({
  id,
  data,
  title,
  name = "",
  required = false,
  info = "",
  showNode,
  isToolMode = false,
  proxy,
  showAdvanced = false,
}: InspectionPanelFieldProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isAutoLogin = useIsAutoLogin();
  const shouldDisplayApiKey = isAuthenticated && !isAutoLogin;

  const { currentFlowId, currentFlowName } = useFlowStore((state) => ({
    currentFlowId: state.currentFlow?.id,
    currentFlowName: state.currentFlow?.name,
  }));

  const { handleNodeClass } = useHandleNodeClass(data.id);

  const { handleOnNewValue } = useHandleOnNewValue({
    node: data.node!,
    nodeId: data.id,
    name,
  });

  const nodeInformationMetadata = useMemo(() => {
    return {
      flowId: currentFlowId ?? "",
      nodeType: data?.type?.toLowerCase() ?? "",
      flowName: currentFlowName ?? "",
      isAuth: shouldDisplayApiKey!,
      variableName: name,
    };
  }, [data?.node?.id, shouldDisplayApiKey, name]);

  const template = data.node?.template[name];
  const type = template?.type;
  const isFlexView = FLEX_VIEW_TYPES.includes(type ?? "");
  const isAdvanced = template?.advanced ?? false;

  const handleToggleVisibility = useCallback(() => {
    handleOnNewValue({ advanced: !isAdvanced });
  }, [handleOnNewValue, isAdvanced]);

  return (
    <div
      className={cn(
        "relative flex min-h-10 w-full flex-wrap items-center justify-between px-3 py-1.5",
        isToolMode && "bg-primary/10",
        (name === "code" && type === "code") || (name.includes("code") && proxy)
          ? "hidden"
          : "",
      )}
    >
      <div
        className={cn(
          "flex w-full flex-col gap-2",
          isFlexView ? "flex-row" : "flex-col",
        )}
      >
        <div className="flex w-full items-center justify-between text-sm">
          <div className="flex w-full items-center truncate">
            {proxy ? (
              <ShadTooltip content={<span>{proxy.id}</span>}>
                <span>
                  {getCustomParameterTitle({
                    title,
                    nodeId: data.id,
                    isFlexView,
                    required,
                    inspectionPanel: true,
                  })}
                </span>
              </ShadTooltip>
            ) : (
              <div className="flex gap-2">
                <span className="text-sm font-medium">
                  {getCustomParameterTitle({
                    title,
                    nodeId: data.id,
                    isFlexView,
                    required,
                    inspectionPanel: true,
                  })}
                </span>
              </div>
            )}
            <div className="flex items-center">
              {info !== "" && (
                <ShadTooltip content={<NodeInputInfo info={info} />}>
                  <div className="cursor-help">
                    <IconComponent
                      name="Info"
                      strokeWidth={ICON_STROKE_WIDTH}
                      className="relative ml-1 h-3 w-3 text-placeholder"
                    />
                  </div>
                </ShadTooltip>
              )}
              {showAdvanced && (
                <ShadTooltip content="Add to canvas">
                  <button
                    className="ml-1 cursor-pointer text-placeholder hover:text-foreground"
                    onClick={handleToggleVisibility}
                    data-testid={"promote-" + name}
                  >
                    <IconComponent
                      name="Plus"
                      strokeWidth={ICON_STROKE_WIDTH}
                      className="h-3 w-3"
                    />
                  </button>
                </ShadTooltip>
              )}
            </div>
            {LANGFLOW_AGENTIC_EXPERIENCE &&
              data.node?.template[name]?.ai_enabled && (
                <AssistantButton
                  compData={id}
                  handleOnNewValue={handleOnNewValue}
                  inputValue={data.node?.template[name]?.value}
                  type="field"
                />
              )}
          </div>
          <CustomParameterLabel
            name={name}
            nodeId={data.id}
            templateValue={data.node?.template[name]}
            nodeClass={data.node!}
          />
        </div>

        {data.node?.template[name] !== undefined && (
          <CustomParameterComponent
            handleOnNewValue={handleOnNewValue}
            name={name}
            nodeId={data.id}
            inputId={id}
            templateData={data.node?.template[name]!}
            templateValue={data.node?.template[name].value ?? ""}
            editNode={false}
            handleNodeClass={handleNodeClass}
            nodeClass={data.node!}
            showParameter={true}
            inspectionPanel={true}
            placeholder={
              isToolMode
                ? DEFAULT_TOOLSET_PLACEHOLDER
                : data.node?.template[name].placeholder
            }
            isToolMode={isToolMode}
            nodeInformationMetadata={nodeInformationMetadata}
            proxy={proxy}
          />
        )}
      </div>
    </div>
  );
}
