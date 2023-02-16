import { Bars3CenterLeftIcon, TrashIcon } from "@heroicons/react/24/outline";
import { Input } from "@mui/material";
import { Handle, Position } from "reactflow";
import { isValidConnection, nodeColors } from "../../utils";
import ToggleComponent from "../../components/toggleComponent";
import { useEffect, useState } from "react";

export default function BooleanNode({ data }) {
  const [enabled, setEnabled] = useState(false);
  return (
    <div className="prompt-node relative bg-white rounded-lg solid border flex flex-col justify-center">
      <div className="w-full flex items-center justify-between gap-8 p-4 bg-gray-50 border-b ">
        <div className="flex items-center gap-4 text-lg">
          <Bars3CenterLeftIcon
            className="w-10 h-10 p-1 text-white rounded"
            style={{ background: nodeColors[data.type] }}
          />
          Boolean
        </div>
        <button
          onClick={() => {
            data.onDelete(data);
          }}
        >
          <TrashIcon className="text-gray-600 w-6 h-6 hover:text-red-500"></TrashIcon>
        </button>
      </div>
      <div className="w-full flex justify-center p-5 h-full">
        <ToggleComponent enabled={enabled} setEnabled={(x) => {setEnabled(x); data.enabled = x}} />
      </div>
      <Handle
        type="target"
        position={Position.Right}
        id={data.name}
        isValidConnection={(connection) => isValidConnection(data,connection)}
        className="-mr-1 bg-transparent border-solid border-l-8 border-y-transparent border-y-8 border-r-0 rounded-none"
        style={{ borderLeftColor: nodeColors[data.type] }}
      ></Handle>
    </div>
  );
}
