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
  const output = selectedOutput
    ? outputs.find((output) => output.name === selectedOutput.name)
    : outputs[0];

  if (!output) return null;

  const idx =
    data.node!.outputs?.findIndex((out) => out.name === output.name) ?? 0;

  const isLoop = output?.allows_loop ?? false;

  const hiddenOutputs = outputs.filter((output) => output.hidden);

  return isLoop ? (
    keyPrefix === "hidden" ? (
      hiddenOutputs?.map((output, idx) => (
        <OutputParameter
          key={`${keyPrefix}-${output.name}-${idx}`}
          output={output}
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
    ) : (
      outputs?.map((output, idx) => (
        <OutputParameter
          key={`${keyPrefix}-${output.name}-${idx}`}
          output={output}
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
      key={`${keyPrefix}-${output.name}-${idx}`}
      output={output}
      outputs={outputs}
      idx={
        data.node!.outputs?.findIndex((out) => out.name === output.name) ?? idx
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
            ? output.hidden
            : true
          : false
      }
    />
  );
}
