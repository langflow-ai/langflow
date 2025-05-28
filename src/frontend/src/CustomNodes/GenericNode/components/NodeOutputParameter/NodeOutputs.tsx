// NodeOutputs.tsx
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
  showHiddenOutputs,
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
  showHiddenOutputs: boolean;
  selectedOutput: any;
  handleSelectOutput: any;
}) {
  // Check if any output has allows_loop or if it's a ConditionalRouter component
  const hasLoopOutput = outputs.some((output) => output.allows_loop);
  const isConditionalRouter = data.type === "ConditionalRouter";
  const shouldShowAllOutputs = hasLoopOutput || isConditionalRouter;

  // For components that should show all outputs
  if (shouldShowAllOutputs) {
    const outputsToRender =
      keyPrefix === "hidden"
        ? outputs.filter((output) => output.hidden)
        : outputs;

    return (
      <>
        {outputsToRender?.map((output, idx) => (
          <OutputParameter
            key={`${keyPrefix}-${output.name}-${idx}`}
            output={output}
            outputs={outputs}
            idx={
              data.node!.outputs?.findIndex(
                (out) => out.name === output.name,
              ) ?? idx
            }
            lastOutput={idx === outputsToRender.length - 1}
            data={data}
            types={types}
            selected={selected}
            showNode={showNode}
            isToolMode={isToolMode}
            showHiddenOutputs={showHiddenOutputs}
            handleSelectOutput={handleSelectOutput}
            hidden={
              keyPrefix === "hidden"
                ? showHiddenOutputs
                  ? output.hidden
                  : true
                : false
            }
          />
        ))}
      </>
    );
  }

  // For regular components, show only the selected output
  const getDisplayOutput = () => {
    if (selectedOutput) {
      return outputs.find((output) => output.name === selectedOutput.name);
    }
    const outputWithSelection = outputs.find((output) => output.selected);
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
      showHiddenOutputs={showHiddenOutputs}
      hidden={
        keyPrefix === "hidden"
          ? showHiddenOutputs
            ? displayOutput.hidden
            : true
          : false
      }
    />
  );
}
