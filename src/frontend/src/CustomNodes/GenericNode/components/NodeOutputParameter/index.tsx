import { useMemo } from "react";

import { getNodeOutputColors } from "../../../helpers/get-node-output-colors";
import { getNodeOutputColorsName } from "../../../helpers/get-node-output-colors-name";
import NodeOutputField from "../NodeOutputfield";

export const OutputParameter = ({
  output,
  outputs = [],
  idx,
  lastOutput,
  data,
  types,
  selected,
  showNode,
  showHiddenOutputs,
  isToolMode,
  hidden,
  handleSelectOutput,
}) => {
  const id = useMemo(() => {
    const selectedType = output.selected ?? output.types[0];
    // For loop inputs (allows_loop), include the original type and any loop_types
    const outputTypes =
      output.allows_loop && output.loop_types
        ? [selectedType, ...output.loop_types]
        : [selectedType];

    return {
      output_types: outputTypes,
      id: data.id,
      dataType: data.type,
      name: output.name,
    };
  }, [
    output.selected,
    output.types,
    output.allows_loop,
    output.loop_types,
    data.id,
    data.type,
    output.name,
  ]);

  const colors = useMemo(
    () => getNodeOutputColors(output, data, types),
    [output, data.type, data.id, types],
  );

  const colorNames = useMemo(
    () => getNodeOutputColorsName(output, data, types),
    [output, data.type, data.id, types],
  );

  return (
    <NodeOutputField
      hidden={hidden}
      index={idx}
      lastOutput={lastOutput}
      selected={selected}
      key={output.name + idx}
      data={data}
      colors={colors}
      outputProxy={output.proxy}
      title={output.display_name ?? output.name}
      tooltipTitle={
        output.allows_loop && output.loop_types
          ? `${output.selected ?? output.types[0]}\n${output.loop_types.join("\n")}`
          : (output.selected ?? output.types[0])
      }
      id={id}
      type={output.types.join("|")}
      showNode={showNode}
      outputName={output.name}
      outputs={outputs}
      handleSelectOutput={handleSelectOutput}
      colorName={colorNames}
      isToolMode={isToolMode}
      showHiddenOutputs={showHiddenOutputs}
    />
  );
};
