import { noteDataType } from "@/types/flow";
import { NodeResizer } from "reactflow";
import IconComponent from "../../components/genericIconComponent";
import NodeDescription from "../GenericNode/components/NodeDescription";
import NodeName from "../GenericNode/components/NodeName";
import { cn } from "@/utils/utils";
import { useState } from "react";
import { NOTE_NODE_MAX_HEIGHT, NOTE_NODE_MAX_WIDTH, NOTE_NODE_MIN_HEIGHT, NOTE_NODE_MIN_WIDTH } from "@/constants/constants";

function NoteNode({
  data,
  selected,
}: {
  data: noteDataType;
  selected: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <NodeResizer
        minWidth={NOTE_NODE_MIN_WIDTH}
        minHeight={NOTE_NODE_MIN_HEIGHT}
        maxHeight={NOTE_NODE_MAX_HEIGHT}
        maxWidth={NOTE_NODE_MAX_WIDTH}
        isVisible={selected}
        lineClassName="border-[3px] border-border"
      />

      <div style={{
        maxHeight: NOTE_NODE_MAX_HEIGHT,
        maxWidth: NOTE_NODE_MAX_WIDTH,
        minWidth: NOTE_NODE_MIN_WIDTH,
        minHeight: NOTE_NODE_MIN_HEIGHT,
      }}
        className={cn("flex flex-col bg-background transition-all gap-3 p-5 h-full border border-b rounded-md", selected ? "" : "shadow-sm")}>
        <div className="w-full flex align-middle items-center h-fit">
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
          <div onClick={() => {
            setExpanded((prev) => !prev)
          }}>
            <IconComponent className="w-4 h-4 cursor-pointer" name={expanded ? "ChevronsDownUp" : "ChevronsUpDown"} />
          </div>
        </div>
        <div className="h-full nowheel overflow-auto">
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
