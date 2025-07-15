import { NodeDataType } from "@/types/flow";
import { OutputParameter } from ".";

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
  const hasLoopOutput = outputs.some((output) => output.allows_loop);
  const hasGroupOutputs = outputs.some((output) => output.group_outputs);
  const isConditionalRouter = data.type === "ConditionalRouter";

  const shouldShowAllOutputs =
    hasLoopOutput || hasGroupOutputs || isConditionalRouter;

  if (shouldShowAllOutputs) {
    return (
      <>
        {outputs?.map((output, idx) => (
          <OutputParameter
            key={`${keyPrefix}-${output.name}-${idx}`}
            output={output}
            outputs={outputs}
            idx={
              data.node!.outputs?.findIndex(
                (out) => out.name === output.name,
              ) ?? idx
            }
            lastOutput={idx === outputs.length - 1}
            data={data}
            types={types}
            selected={selected}
            showNode={showNode}
            isToolMode={isToolMode}
            handleSelectOutput={handleSelectOutput}
            hidden={false}
          />
        ))}
      </>
    );
  }

  const getDisplayOutput = () => {
    const outputWithSelection = outputs.find(
      (output) => output.name === selectedOutput?.name,
    );

    return outputWithSelection || outputs[0];
  };

  const displayOutput = getDisplayOutput();

  if (!displayOutput) return null;

  return (
    <OutputParameter
      key={`${keyPrefix}-${displayOutput.name}`}
      output={displayOutput}
      outputs={outputs}
      idx={
        data.node!.outputs?.findIndex(
          (out) => out.name === displayOutput.name,
        ) ?? 0
      }
      lastOutput={true}
      data={data}
      types={types}
      selected={selected}
      handleSelectOutput={handleSelectOutput}
      showNode={showNode}
      isToolMode={isToolMode}
      hidden={false}
    />
  );
}
