import { Handle, Position, useUpdateNodeInternals } from "reactflow";
import Tooltip from "../../../../components/TooltipComponent";
import {
  isValidConnection,
  nodeColors,
  snakeToNormalCase,
} from "../../../../utils";
import { useEffect, useRef, useState } from "react";
import InputComponent from "../../../../components/inputComponent";
import ToggleComponent from "../../../../components/toggleComponent";
import InputListComponent from "../../../../components/inputListComponent";

export default function ParameterComponent({
  left,
  id,
  data,
  tooltipTitle,
  title,
  color,
  type,
  name = "",
  required = false,
}) {
  const ref = useRef(null);
  const updateNodeInternals = useUpdateNodeInternals();
  const [position, setPosition] = useState(0);
  var _ = require('lodash');
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
  let disabled = data.reactFlowInstance.getEdges().some((e) => (e.sourceHandle === id));

  return (
    <div ref={ref} className="w-full flex flex-wrap justify-between items-center bg-gray-50 mt-1 px-5 py-2">
      <>
        <div className="text-sm truncate">{title}<span className="text-red-600">{required ? " *" : ""}</span></div>
        <Tooltip title={tooltipTitle + (required ? " (required)" : "")}>
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
            {data.node.template[name].list ? 
            <InputListComponent
            disabled={disabled}
            value={!data.node.template[name].value || data.node.template[name].value === "" ? [""] : data.node.template[name].value}
              onChange={(t) => {
                data.node.template[name].value = t;
              }}
            />
            :
            <InputComponent
            disabled={disabled}
            value={data.node.template[name].value ?? ""}
              onChange={(t) => {
                data.node.template[name].value = t;
              }}
            />
            }
            
          </div>
        ) : left === true && type === "bool" ? (
          <div className="mt-2">
            <ToggleComponent
              disabled={disabled}
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
