import { useEffect, useRef, useState } from "react";
import { NodeResizeControl } from "reactflow";
import { cn } from "../../utils/utils";

function NoteNode({ data, selected }) {
  const [value, setValue] = useState(data.text);
  const [editable, setEditable] = useState(false);

  useEffect(() => {
    if (!selected) {
      setEditable(false);
    }
  }, [selected]);

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
            contentEditable={editable}
            onInput={(e) => setValue(e.currentTarget.textContent)}
            className={cn(
              editable
                ? "nocopy nopan nodelete nodrag nound cursor-text outline-none"
                : "",
              "h-fit w-full text-black",
            )}
            onBlur={() => {
              data.label = value;
              setEditable(false);
              window!.getSelection()!.removeAllRanges();
            }}
            onClick={(event) => {
              if (!editable) {
                event.preventDefault();
                event.stopPropagation();
                setEditable(true);
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

export default NoteNode;