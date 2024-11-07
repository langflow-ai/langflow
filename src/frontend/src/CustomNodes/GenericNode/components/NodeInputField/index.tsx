import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import {
  CustomParameterComponent,
  CustomParameterLabel,
  getCustomParameterTitle,
} from "@/customization/components/custom-parameter";
import { cn } from "@/utils/utils";
import { useEffect, useRef } from "react";
import { default as IconComponent } from "../../../../components/genericIconComponent";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import {
  FLEX_VIEW_TYPES,
  ICON_STROKE_WIDTH,
  LANGFLOW_SUPPORTED_TYPES,
} from "../../../../constants/constants";
import useFlowStore from "../../../../stores/flowStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { NodeInputFieldComponentType } from "../../../../types/components";
import { scapedJSONStringfy } from "../../../../utils/reactflowUtils";
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
  info = "",
  proxy,
  showNode,
  colorName,
}: NodeInputFieldComponentType): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const myData = useTypesStore((state) => state.data);
  const postTemplateValue = usePostTemplateValue({
    node: data.node!,
    nodeId: data.id,
    parameterId: name,
  });
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const { handleNodeClass } = useHandleNodeClass(data.id);

  let disabled =
    edges.some(
      (edge) =>
        edge.targetHandle === scapedJSONStringfy(proxy ? { ...id, proxy } : id),
    ) ?? false;

  const { handleOnNewValue } = useHandleOnNewValue({
    node: data.node!,
    nodeId: data.id,
    name,
  });

  useFetchDataOnMount(data.node!, handleNodeClass, name, postTemplateValue);

  useEffect(() => {
    if (optionalHandle && optionalHandle.length === 0) {
      optionalHandle = null;
    }
  }, [optionalHandle]);

  const displayHandle =
    !LANGFLOW_SUPPORTED_TYPES.has(type ?? "") ||
    (optionalHandle && optionalHandle.length > 0);

  const isFlexView = FLEX_VIEW_TYPES.includes(type ?? "");

  const Handle = (
    <HandleRenderComponent
      left={true}
      nodes={nodes}
      tooltipTitle={tooltipTitle}
      proxy={proxy}
      id={id}
      title={title}
      edges={edges}
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
      className={
        "relative mt-1 flex min-h-10 w-full flex-wrap items-center justify-between px-5 py-2" +
        ((name === "code" && type === "code") ||
        (name.includes("code") && proxy)
          ? " hidden"
          : "")
      }
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
                      isFlexView,
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
                        isFlexView,
                      })}
                    </span>
                  }
                </span>
              </div>
            )}
            <span className={"text-status-red"}>{required ? "*" : ""}</span>
            <div>
              {info !== "" && (
                <ShadTooltip content={<NodeInputInfo info={info} />}>
                  {/* put div to avoid bug that does not display tooltip */}
                  <div className="cursor-help">
                    <IconComponent
                      name="Info"
                      strokeWidth={ICON_STROKE_WIDTH}
                      className="relative bottom-px ml-1 h-3 w-3 text-placeholder"
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
            templateData={data.node?.template[name]!}
            templateValue={data.node?.template[name].value ?? ""}
            editNode={false}
            handleNodeClass={handleNodeClass}
            nodeClass={data.node!}
            disabled={disabled}
          />
        )}
      </div>
    </div>
  );
}
