import { Bars3CenterLeftIcon, CheckCircleIcon, TrashIcon } from "@heroicons/react/24/outline";
import { Input } from "@mui/material";
import { Handle, Position } from "reactflow";
import { isValidConnection, nodeColors } from "../../utils";
import ToggleComponent from "../../components/toggleComponent";
import { useContext, useEffect, useState } from "react";
import { typesContext } from "../../contexts/typesContext";

export default function BooleanNode({ data }) {
  const [enabled, setEnabled] = useState(false);
  const {types, deleteNode} = useContext(typesContext);
  return (
    <div className="prompt-node relative bg-white dark:bg-gray-900 rounded-lg solid border dark:border-gray-700 flex flex-col justify-center">
      <div className="w-full flex items-center justify-between gap-8 p-4 bg-gray-50 dark:bg-gray-800 dark:text-white dark:border-b-gray-700 border-b ">
        <div className="flex items-center gap-4 text-lg">
          <CheckCircleIcon
            className="w-10 h-10 p-1 rounded"
            style={{ color: nodeColors[types[data.type]] }}
          />
          Boolean
        </div>
        <button
          onClick={() => {
            deleteNode(data.id);
          }}
        >
          <TrashIcon className="text-gray-600 w-6 h-6 hover:text-red-500"></TrashIcon>
        </button>
      </div>
      <div className="w-full flex justify-center p-5 h-full">
        <ToggleComponent enabled={enabled} disabled={false} setEnabled={(x) => {setEnabled(x); data.value = x}} />
      </div>
      <Handle
        type="source"
        position={Position.Right}
        id={data.type}
        isValidConnection={(connection) => isValidConnection(data,connection)}
        className={"-mr-0.5 w-3 h-3 rounded-full border-2 bg-white dark:bg-gray-800"}
        style={{
          borderColor: nodeColors[types[data.type]],
        }}
      ></Handle>
    </div>
  );
}
