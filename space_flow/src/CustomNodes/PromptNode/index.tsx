import { Handle, Position } from "reactflow";
import { useContext } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { Transition } from "@headlessui/react";
import { ArrowUpRightIcon, CommandLineIcon, PlayIcon, TrashIcon } from "@heroicons/react/24/outline";
import Dropdown from "../../components/dropdownComponent";
import Input from "../../components/inputComponent";

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
        className="prompt-node relative bg-white h-96 w-96 rounded-lg solid border flex flex-col justify-center"
      >
        <Handle type="source"
        position={Position.Left}
        id="b"
        className="bg-gray-400 w-3 h-3 -ml-0.5"></Handle>
        <div className="w-full flex items-center justify-between p-4 bg-gray-50 border-b ">
          <div className="flex items-center gap-4 text-lg">
            <CommandLineIcon className="w-10 h-10 p-1 bg-sky-600 text-white rounded" />
            Prompt
          </div>
          <ArrowUpRightIcon className="w-4 h-4" />
        </div>
        
        <div className="w-full p-5 h-full">
          <div className="w-full text-gray-500 text-sm truncate">
            {data.template}
          </div>
          <div className="w-full mt-5">
            <Dropdown title="Select item:" value="item" options={["item1", "item2", "item3"]} onSelect={() => {}} />
          </div>
          <div className="w-full mt-5">
            <Input title="Enter text:" placeholder="text" onChange={() => {}} />
          </div>
        </div>
        
        <div className="flex w-full justify-between items-center bg-gray-50 gap-2 border-t text-gray-600 p-4 text-sm">
          <TrashIcon className="w-6 h-6"></TrashIcon>
          <PlayIcon className="w-6 h-6"></PlayIcon>
        </div>
        <Handle type="target"
        position={Position.Right}
        id="b" className="bg-sky-600 w-3 h-3 -mr-0.5"></Handle>
      </div>
    </Transition>
  );
}
