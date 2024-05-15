import { useState } from "react";
import InputComponent from "../../components/inputComponent";

function AnnotationNode({ data }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(data.label);

  return (
    <div className="relative">
      <div style={{ padding: 10, display: "flex" }}>
        <div>
          {editing ? (
            <InputComponent
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
              className="nodouble"
              onDoubleClick={() => {
                setEditing(true);
              }}
            >
              {data.label}
            </div>
          )}
        </div>
      </div>
      {data.arrowStyle && (
        <div className="arrow absolute -bottom-2 -right-2 h-5 w-5 -rotate-90">
          ⤹
        </div>
      )}
    </div>
  );
}

export default AnnotationNode;
