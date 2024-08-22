import { noteDataType } from "@/types/flow";
import { NodeResizer, NodeToolbar } from "reactflow";
import IconComponent from "../../components/genericIconComponent";
import NodeDescription from "../GenericNode/components/NodeDescription";
import NodeName from "../GenericNode/components/NodeName";
import { cn } from "@/utils/utils";
import { useEffect, useMemo, useRef, useState} from "react";
import { COLOR_OPTIONS, NOTE_NODE_MAX_HEIGHT, NOTE_NODE_MAX_WIDTH, NOTE_NODE_MIN_HEIGHT, NOTE_NODE_MIN_WIDTH } from "@/constants/constants";
import NoteToolbarComponent from "./NoteToolbarComponent";
function NoteNode({
  data,
  selected,
}: {
  data: noteDataType;
  selected: boolean;
}) {
  const bgColor = data.node?.template.backgroundColor ?? Object.keys(COLOR_OPTIONS)[0];
  const nodeDiv = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  //tricky to start the description with the right size
  useEffect(() => {
    if (nodeDiv.current) {
      setSize({
        width: nodeDiv.current.offsetWidth-43,
        height: nodeDiv.current.offsetHeight-80,
      });
    }
  },[])

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
        onResize={(_, params) => {
          const { width, height } = params;
          setSize({ width:width-43, height:height-80 });
        }}
        isVisible={selected}
        lineClassName="border-[3px] border-border"
      />
      <div style={{
        maxHeight: NOTE_NODE_MAX_HEIGHT,
        maxWidth: NOTE_NODE_MAX_WIDTH,
        minWidth: NOTE_NODE_MIN_WIDTH,
        minHeight: NOTE_NODE_MIN_HEIGHT,
        backgroundColor:COLOR_OPTIONS[bgColor],
      }}
      ref={nodeDiv}
        className={cn("flex flex-col w-full transition-all gap-3 p-5 border border-b h-full rounded-md", selected ? "" : "shadow-sm")}>
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
        </div>
        <div style={{
          width: size.width,
          height: size.height,
        }} className="nowheel overflow-auto">
          <NodeDescription
          inputClassName="border-0 ring-transparent resize-none rounded-none shadow-none h-full w-full"
            style={{backgroundColor:COLOR_OPTIONS[bgColor]}}
            charLimit={2500}
            nodeId={data.id}
            selected={selected}
            description={data.node?.description}
            emptyPlaceholder="Double-click to start typing or enter Markdown..."
          />
        </div>
      </div>
    </>
  );
}

export default NoteNode;
