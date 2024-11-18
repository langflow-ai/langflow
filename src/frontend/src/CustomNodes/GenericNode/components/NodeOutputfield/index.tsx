import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cloneDeep } from "lodash";
import { useEffect, useRef } from "react";
import { useUpdateNodeInternals } from "reactflow";
import { default as IconComponent } from "../../../../components/common/genericIconComponent";
import ShadTooltip from "../../../../components/common/shadTooltipComponent";
import { Button } from "../../../../components/ui/button";
import useFlowStore from "../../../../stores/flowStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { NodeOutputFieldComponentType } from "../../../../types/components";
import {
  getGroupOutputNodeId,
  scapedJSONStringfy,
} from "../../../../utils/reactflowUtils";
import {
  cn,
  logHasMessage,
  logTypeIsError,
  logTypeIsUnknown,
} from "../../../../utils/utils";
import OutputComponent from "../OutputComponent";
import HandleRenderComponent from "../handleRenderComponent";
import OutputModal from "../outputModal";

export default function NodeOutputField({
  selected,
  data,
  title,
  id,
  colors,
  tooltipTitle,
  showNode,
  index,
  type,
  outputName,
  outputProxy,
  lastOutput,
  colorName,
  isToolMode = false,
}: NodeOutputFieldComponentType): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setNode = useFlowStore((state) => state.setNode);
  const myData = useTypesStore((state) => state.data);
  const updateNodeInternals = useUpdateNodeInternals();
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const flowPool = useFlowStore((state) => state.flowPool);

  let flowPoolId = data.id;
  let internalOutputName = outputName;

  if (data.node?.flow && outputProxy) {
    const realOutput = getGroupOutputNodeId(
      data.node.flow,
      outputProxy.name,
      outputProxy.id,
    );
    if (realOutput) {
      flowPoolId = realOutput.id;
      internalOutputName = realOutput.outputName;
    }
  }

  const flowPoolNode = (flowPool[flowPoolId] ?? [])[
    (flowPool[flowPoolId]?.length ?? 1) - 1
  ];

  const displayOutputPreview =
    !!flowPool[flowPoolId] &&
    logHasMessage(flowPoolNode?.data, internalOutputName);

  const unknownOutput = logTypeIsUnknown(
    flowPoolNode?.data,
    internalOutputName,
  );
  const errorOutput = logTypeIsError(flowPoolNode?.data, internalOutputName);

  let disabledOutput =
    edges.some((edge) => edge.sourceHandle === scapedJSONStringfy(id)) ?? false;

  const handleUpdateOutputHide = (value?: boolean) => {
    setNode(data.id, (oldNode) => {
      let newNode = cloneDeep(oldNode);
      newNode.data = {
        ...newNode.data,
        node: {
          ...newNode.data.node,
          outputs: newNode.data.node.outputs?.map((output, i) => {
            if (i === index) {
              output.hidden = value ?? !output.hidden;
            }
            return output;
          }),
        },
      };
      return newNode;
    });
    updateNodeInternals(data.id);
  };

  useEffect(() => {
    if (disabledOutput && data.node?.outputs![index].hidden) {
      handleUpdateOutputHide(false);
    }
  }, [disabledOutput]);

  const Handle = (
    <HandleRenderComponent
      left={false}
      nodes={nodes}
      tooltipTitle={tooltipTitle}
      id={id}
      title={title}
      edges={edges}
      nodeId={data.id}
      myData={myData}
      colors={colors}
      setFilterEdge={setFilterEdge}
      showNode={showNode}
      testIdComplement={`${data?.type?.toLowerCase()}-${showNode ? "shownode" : "noshownode"}`}
      colorName={colorName}
    />
  );

  return !showNode ? (
    <>{Handle}</>
  ) : (
    <div
      ref={ref}
      className={cn(
        "relative mt-1 flex h-11 w-full flex-wrap items-center justify-between bg-muted px-5 py-2",
        lastOutput ? "rounded-b-[0.69rem]" : "",
        isToolMode && "bg-primary",
      )}
    >
      <>
        <div className="flex w-full items-center justify-end truncate text-sm">
          <div className="flex flex-1">
            <Button
              disabled={disabledOutput}
              unstyled
              onClick={() => handleUpdateOutputHide()}
              data-testid={`input-inspection-${title.toLowerCase()}`}
            >
              <ShadTooltip
                content={
                  disabledOutput
                    ? null
                    : data.node?.outputs![index].hidden
                      ? "Show output"
                      : "Hide output"
                }
              >
                <div>
                  <IconComponent
                    className={cn(
                      "icon-size",
                      disabledOutput
                        ? isToolMode
                          ? "text-placeholder-foreground opacity-60"
                          : "text-placeholder-foreground hover:text-foreground"
                        : isToolMode
                          ? "text-background hover:text-secondary-hover"
                          : "text-placeholder-foreground hover:text-primary-hover",
                    )}
                    strokeWidth={ICON_STROKE_WIDTH}
                    name={data.node?.outputs![index].hidden ? "EyeOff" : "Eye"}
                  />
                </div>
              </ShadTooltip>
            </Button>
          </div>

          {data.node?.frozen && (
            <div className="pr-1">
              <IconComponent className="h-5 w-5 text-ice" name={"Snowflake"} />
            </div>
          )}
          <div className="flex items-center gap-2">
            <span className={data.node?.frozen ? "text-ice" : ""}>
              <OutputComponent
                proxy={outputProxy}
                idx={index}
                types={type?.split("|") ?? []}
                selected={
                  data.node?.outputs![index].selected ??
                  data.node?.outputs![index].types[0] ??
                  title
                }
                nodeId={data.id}
                frozen={data.node?.frozen}
                name={title ?? type}
                isToolMode={isToolMode}
              />
            </span>
            <ShadTooltip
              content={
                displayOutputPreview
                  ? unknownOutput
                    ? "Output can't be displayed"
                    : "Inspect output"
                  : "Please build the component first"
              }
            >
              <div className="flex">
                <OutputModal
                  disabled={!displayOutputPreview || unknownOutput}
                  nodeId={flowPoolId}
                  outputName={internalOutputName}
                >
                  <Button
                    disabled={!displayOutputPreview || unknownOutput}
                    data-testid={`output-inspection-${title.toLowerCase()}`}
                    unstyled
                  >
                    {
                      <IconComponent
                        className={cn(
                          "icon-size",
                          isToolMode
                            ? displayOutputPreview && !unknownOutput
                              ? "text-background hover:text-secondary-hover"
                              : "cursor-not-allowed text-placeholder-foreground opacity-80"
                            : displayOutputPreview && !unknownOutput
                              ? "text-foreground hover:text-primary-hover"
                              : "cursor-not-allowed text-placeholder-foreground opacity-60",
                          errorOutput ? "text-destructive" : "",
                        )}
                        name={"ScanEye"}
                        strokeWidth={ICON_STROKE_WIDTH}
                      />
                    }
                  </Button>
                </OutputModal>
              </div>
            </ShadTooltip>
          </div>
        </div>
        {Handle}
      </>
    </div>
  );
}
