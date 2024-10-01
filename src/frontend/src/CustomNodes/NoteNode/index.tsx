import {
  COLOR_OPTIONS,
  NOTE_NODE_MAX_HEIGHT,
  NOTE_NODE_MAX_WIDTH,
  NOTE_NODE_MIN_HEIGHT,
  NOTE_NODE_MIN_WIDTH,
} from "@/constants/constants";
import { noteDataType } from "@/types/flow";
import { cn } from "@/utils/utils";
import { useEffect, useMemo, useRef, useState } from "react";
import { NodeResizer, NodeToolbar } from "reactflow";
import NodeDescription from "../GenericNode/components/NodeDescription";
import NoteToolbarComponent from "./NoteToolbarComponent";
function NoteNode({
  data,
  selected,
}: {
  data: noteDataType;
  selected: boolean;
}) {
  const bgColor =
    data.node?.template.backgroundColor ?? Object.keys(COLOR_OPTIONS)[0];
  const nodeDiv = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  //tricky to start the description with the right size
  useEffect(() => {
    if (nodeDiv.current) {
      setSize({
        width: nodeDiv.current.offsetWidth - 25,
        height: nodeDiv.current.offsetHeight - 25,
      });
    }
  }, []);
  const MemoNoteToolbarComponent = useMemo(
    () => (
      <NodeToolbar>
        <NoteToolbarComponent data={data} bgColor={bgColor} />
      </NodeToolbar>
    ),
    [data, bgColor],
  );
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
          setSize({ width: width - 25, height: height - 25 });
        }}
        isVisible={selected}
        lineClassName="border-[3px] border-border"
      />
      <div
        data-testid="note_node"
        style={{
          maxHeight: NOTE_NODE_MAX_HEIGHT,
          maxWidth: NOTE_NODE_MAX_WIDTH,
          minWidth: NOTE_NODE_MIN_WIDTH,
          minHeight: NOTE_NODE_MIN_HEIGHT,
          backgroundColor: COLOR_OPTIONS[bgColor],
        }}
        ref={nodeDiv}
        className={cn(
          "flex h-full w-full flex-col gap-3 border border-b p-3 transition-all",
          selected ? "" : "-z-50 shadow-sm",
        )}
      >
        <div
          style={{
            width: size.width,
            height: size.height,
          }}
        >
          <NodeDescription
            inputClassName="border-0 ring-transparent resize-none rounded-none shadow-none h-full w-full"
            style={{ backgroundColor: COLOR_OPTIONS[bgColor] }}
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
