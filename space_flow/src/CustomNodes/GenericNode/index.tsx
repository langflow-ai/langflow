import {
  ArrowUpRightIcon,
  TrashIcon,
  PlayIcon,
} from "@heroicons/react/24/outline";
import { Handle, Position } from "reactflow";
import Dropdown from "../../components/dropdownComponent";
import Input from "../../components/inputComponent";
import { nodeColors, nodeIcons, snakeToNormalCase } from "../../utils";
import Tooltip from "../../components/TooltipComponent";

export default function GenericNode({ data }) {
  const Icon = nodeIcons[data.type];
  return (
    <div className="prompt-node relative bg-white w-96 rounded-lg solid border flex flex-col justify-center">
      <div className="w-full flex items-center justify-between p-4 bg-gray-50 border-b ">
        <div className="flex items-center gap-4 text-lg">
          <Icon
            className="w-10 h-10 p-1 text-white rounded"
            style={{ background: nodeColors[data.type] }}
          />
          {data.name}
        </div>
      </div>

      <div className="w-full p-5 h-full">
        <div className="w-full text-gray-500 text-sm truncate">
          {data.node.description}
        </div>
        {Object.keys(data.node.template).map((t, idx) => (
          <div key={idx} className="w-full mt-5">
            <Tooltip title={t + ": " + data.node.template[t].type}>
              <Handle
                type="source"
                position={Position.Left}
                id={data.node.template[t].type}
                isValidConnection={({ sourceHandle, targetHandle }) =>
                  targetHandle === sourceHandle ||
                  data.types[targetHandle] === sourceHandle ||
                  sourceHandle === "str"
                }
                className="ml-1 bg-transparent border-solid border-l-8 border-y-transparent border-y-8 border-r-0 rounded-none"
                style={{
                  borderLeftColor: nodeColors[data.type],
                  marginTop: idx * 30 - 50 + "px",
                }}
              ></Handle>
            </Tooltip>
          </div>
        ))}
        <div className="w-full mt-5"></div>
      </div>

      <div className="flex w-full justify-between items-center bg-gray-50 gap-2 border-t text-gray-600 p-4 text-sm">
        <button onClick={data.onDelete}>
          <TrashIcon className="w-6 h-6 hover:text-red-500"></TrashIcon>
        </button>
      </div>
      <Tooltip title={"Output: " + data.name}>
        <Handle
          type="target"
          position={Position.Right}
          id={data.name}
          isValidConnection={({ sourceHandle, targetHandle }) =>
            targetHandle === sourceHandle ||
            data.types[targetHandle] === sourceHandle ||
            sourceHandle === "str"
          }
          className="-mr-1 bg-transparent border-solid border-l-8 border-y-transparent border-y-8 border-r-0 rounded-none"
          style={{ borderLeftColor: nodeColors[data.type] }}
        ></Handle>
      </Tooltip>
    </div>
  );
}
