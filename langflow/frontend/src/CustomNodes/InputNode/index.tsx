import { Bars3CenterLeftIcon, TrashIcon } from "@heroicons/react/24/outline";
import InputComponent from "../../components/inputComponent";
import {
  isValidConnection,
  nodeColors,
} from "../../utils";
import { Handle, Position } from "reactflow";
import { useContext } from "react";
import Tooltip from "../../components/TooltipComponent";
import { typesContext } from "../../contexts/typesContext";
import { NodeDataType } from "../../types/flow";

export default function InputNode({ data }:{data:NodeDataType}) {
  console.log(data)
  const {types, deleteNode,reactFlowInstance} = useContext(typesContext);
  return (
    <div className="prompt-node relative bg-white dark:bg-gray-900 w-96 rounded-lg solid border dark:border-gray-700 flex flex-col justify-center">
      <Tooltip title="Prefix: str">
        <Handle
          type="target"
          position={Position.Left}
          id={"str|Prefix|" + data.id}
          isValidConnection={(connection) =>
            isValidConnection(connection,reactFlowInstance)
          }
          className={"-ml-0.5 w-3 h-3 rounded-full border-2 bg-white dark:bg-gray-800"}
          style={{
            borderColor: nodeColors[types[data.type]],
          }}
        ></Handle>
      </Tooltip>

      <div className="w-full flex items-center justify-between p-4 gap-8 bg-gray-50 dark:bg-gray-800 dark:text-white border-b dark:border-b-gray-700 ">
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
        isValidConnection={(connection) => isValidConnection(connection,reactFlowInstance)}
        className={"-mr-0.5 w-3 h-3 rounded-full border-2 bg-white dark:bg-gray-800"}
        style={{
          borderColor: nodeColors[types[data.type]],
        }}
      ></Handle>
    </div>
  );
}
