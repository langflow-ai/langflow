import React, { useMemo } from "react";

import { getNodeOutputColors } from "../../../helpers/get-node-output-colors";
import { getNodeOutputColorsName } from "../../../helpers/get-node-output-colors-name";
import NodeOutputField from "../NodeOutputfield";

export const OutputParameter = ({
  output,
  idx,
  lastOutput,
  data,
  types,
  selected,
  showNode,
  isToolMode,
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
      colorName={colorNames}
      isToolMode={isToolMode}
    />
  );
};
