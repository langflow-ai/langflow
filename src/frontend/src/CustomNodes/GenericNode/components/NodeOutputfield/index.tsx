import { useUpdateNodeInternals } from '@xyflow/react';
import { cloneDeep } from 'lodash';
import {
  forwardRef,
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useHotkeys } from 'react-hotkeys-hook';
import { Badge } from '@/components/ui/badge';
import { ICON_STROKE_WIDTH } from '@/constants/constants';
import { useShortcutsStore } from '@/stores/shortcuts';
import ForwardedIconComponent, {
  default as IconComponent,
} from '../../../../components/common/genericIconComponent';
import ShadTooltip from '../../../../components/common/shadTooltipComponent';
import { Button } from '../../../../components/ui/button';
import useFlowStore from '../../../../stores/flowStore';
import { useTypesStore } from '../../../../stores/typesStore';
import type { NodeOutputFieldComponentType } from '../../../../types/components';
import {
  getGroupOutputNodeId,
  scapedJSONStringfy,
  scapeJSONParse,
} from '../../../../utils/reactflowUtils';
import { cn } from '../../../../utils/utils';
import {
  determineOutputStatus,
  isOutputEmpty,
  detectLooping,
  isOutputShortcutOpenable,
} from '../NodeOutputParameter/nodeOutputUtils';
import HandleRenderComponent from '../handleRenderComponent';
import OutputComponent from '../OutputComponent';
import OutputModal from '../outputModal';

const SnowflakeIcon = memo(() => (
  <IconComponent className="h-5 w-5 text-ice" name="Snowflake" />
));

