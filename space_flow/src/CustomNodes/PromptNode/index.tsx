import { Handle, Position } from "reactflow";
import { useContext } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { Transition } from "@headlessui/react";

export default function PromptNode({ data }) {
  const { openPopUp } = useContext(PopUpContext);
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
        onClick={() =>
          openPopUp(<div className="absolute top-1/2 left-1/2">teste</div>)
        }
        className="prompt-node relative bg-white h-16 w-40 border rounded-sm solid border-black flex flex-col justify-center"
      >
        <Handle type="source" position={Position.Left}></Handle>
        <label className="absolute cursor-grab text-sm -top-3 left-1 bg-white w-14 text-center">
          Prompt
        </label>
        <div className="w-full h-10 truncate bg-slate-50 text-xs">
          {data.template}
        </div>
        <Handle type="target" position={Position.Right}></Handle>
      </div>
    </Transition>
  );
}
