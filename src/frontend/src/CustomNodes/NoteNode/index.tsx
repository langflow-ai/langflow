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
import IconComponent from "../../components/genericIconComponent";
import NodeDescription from "../GenericNode/components/NodeDescription";
import NodeName from "../GenericNode/components/NodeName";
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
        width: nodeDiv.current.offsetWidth - 43,
        height: nodeDiv.current.offsetHeight - 80,
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
          setSize({ width: width - 43, height: height - 80 });
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
          "flex h-full w-full flex-col gap-3 rounded-md border border-b p-5 transition-all",
          selected ? "" : "-z-50 shadow-sm",
        )}
      >
        <div className="flex h-fit w-full items-center align-middle">
          <div className="flex w-full gap-2">
            <div data-testid="note_icon">
              <IconComponent name="SquarePen" className="min-w-fit" />
            </div>

            <div className="w-11/12">
              <NodeName
                nodeId={data.id}
                selected={selected}
                display_name={data.node?.display_name || "Note"}
              />
            </div>
          </div>
        </div>
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
