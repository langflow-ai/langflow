import { useMemo } from "react";
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
import { useTypesStore } from "@/stores/typesStore";
import type { NodeInputFieldComponentType } from "@/types/components";
import { cn } from "@/utils/utils";
import {
  DEFAULT_TOOLSET_PLACEHOLDER,
  FLEX_VIEW_TYPES,
  ICON_STROKE_WIDTH,
} from "@/constants/constants";
import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import useFetchDataOnMount from "@/CustomNodes/hooks/use-fetch-data-on-mount";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import NodeInputInfo from "@/CustomNodes/GenericNode/components/NodeInputInfo";

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
}: Omit<
  NodeInputFieldComponentType,
  | "colors"
  | "tooltipTitle"
  | "type"
  | "optionalHandle"
  | "colorName"
  | "lastInput"
>) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isAutoLogin = useIsAutoLogin();
  const shouldDisplayApiKey = isAuthenticated && !isAutoLogin;

  const { currentFlowId, currentFlowName } = useFlowStore((state) => ({
    currentFlowId: state.currentFlow?.id,
    currentFlowName: state.currentFlow?.name,
  }));

  const myData = useTypesStore((state) => state.data);
  const postTemplateValue = usePostTemplateValue({
    node: data.node!,
    nodeId: data.id,
    parameterId: name,
  });

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

  useFetchDataOnMount(
    data.node!,
    data.id,
    handleNodeClass,
    name,
    postTemplateValue,
  );

  const template = data.node?.template[name];
  const type = template?.type;
  const isFlexView = FLEX_VIEW_TYPES.includes(type ?? "");

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
                  })}
                </span>
              </div>
            )}
            <div>
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

// Made with Bob
