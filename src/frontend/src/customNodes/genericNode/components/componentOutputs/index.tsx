import { NodeDataType } from "../../../../types/flow";
import ComponentOutput from "../ComponentOutput";

export default function ComponentOutputs({ data }: { data: NodeDataType }) {
  return (
    <div>
      {data.node?.outputs?.map((output) => (
        <ComponentOutput
          nodeId={data.id}
          frozen={data.node?.frozen}
          types={output.types}
          selected={output.selected ?? output.types[0]}
        />
      ))}
    </div>
  );
}
