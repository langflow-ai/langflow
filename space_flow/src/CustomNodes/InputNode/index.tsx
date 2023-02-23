import { Bars3CenterLeftIcon, TrashIcon } from "@heroicons/react/24/outline";
import InputComponent from "../../components/inputComponent";
import {
  isValidConnection,
  nodeColors,
  nodeIcons,
  snakeToNormalCase,
} from "../../utils";
import { Handle, Position } from "reactflow";
import { useContext, useEffect } from "react";
import Tooltip from "../../components/TooltipComponent";
import { typesContext } from "../../contexts/typesContext";
import TextAreaComponent from "../../components/textAreaComponent";

export default function InputNode({ data }) {
  const {types, deleteNode} = useContext(typesContext);
  return (
    <div className="prompt-node relative bg-white w-96 rounded-lg solid border flex flex-col justify-center">
      <Tooltip title="Prefix: str">
        <Handle
          type="target"
          position={Position.Left}
          id={"str|Prefix|" + data.id}
          isValidConnection={(connection) =>
            isValidConnection(data, connection)
          }
          className="ml-1 bg-transparent border-solid border-l-8 border-y-transparent border-y-8 border-r-0 rounded-none"
          style={{ borderLeftColor: nodeColors[types[data.type]] }}
        ></Handle>
      </Tooltip>

      <div className="w-full flex items-center justify-between p-4 gap-8 bg-gray-50 border-b ">
        <div className="flex items-center gap-4 text-lg">
          <Bars3CenterLeftIcon
            className="w-10 h-10 p-1 rounded"
            style={{ color: nodeColors[types[data.type]] }}
          />
          String
        </div>
        <button
          onClick={() => {
            deleteNode(data.id)
          }}
        >
          <TrashIcon className="text-gray-600 w-6 h-6 hover:text-red-500"></TrashIcon>
        </button>
      </div>
      <div className="w-full p-5 h-full">
        
          <InputComponent
            disabled={false}
            value=""
            onChange={(e) => {
              data.value = e;
            }}
          />
      </div>
      <Handle
        type="source"
        position={Position.Right}
        id={data.type}
        isValidConnection={(connection) => isValidConnection(data, connection)}
        className="-mr-1 bg-transparent border-solid border-l-8 border-y-transparent border-y-8 border-r-0 rounded-none"
        style={{ borderLeftColor: nodeColors[types[data.type]] }}
      ></Handle>
    </div>
  );
}
