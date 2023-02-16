import { Bars3CenterLeftIcon, TrashIcon } from "@heroicons/react/24/outline";
import Input from "../../components/inputComponent";
import { nodeColors, nodeIcons, snakeToNormalCase } from "../../utils";
import { Handle, Position } from "reactflow";

export default function InputNode({ data }) {
  return (
    <div className="prompt-node relative bg-white w-96 rounded-lg solid border flex flex-col justify-center">
      <div className="w-full flex items-center justify-between p-4 bg-gray-50 border-b ">
        <div className="flex items-center gap-4 text-lg">
          <Bars3CenterLeftIcon
            className="w-10 h-10 p-1 text-white rounded"
            style={{ background: nodeColors[data.type] }}
          />
          String
        </div>
      </div>
      <div className="w-full p-5 h-full">
        <Input
          onChange={(e) => {
            data.text = e;
          }}
        />
      </div>

      <div className="flex w-full justify-between items-center bg-gray-50 gap-2 border-t text-gray-600 p-4 text-sm">
        <button onClick={() => {data.onDelete(data)}}>
          <TrashIcon className="w-6 h-6 hover:text-red-500"></TrashIcon>
        </button>
        <button onClick={data.onRun}></button>
      </div>
      <Handle
        type="target"
        position={Position.Right}
        id="b"
        className="-mr-1 bg-transparent border-solid border-l-8 border-y-transparent border-y-8 border-r-0 rounded-none"
        style={{borderLeftColor: nodeColors[data.type]}}
      ></Handle>
    </div>
  );
}
