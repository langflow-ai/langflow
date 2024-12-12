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
import { NodeResizer } from "reactflow";
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
    Object.keys(COLOR_OPTIONS).find(
      (key) => key === data.node?.template.backgroundColor,
    ) ?? Object.keys(COLOR_OPTIONS)[0];
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
    () =>
      selected ? (
        <div className={cn("absolute -top-12 left-1/2 z-50 -translate-x-1/2")}>
          <NoteToolbarComponent data={data} bgColor={bgColor} />
        </div>
      ) : (
        <></>
      ),
    [data, bgColor, selected],
  );
  return (
    <>
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
        lineClassName="!border !border-muted-foreground"
      />
      <div
        data-testid="note_node"
        style={{
          maxHeight: NOTE_NODE_MAX_HEIGHT,
          maxWidth: NOTE_NODE_MAX_WIDTH,
          minWidth: NOTE_NODE_MIN_WIDTH,
          minHeight: NOTE_NODE_MIN_HEIGHT,
          backgroundColor: COLOR_OPTIONS[bgColor] ?? "#00000000",
        }}
        ref={nodeDiv}
        className={cn(
          "relative flex h-full w-full flex-col gap-3 rounded-xl p-3 transition-all",
          COLOR_OPTIONS[bgColor] !== null &&
            `border ${!selected && "-z-50 shadow-sm"}`,
        )}
      >
        {MemoNoteToolbarComponent}
        <div
          style={{
            width: size.width,
            height: size.height,
            display: "flex",
          }}
        >
          <NodeDescription
            inputClassName={cn(
              "border-0 ring-0 focus:ring-0 resize-none shadow-none rounded-sm h-full w-full",
              COLOR_OPTIONS[bgColor] === null
                ? ""
                : "dark:!ring-background dark:text-background",
            )}
            mdClassName={cn(
              COLOR_OPTIONS[bgColor] === null
                ? "dark:prose-invert"
                : "dark:!text-background",
            )}
            style={{ backgroundColor: COLOR_OPTIONS[bgColor] ?? "#00000000" }}
            charLimit={2500}
            nodeId={data.id}
            selected={selected}
            description={data.node?.description}
            emptyPlaceholder="Double-click to start typing or enter Markdown..."
            placeholderClassName={
              COLOR_OPTIONS[bgColor] === null ? "" : "dark:!text-background"
            }
          />
        </div>
      </div>
    </>
  );
}

export default NoteNode;