const InspectButton = memo(
  forwardRef(
    (
      {
        disabled,
        displayOutputPreview,
        unknownOutput,
        errorOutput,
        isToolMode,
        title,
        onClick,
        id,
      }: {
        disabled: boolean | undefined;
        displayOutputPreview: boolean;
        unknownOutput: boolean | undefined;
        errorOutput: boolean;
        isToolMode: boolean;
        title: string;
        onClick: () => void;
        id: string;
      },
      ref: React.ForwardedRef<HTMLButtonElement>
    ) => (
      <Button
        ref={ref}
        disabled={disabled}
        data-testid={`output-inspection-${title.toLowerCase()}-${id.toLowerCase()}`}
        unstyled
        onClick={onClick}
      >
        <IconComponent
          name="TextSearchIcon"
          strokeWidth={ICON_STROKE_WIDTH}
          className={cn(
            'icon-size',
            isToolMode
              ? displayOutputPreview && !unknownOutput && !disabled
                ? 'text-background hover:text-secondary-hover'
                : 'cursor-not-allowed text-placeholder-foreground opacity-80'
              : displayOutputPreview && !unknownOutput && !disabled
              ? 'text-foreground hover:text-primary-hover'
              : 'cursor-not-allowed text-placeholder-foreground opacity-60',
            errorOutput ? 'text-destructive' : ''
          )}
        />
      </Button>
    )
  )
);
InspectButton.displayName = 'InspectButton';

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
  outputs,
  outputProxy,
  lastOutput,
  colorName,
  isToolMode = false,
  handleSelectOutput,
}: NodeOutputFieldComponentType): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  const updateNodeInternals = useUpdateNodeInternals();

  const edges = useFlowStore(state => state.edges);
  const setNode = useFlowStore(state => state.setNode);
  const setFilterEdge = useFlowStore(state => state.setFilterEdge);
  const flowPool = useFlowStore(state => state.flowPool);
  const myData = useTypesStore(state => state.data);

  const { flowPoolId, internalOutputName } = useMemo(() => {
    if (data.node?.flow && outputProxy) {
      const realOutput = getGroupOutputNodeId(
        data.node.flow,
        outputProxy.name,
        outputProxy.id
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
    () => determineOutputStatus(flowPool, flowPoolId, internalOutputName || ''),
    [flowPool, flowPoolId, internalOutputName]
  );

  const emptyOutput = useMemo(() => {
    return isOutputEmpty(flowPoolNode?.data);
  }, [flowPoolNode?.data]);

  const looping = useMemo(() => {
    return detectLooping(edges, scapedJSONStringfy(id));
  }, [edges, id]);

  const [openOutputModal, setOpenOutputModal] = useState(false);

  const outputShortcutOpenable = useMemo(() => {
    return isOutputShortcutOpenable({
      displayOutputPreview,
      selected,
      edges,
      nodeData: data,
      id: scapedJSONStringfy(id),
      flowPoolNode,
      internalOutputName: internalOutputName || '',
    });
  }, [
    displayOutputPreview,
    selected,
    edges,
    data,
    id,
    flowPoolNode,
    internalOutputName,
  ]);

  const handleOpenOutputModal = () => {
    if (outputShortcutOpenable) {
      setOpenOutputModal(true);
    }
  };

  const outputInspection = useShortcutsStore(state => state.outputInspection);
  useHotkeys(outputInspection, handleOpenOutputModal, { preventDefault: true });

  const LoopHandle = useMemo(() => {
    if (data.node?.outputs![index].allows_loop) {
      return (
        <HandleRenderComponent
          left={true}
          tooltipTitle={tooltipTitle}
          id={id}
          title={title}
          nodeId={data.id}
          myData={myData}
          colors={colors}
          setFilterEdge={setFilterEdge}
          showNode={showNode}
          testIdComplement={`${data?.type?.toLowerCase()}-${
            showNode ? 'shownode' : 'noshownode'
          }`}
          colorName={colorName}
        />
      );
    }
  }, [
    tooltipTitle,
    id,
    title,
    data.id,
    myData,
    colors,
    setFilterEdge,
    showNode,
    data?.type,
    colorName,
  ]);

  const Handle = useMemo(
    () => (
      <HandleRenderComponent
        left={false}
        tooltipTitle={tooltipTitle}
        id={id}
        title={title}
        nodeId={data.id}
        myData={myData}
        colors={colors}
        setFilterEdge={setFilterEdge}
        showNode={showNode}
        testIdComplement={`${data?.type?.toLowerCase()}-${
          showNode ? 'shownode' : 'noshownode'
        }`}
        colorName={colorName}
      />
    ),
    [
      tooltipTitle,
      id,
      title,
      data.id,
      myData,
      colors,
      setFilterEdge,
      showNode,
      data?.type,
      colorName,
    ]
  );

  const disabledInspectButton =
    !displayOutputPreview || unknownOutput || emptyOutput;

  if (!showNode) return <>{Handle}</>;

  return (
    <div
      ref={ref}
      className={cn(
        'relative flex h-11 w-full flex-wrap items-center justify-between bg-muted px-5 py-2',
        lastOutput ? 'rounded-b-[0.69rem]' : '',
        isToolMode && 'bg-primary'
      )}
    >
      {LoopHandle}
      <div className="flex w-full items-center justify-end truncate text-sm">
        <div className="flex flex-1">
          {data.node?.outputs![index].allows_loop && (
            <Badge variant="pinkStatic" size="xq" className="mr-2 px-1">
              <ForwardedIconComponent name="Infinity" className="h-4 w-4" />
            </Badge>
          )}
        </div>

        {data.node?.frozen && (
          <div className="pr-1" data-testid="frozen-icon">
            <SnowflakeIcon />
          </div>
        )}

        <div className="flex items-center gap-2">
          <span className={data.node?.frozen ? 'text-ice' : ''}>
            <MemoizedOutputComponent
              proxy={outputProxy}
              outputs={outputs}
              idx={index}
              types={type?.split('|') ?? []}
              selected={
                data.node?.outputs![index].selected ??
                data.node?.outputs![index].types[0] ??
                title
              }
              nodeId={data.id}
              frozen={data.node?.frozen}
              name={title ?? type}
              isToolMode={isToolMode}
              handleSelectOutput={handleSelectOutput}
              outputName={data.node?.key as string}
            />
          </span>

          <ShadTooltip
            content={
              displayOutputPreview
                ? unknownOutput || emptyOutput
                  ? "Output can't be displayed"
                  : 'Inspect output'
                : 'Please build the component first'
            }
            styleClasses="z-40"
          >
            <div className="flex items-center gap-2">
              <OutputModal
                open={openOutputModal}
                setOpen={setOpenOutputModal}
                disabled={disabledInspectButton}
                nodeId={flowPoolId}
                outputName={internalOutputName}
              >
                <InspectButton
                  disabled={disabledInspectButton}
                  displayOutputPreview={displayOutputPreview}
                  unknownOutput={unknownOutput ?? false}
                  errorOutput={errorOutput ?? false}
                  isToolMode={isToolMode}
                  title={title}
                  onClick={() => {}}
                  id={data?.type}
                />
              </OutputModal>
              {looping && (
                <Badge variant="pinkStatic" size="xq" className="px-1">
                  Looping
                </Badge>
              )}
            </div>
          </ShadTooltip>
        </div>
      </div>
      {Handle}
    </div>
  );
}

export default memo(NodeOutputField);
