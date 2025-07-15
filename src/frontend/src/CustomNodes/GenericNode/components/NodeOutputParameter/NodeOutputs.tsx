import type { NodeDataType } from '@/types/flow';
import { OutputParameter } from '.';

export default function NodeOutputs({
  outputs,
  keyPrefix,
  data,
  types,
  selected,
  showNode,
  isToolMode,
  selectedOutput,
  handleSelectOutput,
}: {
  outputs: any;
  keyPrefix: string;
  data: NodeDataType;
  types: any;
  selected: boolean;
  showNode: boolean;
  isToolMode: boolean;
  selectedOutput: any;
  handleSelectOutput: any;
}) {
  const hasLoopOutput = outputs.some(output => output.allows_loop);
  const isConditionalRouter = data.type === 'ConditionalRouter';

  // Separate outputs based on group_outputs field
  const groupedOutputs = outputs.filter((output: any) => output.group_outputs);
  const individualOutputs = outputs.filter(
    (output: any) => !output.group_outputs
  );

  const shouldShowAllOutputs = hasLoopOutput || isConditionalRouter;

  if (shouldShowAllOutputs) {
    return (
      <>
        {outputs?.map((output, idx) => (
          <OutputParameter
            key={`${keyPrefix}-${output.name}-${idx}`}
            output={output}
            outputs={outputs}
            idx={
              data.node!.outputs?.findIndex(out => out.name === output.name) ??
              idx
            }
            lastOutput={idx === outputs.length - 1}
            data={data}
            types={types}
            selected={selected}
            showNode={showNode}
            isToolMode={isToolMode}
            handleSelectOutput={handleSelectOutput}
          />
        ))}
      </>
    );
  }

  // Handle individual outputs (group_outputs: false)
  const renderIndividualOutputs = () => {
    // @ts-ignore - Type compatibility issue with filtered array
    return individualOutputs.map((output: any, idx: number) => (
      <OutputParameter
        key={`${keyPrefix}-individual-${output.name}-${idx}`}
        output={output}
        outputs={[output] as any} // Pass only this output to avoid dropdown behavior
        idx={
          data.node!.outputs?.findIndex(
            (out: any) => out.name === output.name
          ) ?? idx
        }
        lastOutput={individualOutputs.length === 0}
        data={data}
        types={types}
        selected={selected}
        showNode={showNode}
        isToolMode={isToolMode}
        handleSelectOutput={handleSelectOutput}
      />
    ));
  };

  // Handle grouped outputs (group_outputs: true) - show as dropdown
  const renderGroupedOutputs = () => {
    if (groupedOutputs.length === 0) return null;

    const getDisplayOutput = () => {
      const outputWithSelection = groupedOutputs.find(
        output => output.name === selectedOutput?.name
      );
      return outputWithSelection || groupedOutputs[0];
    };

    const displayOutput = getDisplayOutput();

    return (
      <OutputParameter
        key={`${keyPrefix}-grouped-${displayOutput.name}`}
        output={displayOutput}
        outputs={groupedOutputs}
        idx={
          data.node!.outputs?.findIndex(
            out => out.name === displayOutput.name
          ) ?? 0
        }
        lastOutput={true}
        data={data}
        types={types}
        selected={selected}
        handleSelectOutput={handleSelectOutput}
        showNode={showNode}
        isToolMode={isToolMode}
      />
    );
  };

  return (
    <>
      {renderIndividualOutputs()}
      {renderGroupedOutputs()}
    </>
  );
}
