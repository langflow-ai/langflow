import { Handle, Position, useUpdateNodeInternals } from "reactflow";
import Tooltip from "../../../../components/TooltipComponent";
import {
  isValidConnection,
  nodeColors,
  snakeToNormalCase,
} from "../../../../utils";
import { useEffect, useRef, useState } from "react";
import Input from "../../../../components/inputComponent";
import ToggleComponent from "../../../../components/toggleComponent";

export default function ParameterComponent({
  left,
  id,
  data,
  tooltipTitle,
  title,
  color,
  type,
  name = "",
}) {
  const ref = useRef(null);
  const updateNodeInternals = useUpdateNodeInternals();
  const [position, setPosition] = useState(0);
  useEffect(() => {
    if (ref.current && ref.current.offsetTop && ref.current.clientHeight) {
      setPosition(ref.current.offsetTop + ref.current.clientHeight / 2);
      updateNodeInternals(data.id);
    }
  }, [data.id, ref, updateNodeInternals]);

  useEffect(() => {
    updateNodeInternals(data.id);
  }, [data.id, position, updateNodeInternals]);

  const [enabled, setEnabled] = useState(data.node.template[name]?.value ?? false);

  return (
    <div ref={ref} className="w-full flex flex-wrap justify-between items-center bg-gray-50 mt-1 px-5 py-2">
      <>
        <div className="text-sm truncate">{title}</div>
        <Tooltip title={tooltipTitle}>
          <Handle
            type={left ? "source" : "target"}
            position={left ? Position.Left : Position.Right}
            id={id}
            isValidConnection={(connection) =>
              isValidConnection(data, connection)
            }
            className={
              (left ? "-ml-0.5 " : "-mr-0.5 ") +
              "w-3 h-3 rounded-full border-2 bg-white"
            }
            style={{
              borderColor: color,
              top: position,
            }}
          ></Handle>
        </Tooltip>
        {left === true && type === "str" ? (
          <div className="mt-2 w-full">
            <Input
              onChange={(t) => {
                data.node.template[name].value = t;
              }}
            />
          </div>
        ) : left === true && type === "bool" ? (
          <div className="mt-2">
            <ToggleComponent
              enabled={enabled}
              setEnabled={(t) => {
                data.node.template[name].value = t;
                setEnabled(t);
              }}
            />
          </div>
        ) : (
          <></>
        )}
      </>
    </div>
  );
}
