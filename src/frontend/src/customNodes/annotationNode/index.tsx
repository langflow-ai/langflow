import { useRef, useState } from "react";
import { NodeResizeControl, useUpdateNodeInternals } from "reactflow";
import InputComponent from "../../components/inputComponent";
import ForwardedIconComponent from "../../components/genericIconComponent";

function AnnotationNode({ data }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(data.label);

  const updateNodeInternals = useUpdateNodeInternals();

  return (
    <>
      <NodeResizeControl
        minWidth={20}
        className="left-auto right-4 z-10 border-none bg-transparent"
        onResize={() => {
          updateNodeInternals(data.id);
        }}
        position="right"
      >
        <ForwardedIconComponent
          name="GripVertical"
          className="h-4 w-4 text-muted-foreground"
        />
      </NodeResizeControl>
      <div className="relative h-fit">
        <div className="flex h-fit overflow-hidden rounded-lg border bg-yellow-200 p-2 pr-8">
          {editing ? (
            <InputComponent
              className="w-full"
              autoFocus={true}
              password={false}
              value={value}
              onChange={(value) => setValue(value)}
              onBlur={() => {
                setEditing(false);
                data.label = value;
              }}
            />
          ) : (
            <div
              className="nodouble h-fit w-full"
              onDoubleClick={() => {
                setEditing(true);
              }}
            >
              {data.label}
            </div>
          )}
        </div>
        {data.arrowStyle && (
          <div className="arrow absolute -bottom-2 -right-2 h-5 w-5 -rotate-90">
            ⤹
          </div>
        )}
      </div>
    </>
  );
}

export default AnnotationNode;
