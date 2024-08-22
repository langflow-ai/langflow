import { noteDataType } from "@/types/flow";
import { NodeResizer, NodeToolbar } from "reactflow";
import IconComponent from "../../components/genericIconComponent";
import NodeDescription from "../GenericNode/components/NodeDescription";
import NodeName from "../GenericNode/components/NodeName";
import { cn } from "@/utils/utils";
import { useMemo, useState } from "react";
import { COLOR_OPTIONS, NOTE_NODE_MAX_HEIGHT, NOTE_NODE_MAX_WIDTH, NOTE_NODE_MIN_HEIGHT, NOTE_NODE_MIN_WIDTH } from "@/constants/constants";
import NoteToolbarComponent from "./NoteToolbarComponent";

function NoteNode({
  data,
  selected,
}: {
  data: noteDataType;
  selected: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const bgColor = data.node?.template.backgroundColor ?? Object.keys(COLOR_OPTIONS)[0];
  const MemoNoteToolbarComponent = useMemo(() =>(
    <NodeToolbar>
    <NoteToolbarComponent data={data} bgColor={bgColor}/>
  </NodeToolbar>
  ), [data, bgColor]);

  return (
    <>
    {MemoNoteToolbarComponent}
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
        backgroundColor:COLOR_OPTIONS[bgColor]
      }}
        className={cn("flex flex-col transition-all gap-3 p-5 h-full border border-b rounded-md", selected ? "" : "shadow-sm")}>
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
