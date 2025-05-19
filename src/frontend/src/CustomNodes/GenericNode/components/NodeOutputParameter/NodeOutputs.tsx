// NodeOutputs.tsx
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
}) {
  if (!outputs?.length) return null;

  return outputs?.map((output, idx) => (
    <OutputParameter
      key={`${keyPrefix}-${output.name}-${idx}`}
      output={output}
      idx={
        data.node!.outputs?.findIndex((out) => out.name === output.name) ?? idx
      }
      lastOutput={idx === outputs.length - 1}
      data={data}
      types={types}
      selected={selected}
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
  ));
}
