import { noteDataType } from "@/types/flow";
import { NodeResizer } from "reactflow";
import IconComponent from "../../components/genericIconComponent";
import NodeDescription from "../GenericNode/components/NodeDescription";
import NodeName from "../GenericNode/components/NodeName";
import { Button } from "@/components/ui/button";

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
        minWidth={324}
        minHeight={128}
        maxHeight={800}
        maxWidth={600}
        isVisible={selected}
        lineClassName="border border-border"
      />

      <div className="generic-node-div gap-3 p-5 h-full border border-b">
        <div className="w-full flex align-middle items-center">
          <div className="flex w-full gap-2">
            <IconComponent name="StickyNote" />
            <div className="w-4/5">
              <NodeName
                nodeId={data.id}
                selected={selected}
                display_name={data.node?.display_name || "Note"}
              />

            </div>
          </div>
            <IconComponent className="w-4 h-4" name="ChevronsDownUp" />
        </div>
        <div className=" h-full">
        <NodeDescription
        charLimit={2500}
          nodeId={data.id}
          selected={selected}
          description={data.node?.description}
          emptyPlaceholder="Double Click to Edit Note"
        />
        </div>
      </div>
    </>
  );
}

export default NoteNode;
