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
  isToolMode,
  hidden,
  handleSelectOutput,
}) => {
  const id = useMemo(
    () => ({
      output_types: [output.selected ?? output.types[0]],
      id: data.id,
      dataType: data.type,
      name: output.name,
    }),
    [output.selected, output.types, data.id, data.type, output.name],
  );

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
      tooltipTitle={output.selected ?? output.types[0]}
      id={id}
      type={output.types.join("|")}
      showNode={showNode}
      outputName={output.name}
      outputs={outputs}
      handleSelectOutput={handleSelectOutput}
      colorName={colorNames}
      isToolMode={isToolMode}
    />
  );
};
