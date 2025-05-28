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
  // Find the output that should be displayed
  // If there's a selectedOutput, use it; otherwise find the output with a selected property
  // If neither exists, use the first output
  const getDisplayOutput = () => {
    if (selectedOutput) {
      return outputs.find((output) => output.name === selectedOutput.name);
    }
    const outputWithSelection = outputs.find((output) => output.selected);
    return outputWithSelection || outputs[0];
  };

  const displayOutput = getDisplayOutput();

  if (!displayOutput) return null;

  const isLoop = displayOutput?.allows_loop ?? false;

  const hiddenOutputs = outputs.filter((output) => output.hidden);

  return isLoop ? (
    keyPrefix === "hidden" ? (
      hiddenOutputs?.map((output, idx) => (
        <OutputParameter
          key={`${keyPrefix}-${output.name}-${idx}`}
          output={output}
          outputs={outputs}
          idx={
            data.node!.outputs?.findIndex((out) => out.name === output.name) ??
            idx
          }
          lastOutput={idx === hiddenOutputs.length - 1}
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
      ))
    ) : (
      outputs?.map((output, idx) => (
        <OutputParameter
          key={`${keyPrefix}-${output.name}-${idx}`}
          output={output}
          outputs={outputs}
          idx={
            data.node!.outputs?.findIndex((out) => out.name === output.name) ??
            idx
          }
          lastOutput={idx === outputs.length - 1}
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
      ))
    )
  ) : (
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
