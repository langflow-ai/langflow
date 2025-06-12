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
  hasExistingHiddenOutputs = false,
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
  hasExistingHiddenOutputs?: boolean;
}) {
  const hasLoopOutput = outputs.some((output) => output.allows_loop);
  const hasGroupOutputs = outputs.some((output) => output.group_outputs);
  const isConditionalRouter = data.type === "ConditionalRouter";
  const hasHiddenOutputs = outputs.some((output) => output.hidden);

  const shouldShowAllOutputs =
    hasLoopOutput || hasGroupOutputs || isConditionalRouter || hasHiddenOutputs;

  if (shouldShowAllOutputs) {
    const outputsToRender =
      keyPrefix === "hidden"
        ? outputs.filter((output) => output.hidden)
        : outputs.filter((output) => !output.hidden);

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

  const getDisplayOutput = () => {
    const filteredOutputs =
      keyPrefix === "hidden"
        ? outputs.filter((output) => output.hidden)
        : outputs.filter((output) => !output.hidden);

    if (selectedOutput) {
      return (
        filteredOutputs.find((output) => output.name === selectedOutput.name) ||
        filteredOutputs[0]
      );
    }

    const outputWithSelection = filteredOutputs.find(
      (output) => output.selected,
    );

    return outputWithSelection || filteredOutputs[0];
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
      lastOutput={!hasExistingHiddenOutputs}
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
