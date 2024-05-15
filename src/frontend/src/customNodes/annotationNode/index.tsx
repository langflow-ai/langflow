import { useRef, useState } from "react";
import { NodeResizeControl } from "reactflow";
import { cn } from "../../utils/utils";

function AnnotationNode({ data, selected, id }) {
  const [value, setValue] = useState(data.label);

  const editRef = useRef<HTMLDivElement>(null);

  return (
    <>
      <div className="relative h-fit">
        <NodeResizeControl
          minWidth={100}
          className={cn(
            "absolute left-auto right-1 z-10 h-4 border-none bg-transparent",
            !selected ? "hidden" : "",
          )}
          position="right"
        >
          <div className="px-1">
            <div className="h-4 w-px rounded bg-ring" />
          </div>
        </NodeResizeControl>
        <div
          className={cn(
            "flex h-fit overflow-hidden rounded-lg border bg-yellow-100 p-3",
            selected ? "border-ring" : "border-border",
          )}
        >
          <div
            contentEditable={selected}
            ref={editRef}
            onInput={(e) => setValue(e.currentTarget.textContent)}
            className={cn(
              selected
                ? "nocopy nopan nodouble nodelete nodrag nound cursor-text outline-none"
                : "",
              "h-fit w-full text-black",
            )}
            onBlur={() => {
              data.label = value;
              window!.getSelection()!.removeAllRanges();
            }}
            onDoubleClick={(event) => {
              if (!selected) {
                event.preventDefault();
                event.stopPropagation();
                editRef?.current?.focus();
                // Place the cursor at the end of the text
                const range = document.createRange();
                const selection = window.getSelection();
                range.selectNodeContents(editRef?.current!);
                range.collapse(false);
                selection?.removeAllRanges();
                selection?.addRange(range);
              }
            }}
          >
            {data.label}
          </div>
        </div>
      </div>
    </>
  );
}

export default AnnotationNode;
