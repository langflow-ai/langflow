import { noteDataType } from "@/types/flow";
import { NodeResizer } from "reactflow";
import IconComponent from "../../components/genericIconComponent";
import NodeDescription from "../GenericNode/components/NodeDescription";
import NodeName from "../GenericNode/components/NodeName";

function NoteNode({
  data,
  selected,
}: {
  data: noteDataType;
  selected: boolean;
}) {
  return (
    <>
      <NodeResizer
        minWidth={100}
        minHeight={30}
        isVisible={selected}
        lineClassName="border border-border"
      />

      <div className="generic-node-div">
        <div className="w-18 flex">
          <IconComponent name="StickyNote" />
          <NodeName
            nodeId={data.id}
            selected={selected}
            display_name={data.node?.display_name || "Note"}
          />
        </div>
        <NodeDescription
          nodeId={data.id}
          selected={selected}
          description={data.node?.description}
          emptyPlaceholder="Double Click to Edit Note"
        />
      </div>
    </>
  );
}

export default NoteNode;
