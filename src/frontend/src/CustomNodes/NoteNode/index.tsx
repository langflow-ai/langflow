import { NodeResizer } from "@xyflow/react";
import { debounce } from "lodash";
import { useMemo, useRef, useState } from "react";
import {
  COLOR_OPTIONS,
  NOTE_NODE_MAX_HEIGHT,
  NOTE_NODE_MAX_WIDTH,
  NOTE_NODE_MIN_HEIGHT,
  NOTE_NODE_MIN_WIDTH,
} from "@/constants/constants";
import { useAlternate } from "@/shared/hooks/use-alternate";
import useFlowStore from "@/stores/flowStore";
import type { NoteDataType } from "@/types/flow";
import { cn } from "@/utils/utils";
import NodeDescription from "../GenericNode/components/NodeDescription";
import NoteToolbarComponent from "./NoteToolbarComponent";

const CHAR_LIMIT = 2500;
const DEFAULT_WIDTH = NOTE_NODE_MIN_WIDTH;
const DEFAULT_HEIGHT = NOTE_NODE_MIN_HEIGHT;

function NoteNode({
  data,
  selected,
}: {
  data: NoteDataType;
  selected?: boolean;
}) {
  const bgColor =
    Object.keys(COLOR_OPTIONS).find(
      (key) => key === data.node?.template.backgroundColor,
    ) ?? Object.keys(COLOR_OPTIONS)[0];
  const nodeDiv = useRef<HTMLDivElement>(null);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const setNode = useFlowStore((state) => state.setNode);

  const nodeData = useMemo(
    () => currentFlow?.data?.nodes.find((node) => node.id === data.id),
    [currentFlow, data.id],
  );

  const nodeDataWidth = useMemo(
    () => nodeData?.width ?? DEFAULT_WIDTH,
    [nodeData?.width],
  );
  const nodeDataHeight = useMemo(
    () => nodeData?.height ?? DEFAULT_HEIGHT,
    [nodeData?.height],
  );

  const dataId = useMemo(() => data.id, [data.id]);
  const dataDescription = useMemo(
    () => data.node?.description,
    [data.node?.description],
  );

  const debouncedResize = useMemo(
    () =>
      debounce((width: number, height: number) => {
        setNode(data.id, (node) => {
          return {
            ...node,
            width: width,
            height: height,
          };
        });
      }, 5),
    [data.id, setNode],
  );

  const [editNameDescription, set] = useAlternate(false);

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
        maxWidth={NOTE_NODE_MAX_WIDTH}
        maxHeight={NOTE_NODE_MAX_HEIGHT}
        onResize={(_, params) => {
          const { width, height } = params;
          debouncedResize(width, height);
        }}
        onResizeEnd={() => {
          debouncedResize.flush();
        }}
        isVisible={selected}
        lineClassName="!border !border-muted-foreground"
      />
      <div
        data-testid="note_node"
        style={{
          width: nodeDataWidth,
          height: nodeDataHeight,
          backgroundColor: COLOR_OPTIONS[bgColor] ?? "#00000000",
        }}
        ref={nodeDiv}
        className={cn(
          "relative flex h-full w-full flex-col gap-3 rounded-xl p-3",
          "duration-200 ease-in-out",
          "transition-transform",
          COLOR_OPTIONS[bgColor] !== null &&
            `border ${!selected && "-z-50 shadow-sm"}`,
        )}
      >
        {MemoNoteToolbarComponent}
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            overflow: "hidden",
            maxHeight: "100%",
          }}
          className={cn(
            "flex-1 duration-200 ease-in-out",
            "transition-[width,height]",
          )}
        >
          <NodeDescription
            inputClassName={cn(
              "border-0 ring-0 focus:ring-0 resize-none shadow-none rounded-sm h-full min-w-full max-h-full overflow-auto",
              COLOR_OPTIONS[bgColor] === null
                ? ""
                : "dark:!ring-background dark:text-background",
            )}
            mdClassName={cn(
              COLOR_OPTIONS[bgColor] === null
                ? "dark:prose-invert"
                : "dark:!text-background",
              "min-w-full max-h-full overflow-auto",
            )}
            style={{ backgroundColor: COLOR_OPTIONS[bgColor] ?? "#00000000" }}
            charLimit={CHAR_LIMIT}
            nodeId={dataId}
            selected={selected}
            description={dataDescription}
            emptyPlaceholder="Double-click to start typing or enter Markdown..."
            placeholderClassName={cn(
              COLOR_OPTIONS[bgColor] === null ? "" : "dark:!text-background",
              "px-2",
            )}
            editNameDescription={editNameDescription}
            setEditNameDescription={set}
            stickyNote
          />
        </div>
      </div>
    </>
  );
}

export default NoteNode;
