import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import { NodeInfoType } from "@/components/core/parameterRenderComponent/types";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import {
  CustomParameterComponent,
  CustomParameterLabel,
  getCustomParameterTitle,
} from "@/customization/components/custom-parameter";
import { useIsAutoLogin } from "@/hooks/use-is-auto-login";
import useAuthStore from "@/stores/authStore";
import { cn } from "@/utils/utils";
import { useEffect, useMemo, useRef } from "react";
import { useShallow } from "zustand/react/shallow";
import { default as IconComponent } from "../../../../components/common/genericIconComponent";
import ShadTooltip from "../../../../components/common/shadTooltipComponent";
import {
  DEFAULT_TOOLSET_PLACEHOLDER,
  FLEX_VIEW_TYPES,
  ICON_STROKE_WIDTH,
  IS_AUTO_LOGIN,
  LANGFLOW_SUPPORTED_TYPES,
} from "../../../../constants/constants";
import useFlowStore from "../../../../stores/flowStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { NodeInputFieldComponentType } from "../../../../types/components";
import useFetchDataOnMount from "../../../hooks/use-fetch-data-on-mount";
import useHandleOnNewValue from "../../../hooks/use-handle-new-value";
import NodeInputInfo from "../NodeInputInfo";
import HandleRenderComponent from "../handleRenderComponent";

export default function NodeInputField({
  id,
  data,
  tooltipTitle,
  title,
  colors,
  type,
  name = "",
  required = false,
  optionalHandle = null,
  lastInput = false,
  info = "",
  proxy,
  showNode,
  colorName,
  isToolMode = false,
}: NodeInputFieldComponentType): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isAutoLogin = useIsAutoLogin();
  const shouldDisplayApiKey = isAuthenticated && !isAutoLogin;

  const { currentFlowId, currentFlowName } = useFlowStore(
    useShallow((state) => ({
      currentFlowId: state.currentFlow?.id,
      currentFlowName: state.currentFlow?.name,
    })),
  );

  const myData = useTypesStore((state) => state.data);
  const postTemplateValue = usePostTemplateValue({
    node: data.node!,
    nodeId: data.id,
    parameterId: name,
  });
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const { handleNodeClass } = useHandleNodeClass(data.id);

  const { handleOnNewValue } = useHandleOnNewValue({
    node: data.node!,
    nodeId: data.id,
    name,
  });

  const hasRefreshButton = useMemo(() => {
    return data.node?.template[name]?.refresh_button;
  }, [data.node?.template, name]);

  const nodeInformationMetadata: NodeInfoType = useMemo(() => {
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

  useEffect(() => {
    if (optionalHandle && optionalHandle.length === 0) {
      optionalHandle = null;
    }
  }, [optionalHandle]);

  const displayHandle =
    (!LANGFLOW_SUPPORTED_TYPES.has(type ?? "") ||
      (optionalHandle && optionalHandle.length > 0)) &&
    !isToolMode &&
    !hasRefreshButton;

  const isFlexView = FLEX_VIEW_TYPES.includes(type ?? "");

  const Handle = (
    <HandleRenderComponent
      left={true}
      tooltipTitle={tooltipTitle}
      proxy={proxy}
      id={id}
      title={title}
      myData={myData}
      colors={colors}
      setFilterEdge={setFilterEdge}
      showNode={showNode}
      testIdComplement={`${data?.type?.toLowerCase()}-${showNode ? "shownode" : "noshownode"}`}
      nodeId={data.id}
      colorName={colorName}
    />
  );

  return !showNode ? (
    displayHandle ? (
      Handle
    ) : (
      <></>
    )
  ) : (
    <div
      ref={ref}
      className={cn(
        "relative flex min-h-10 w-full flex-wrap items-center justify-between px-5 py-2",
        lastInput ? "rounded-b-[0.69rem] pb-5" : "",
        isToolMode && "bg-primary/10",
        (name === "code" && type === "code") || (name.includes("code") && proxy)
          ? "hidden"
          : "",
      )}
    >
      {displayHandle && Handle}
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
                {
                  <span>
                    {getCustomParameterTitle({
                      title,
                      nodeId: data.id,
                      isFlexView,
                      required,
                    })}
                  </span>
                }
              </ShadTooltip>
            ) : (
              <div className="flex gap-2">
                <span>
                  {
                    <span className="text-sm font-medium">
                      {getCustomParameterTitle({
                        title,
                        nodeId: data.id,
                        isFlexView,
                        required,
                      })}
                    </span>
                  }
                </span>
              </div>
            )}
            <div>
              {info !== "" && (
                <ShadTooltip content={<NodeInputInfo info={info} />}>
                  {/* put div to avoid bug that does not display tooltip */}
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
