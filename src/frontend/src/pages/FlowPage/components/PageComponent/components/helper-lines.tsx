import { useViewport } from "@xyflow/react";
import { HelperLinesState } from "../helpers/helper-lines";

interface HelperLinesProps {
  helperLines: HelperLinesState;
}

export default function HelperLines({ helperLines }: HelperLinesProps) {
  const { x: viewportX, y: viewportY, zoom } = useViewport();

  if (!helperLines.horizontal && !helperLines.vertical) {
    return null;
  }

  return (
    // Transient drag-alignment guides: decoration with no meaning to announce.
    <svg className="helper-lines" aria-hidden="true">
      {helperLines.horizontal && (
        <line
          x1={0}
          y1={helperLines.horizontal.position * zoom + viewportY}
          x2="100%"
          y2={helperLines.horizontal.position * zoom + viewportY}
          className="helper-line horizontal"
        />
      )}
      {helperLines.vertical && (
        <line
          x1={helperLines.vertical.position * zoom + viewportX}
          y1={0}
          x2={helperLines.vertical.position * zoom + viewportX}
          y2="100%"
          className="helper-line vertical"
        />
      )}
    </svg>
  );
}
