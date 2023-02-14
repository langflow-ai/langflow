import {
  CommandLineIcon,
  ArrowUpRightIcon,
  TrashIcon,
  PlayIcon,
} from "@heroicons/react/24/outline";
import { Handle, Position } from "reactflow";
import Dropdown from "../../components/dropdownComponent";
import Input from "../../components/inputComponent";
import { nodeColors, nodeIcons } from "../../utils";

export default function GenericNode({ data, onDelete, onRun }) {
  const Icon = nodeIcons[data.type];
  return (
    <div className="prompt-node relative bg-white h-96 w-96 rounded-lg solid border flex flex-col justify-center">
      <Handle
        type="source"
        position={Position.Left}
        id="b"
        className="bg-gray-400 w-3 h-3 -ml-0.5"
      ></Handle>
      <div className="w-full flex items-center justify-between p-4 bg-gray-50 border-b ">
        <div className="flex items-center gap-4 text-lg">
          <Icon
            className="w-10 h-10 p-1 text-white rounded"
            style={{ background: nodeColors[data.type] }}
          />
          {data.name}
        </div>
        <ArrowUpRightIcon className="w-4 h-4" />
      </div>

      <div className="w-full p-5 h-full">
        <div className="w-full text-gray-500 text-sm truncate">
          {data.description}
        </div>
        {data.template.map((t) => (
          <div className="w-full mt-5">
            {t.type === "dropdown" ? (
              <Dropdown
                title={t.title}
                value={t.options[0]}
                options={t.options}
                onSelect={() => {}}
              />
            ) : t.type === "input" ? (
              <Input
                title={t.title}
                placeholder={t.placeholder}
                onChange={() => {}}
              />
            ) : (
              <></>
            )}
          </div>
        ))}
        <div className="w-full mt-5"></div>
      </div>

      <div className="flex w-full justify-between items-center bg-gray-50 gap-2 border-t text-gray-600 p-4 text-sm">
        <button onClick={onDelete}>
          <TrashIcon className="w-6 h-6"></TrashIcon>
        </button>
        <button onClick={onRun}>
          <PlayIcon className="w-6 h-6"></PlayIcon>
        </button>
      </div>
      <Handle
        type="target"
        position={Position.Right}
        id="b"
        className=" w-3 h-3 -mr-0.5"
        style={{ background: nodeColors[data.type] }}
      ></Handle>
    </div>
  );
}
