import {
  COLOR_OPTIONS,
  NOTE_NODE_MAX_HEIGHT,
  NOTE_NODE_MAX_WIDTH,
  NOTE_NODE_MIN_HEIGHT,
  NOTE_NODE_MIN_WIDTH,
} from "@/constants/constants";
import { useAlternate } from "@/shared/hooks/use-alternate";
import useFlowStore from "@/stores/flowStore";
import { NoteDataType } from "@/types/flow";
import { cn } from "@/utils/utils";
import { NodeResizer } from "@xyflow/react";
import { debounce } from "lodash";
import { useEffect, useMemo, useRef, useState } from "react";
import NodeDescription from "../GenericNode/components/NodeDescription";
import NoteToolbarComponent from "./NoteToolbarComponent";

const NOTE_NODE_PADDING = 25;
const CHAR_LIMIT = 2500;
const DEFAULT_WIDTH = 324;
const DEFAULT_HEIGHT = 324;

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
  const [size, setSize] = useState({
    width: DEFAULT_WIDTH - NOTE_NODE_PADDING,
    height: DEFAULT_HEIGHT - NOTE_NODE_PADDING,
  });
  const [resizedNote, setResizedNote] = useState(false);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const setNode = useFlowStore((state) => state.setNode);
  const [isResizing, setIsResizing] = useState(false);

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
        setSize({
          width: width - NOTE_NODE_PADDING,
          height: height - NOTE_NODE_PADDING,
        });
        setNode(data.id, (node) => {
          return {
            ...node,
            width: width,
            height: height,
          };
        });
      }, 5),
    [],
  );

  useEffect(() => {
    if (nodeData && !resizedNote && nodeDataWidth > 0 && nodeDataHeight > 0) {
      setSize({
        width: nodeDataWidth - NOTE_NODE_PADDING,
        height: nodeDataHeight - NOTE_NODE_PADDING,
      });
    } else if (!nodeData && nodeDiv.current) {
      const currentWidth = nodeDiv.current.offsetWidth || DEFAULT_WIDTH;
      const currentHeight = nodeDiv.current.offsetHeight || DEFAULT_HEIGHT;
      setSize({
        width: Math.max(currentWidth, DEFAULT_WIDTH) - NOTE_NODE_PADDING,
        height: Math.max(currentHeight, DEFAULT_HEIGHT) - NOTE_NODE_PADDING,
      });
    }
  }, [nodeData, nodeDataWidth, nodeDataHeight, resizedNote]);

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
        minWidth={Math.max(DEFAULT_WIDTH, NOTE_NODE_MIN_WIDTH)}
        minHeight={Math.max(DEFAULT_HEIGHT, NOTE_NODE_MIN_HEIGHT)}
        maxWidth={NOTE_NODE_MAX_WIDTH}
        maxHeight={NOTE_NODE_MAX_HEIGHT}
        onResize={(_, params) => {
          const { width, height } = params;
          debouncedResize(width, height);
        }}
        isVisible={selected}
        lineClassName="!border !border-muted-foreground"
        onResizeStart={() => {
          setResizedNote(true);
          setIsResizing(true);
        }}
        onResizeEnd={() => {
          setIsResizing(false);
          debouncedResize.flush();
        }}
      />
      <div
        data-testid="note_node"
        style={{
          minWidth: Math.max(DEFAULT_WIDTH, NOTE_NODE_MIN_WIDTH),
          minHeight: Math.max(DEFAULT_HEIGHT, NOTE_NODE_MIN_HEIGHT),
          backgroundColor: COLOR_OPTIONS[bgColor] ?? "#00000000",
        }}
        ref={nodeDiv}
        className={cn(
          "relative flex h-full w-full flex-col gap-3 rounded-xl p-3",
          "duration-200 ease-in-out",
          !isResizing && "transition-transform",
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
          }}
          className={cn(
            "flex-1 duration-200 ease-in-out",
            !isResizing && "transition-[width,height]",
          )}
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
              "min-w-full",
            )}
            style={{ backgroundColor: COLOR_OPTIONS[bgColor] ?? "#00000000" }}
            charLimit={CHAR_LIMIT}
            nodeId={dataId}
            selected={selected}
            description={dataDescription}
            emptyPlaceholder="Double-click to start typing or enter Markdown..."
            placeholderClassName={
              COLOR_OPTIONS[bgColor] === null ? "" : "dark:!text-background"
            }
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
