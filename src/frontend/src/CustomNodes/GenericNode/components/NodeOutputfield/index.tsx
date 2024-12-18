import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cloneDeep } from "lodash";
import { memo, useCallback, useEffect, useMemo, useRef } from "react";
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

// Memoize IconComponent instances
const EyeIcon = memo(
  ({ hidden, className }: { hidden: boolean; className: string }) => (
    <IconComponent
      className={className}
      strokeWidth={ICON_STROKE_WIDTH}
      name={hidden ? "EyeOff" : "Eye"}
    />
  ),
);

const SnowflakeIcon = memo(() => (
  <IconComponent className="h-5 w-5 text-ice" name="Snowflake" />
));

const ScanEyeIcon = memo(({ className }: { className: string }) => (
  <IconComponent
    className={className}
    name="ScanEye"
    strokeWidth={ICON_STROKE_WIDTH}
  />
));

// Memoize Button components
const HideShowButton = memo(
  ({
    disabled,
    onClick,
    hidden,
    isToolMode,
    title,
  }: {
    disabled: boolean;
    onClick: () => void;
    hidden: boolean;
    isToolMode: boolean;
    title: string;
  }) => (
    <Button
      disabled={disabled}
      unstyled
      onClick={onClick}
      data-testid={`input-inspection-${title.toLowerCase()}`}
    >
      <ShadTooltip
        content={disabled ? null : hidden ? "Show output" : "Hide output"}
      >
        <div>
          <EyeIcon
            hidden={hidden}
            className={cn(
              "icon-size",
              disabled
                ? isToolMode
                  ? "text-placeholder-foreground opacity-60"
                  : "text-placeholder-foreground hover:text-foreground"
                : isToolMode
                  ? "text-background hover:text-secondary-hover"
                  : "text-placeholder-foreground hover:text-primary-hover",
            )}
          />
        </div>
      </ShadTooltip>
    </Button>
  ),
);

const InspectButton = memo(
  ({
    disabled,
    displayOutputPreview,
    unknownOutput,
    errorOutput,
    isToolMode,
    title,
    onClick,
  }: {
    disabled: boolean | undefined;
    displayOutputPreview: boolean;
    unknownOutput: boolean | undefined;
    errorOutput: boolean;
    isToolMode: boolean;
    title: string;
    onClick: () => void;
  }) => (
    <Button
      disabled={disabled}
      data-testid={`output-inspection-${title.toLowerCase()}`}
      unstyled
      onClick={onClick}
    >
      <ScanEyeIcon
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
      />
    </Button>
  ),
);

const MemoizedOutputComponent = memo(OutputComponent);

function NodeOutputField({
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
  const updateNodeInternals = useUpdateNodeInternals();

  // Use selective store subscriptions
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setNode = useFlowStore((state) => state.setNode);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const flowPool = useFlowStore((state) => state.flowPool);
  const myData = useTypesStore((state) => state.data);

  // Memoize computed values
  const { flowPoolId, internalOutputName } = useMemo(() => {
    if (data.node?.flow && outputProxy) {
      const realOutput = getGroupOutputNodeId(
        data.node.flow,
        outputProxy.name,
        outputProxy.id,
      );
      if (realOutput) {
        return {
          flowPoolId: realOutput.id,
          internalOutputName: realOutput.outputName,
        };
      }
    }
    return { flowPoolId: data.id, internalOutputName: outputName };
  }, [data.id, data.node?.flow, outputProxy, outputName]);

  const flowPoolNode = useMemo(() => {
    const pool = flowPool[flowPoolId] ?? [];
    return pool[pool.length - 1];
  }, [flowPool, flowPoolId]);

  const { displayOutputPreview, unknownOutput, errorOutput } = useMemo(
    () => ({
      displayOutputPreview:
        !!flowPool[flowPoolId] &&
        logHasMessage(flowPoolNode?.data, internalOutputName),
      unknownOutput: logTypeIsUnknown(flowPoolNode?.data, internalOutputName),
      errorOutput: logTypeIsError(flowPoolNode?.data, internalOutputName),
    }),
    [flowPool, flowPoolId, flowPoolNode?.data, internalOutputName],
  );

  const disabledOutput = useMemo(
    () => edges.some((edge) => edge.sourceHandle === scapedJSONStringfy(id)),
    [edges, id],
  );

  const handleUpdateOutputHide = useCallback(
    (value?: boolean) => {
      setNode(data.id, (oldNode) => {
        const newNode = cloneDeep(oldNode);
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
    },
    [data.id, index, setNode, updateNodeInternals],
  );

  useEffect(() => {
    if (disabledOutput && data.node?.outputs![index].hidden) {
      handleUpdateOutputHide(false);
    }
  }, [disabledOutput, data.node?.outputs, handleUpdateOutputHide, index]);

  const Handle = useMemo(
    () => (
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
    ),
    [
      nodes,
      tooltipTitle,
      id,
      title,
      edges,
      data.id,
      myData,
      colors,
      setFilterEdge,
      showNode,
      data?.type,
      colorName,
    ],
  );

  if (!showNode) return <>{Handle}</>;

  return (
    <div
      ref={ref}
      className={cn(
        "relative mt-1 flex h-11 w-full flex-wrap items-center justify-between bg-muted px-5 py-2",
        lastOutput ? "rounded-b-[0.69rem]" : "",
        isToolMode && "bg-primary",
      )}
    >
      <div className="flex w-full items-center justify-end truncate text-sm">
        <div className="flex flex-1">
          <HideShowButton
            disabled={disabledOutput}
            onClick={() => handleUpdateOutputHide()}
            hidden={!!data.node?.outputs![index].hidden}
            isToolMode={isToolMode}
            title={title}
          />
        </div>

        {data.node?.frozen && (
          <div className="pr-1">
            <SnowflakeIcon />
          </div>
        )}

        <div className="flex items-center gap-2">
          <span className={data.node?.frozen ? "text-ice" : ""}>
            <MemoizedOutputComponent
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
                <InspectButton
                  disabled={!displayOutputPreview || unknownOutput}
                  displayOutputPreview={displayOutputPreview}
                  unknownOutput={unknownOutput ?? false}
                  errorOutput={errorOutput ?? false}
                  isToolMode={isToolMode}
                  title={title}
                  onClick={() => {
                    //just to trigger the memoization
                  }}
                />
              </OutputModal>
            </div>
          </ShadTooltip>
        </div>
      </div>
      {Handle}
    </div>
  );
}

export default memo(NodeOutputField);
