import { NodeResizer } from "@xyflow/react";
import { debounce } from "lodash";
import { useMemo, useRef, useState } from "react";
import {
  COLOR_OPTIONS,
  DEFAULT_NOTE_SIZE,
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
const TRANSPARENT_COLOR = "#00000000";

/**
 * Calculates relative luminance and returns whether text should be light or dark.
 * Uses WCAG luminance formula: L = 0.299*R + 0.587*G + 0.114*B
 * Supports hex (#RRGGBB), rgb(), and hsl() color formats.
 */
function getContrastTextColor(bgColor: string): "light" | "dark" {
  if (!bgColor || bgColor === TRANSPARENT_COLOR) {
    return "dark";
  }

  let r = 0,
    g = 0,
    b = 0;

  if (bgColor.startsWith("#")) {
    const hex = bgColor.replace("#", "");
    r = parseInt(hex.substring(0, 2), 16);
    g = parseInt(hex.substring(2, 4), 16);
    b = parseInt(hex.substring(4, 6), 16);
  } else if (bgColor.startsWith("hsl")) {
    // For HSL, extract lightness value directly (simpler than full conversion)
    const match = bgColor.match(/hsl\(.*?,.*?,\s*(\d+(?:\.\d+)?)%?\)/);
    if (match) {
      const lightness = parseFloat(match[1]);
      return lightness > 50 ? "dark" : "light";
    }
    return "dark";
  } else if (bgColor.startsWith("rgb")) {
    const match = bgColor.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (match) {
      r = parseInt(match[1]);
      g = parseInt(match[2]);
      b = parseInt(match[3]);
    }
  }

  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.5 ? "dark" : "light";
}

/** Checks if a color is custom (not a preset from COLOR_OPTIONS) */
function isCustomColor(color: string | undefined): boolean {
  return Boolean(color && !Object.keys(COLOR_OPTIONS).includes(color));
}

function NoteNode({
  data,
  selected,
}: {
  data: NoteDataType;
  selected?: boolean;
}) {
  const nodeRef = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState(false);
  const [isEditingDescription, setIsEditingDescription] = useAlternate(false);

  const currentFlow = useFlowStore((state) => state.currentFlow);
  const setNode = useFlowStore((state) => state.setNode);

  // Resolve background color: either a custom hex or a preset key from COLOR_OPTIONS
  const templateBgColor = data.node?.template.backgroundColor;
  const hasCustomColor = isCustomColor(templateBgColor);
  const bgColorKey = hasCustomColor
    ? templateBgColor!
    : (templateBgColor ?? Object.keys(COLOR_OPTIONS)[0]);

  // Resolved CSS background color value
  const resolvedBgColor = useMemo(
    () =>
      hasCustomColor
        ? bgColorKey
        : (COLOR_OPTIONS[bgColorKey] ?? TRANSPARENT_COLOR),
    [hasCustomColor, bgColorKey],
  );

  // Determine text color mode based on background luminance
  const textColorMode = useMemo(
    () => getContrastTextColor(resolvedBgColor),
    [resolvedBgColor],
  );

  // Get current node dimensions from flow state
  const nodeData = useMemo(
    () => currentFlow?.data?.nodes.find((node) => node.id === data.id),
    [currentFlow, data.id],
  );
  const nodeWidth = nodeData?.width ?? DEFAULT_NOTE_SIZE;
  const nodeHeight = nodeData?.height ?? DEFAULT_NOTE_SIZE;

  // Debounced resize handler to avoid excessive state updates during drag
  const debouncedResize = useMemo(
    () =>
      debounce((width: number, height: number) => {
        setNode(data.id, (node) => ({ ...node, width, height }));
      }, 5),
    [setNode, data.id],
  );

  // Only render toolbar when note is selected
  const toolbar = useMemo(
    () =>
      selected ? (
        <div className="absolute -top-12 left-1/2 z-50 -translate-x-1/2">
          <NoteToolbarComponent data={data} bgColor={bgColorKey} />
        </div>
      ) : null,
    [data, bgColorKey, selected],
  );

  // Generate text color classes based on background (light text on dark bg, dark on light)
  const getTextColorClass = (opacity?: number) => {
    if (!hasCustomColor) {
      return COLOR_OPTIONS[bgColorKey] === null
        ? ""
        : "dark:!ring-background dark:text-background";
    }
    const base = textColorMode === "light" ? "!text-white" : "!text-black";
    return opacity
      ? base
          .replace("white", `white/${opacity}`)
          .replace("black", `black/${opacity}`)
      : base;
  };

  const hasVisibleBg = hasCustomColor || COLOR_OPTIONS[bgColorKey] !== null;

  return (
    <>
      <NodeResizer
        minWidth={NOTE_NODE_MIN_WIDTH}
        minHeight={NOTE_NODE_MIN_HEIGHT}
        onResize={(_, { width, height }) => debouncedResize(width, height)}
        isVisible={selected}
        lineClassName="!border !border-muted-foreground"
        onResizeStart={() => setIsResizing(true)}
        onResizeEnd={() => {
          setIsResizing(false);
          debouncedResize.flush();
        }}
      />

      <div
        ref={nodeRef}
        data-testid="note_node"
        style={{
          width: nodeWidth,
          height: nodeHeight,
          backgroundColor: resolvedBgColor,
        }}
        className={cn(
          "relative flex h-full w-full flex-col gap-3 rounded-xl p-3",
          "duration-200 ease-in-out",
          !isResizing && "transition-transform",
          hasVisibleBg && `border ${!selected && "-z-50 shadow-sm"}`,
        )}
      >
        {toolbar}

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
              "border-0 ring-0 focus:ring-0 resize-none shadow-none rounded-sm h-full min-w-full",
              hasCustomColor
                ? getTextColorClass()
                : COLOR_OPTIONS[bgColorKey] === null
                  ? ""
                  : "dark:!ring-background dark:text-background",
            )}
            mdClassName={cn(
              hasCustomColor
                ? getTextColorClass()
                : COLOR_OPTIONS[bgColorKey] === null
                  ? "dark:prose-invert"
                  : "dark:!text-background",
              "min-w-full",
            )}
            style={{ backgroundColor: resolvedBgColor }}
            charLimit={CHAR_LIMIT}
            nodeId={data.id}
            selected={selected}
            description={data.node?.description}
            emptyPlaceholder="Double-click to start typing or enter Markdown..."
            placeholderClassName={cn(
              hasCustomColor
                ? textColorMode === "light"
                  ? "!text-white/70"
                  : "!text-black/70"
                : COLOR_OPTIONS[bgColorKey] === null
                  ? ""
                  : "dark:!text-background",
              "px-2",
            )}
            editNameDescription={isEditingDescription}
            setEditNameDescription={setIsEditingDescription}
            stickyNote
          />
        </div>
      </div>
    </>
  );
}

export default NoteNode;
