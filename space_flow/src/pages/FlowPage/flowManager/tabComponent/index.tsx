import { PlusIcon, XMarkIcon } from "@heroicons/react/24/solid";
import { useContext } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";
import { classNames } from "../../../../utils";

export default function TabComponent({ selected, flow, id, onClick}) {
	const { removeFlow, flows } = useContext(TabsContext);
	return (
		<>
      {flow ? (
        selected ? (
          <button
            className="px-4 my-2 mt-3 border-l border-gray-300 -ml-px"
            onClick={onClick}
          >
            {flow.name}
          </button>
        ) : (
          <div className="bg-white pt-3 pointer-events-none border border-b-0 border-gray-300 px-4 py-2 rounded-t-xl">
            {flow.name}
          </div>
        )
      ) : (
        <div className="h-full py-2 pt-3 flex justify-center items-center">
          <button className="px-3 h-full border-l border-gray-300 -ml-px">
            <PlusIcon className="h-5" />
          </button>
        </div>
      )}
    </>
    )}