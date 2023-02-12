import { Transition } from "@headlessui/react";
import { Handle, Position } from "reactflow";

export default function MemoryNode({ data }) {
  return (
    <Transition
      appear={true}
      show={true}
      enter="transition ease-out duration-100"
      enterFrom="transform opacity-0 scale-95"
      enterTo="transform opacity-100 scale-100"
      leave="transition ease-in duration-75"
      leaveFrom="transform opacity-100 scale-100"
      leaveTo="transform opacity-0 scale-95"
    >
      <div
        onClick={data.delete}
        className="memory-node relative bg-white h-16 w-40 border rounded-sm solid border-black flex flex-col justify-center"
      >
        <Handle type="source" position={Position.Left}></Handle>
        <label className="absolute cursor-grab text-sm -top-3 left-1 bg-white w-14 text-center">
          Memory
        </label>
        <div className="w-full h-min text-xs text-center">
          Memory
        </div>
        <Handle type="target" position={Position.Right}></Handle>
      </div>
    </Transition>
  );
}
