import { PlusIcon, XMarkIcon } from "@heroicons/react/24/solid";
import { useContext } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";

export default function TabComponent({ selected, flow, onClick }) {
  const { removeFlow } = useContext(TabsContext);
  return (
    <>
      {flow ? (
        !selected ? (
          <div
            className="flex justify-between select-none w-36 items-center px-4 my-2 mt-3 border-x border-gray-300 -ml-px"
            onClick={onClick}
          >
            {flow.name}
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeFlow(flow.id);
              }}
            >
              <XMarkIcon className="h-4" />
            </button>
          </div>
        ) : (
          <div className="bg-white flex select-none justify-between w-36 items-center pt-3 border border-b-0 border-gray-300 px-4 py-2 rounded-t-xl -ml-px">
            {flow.name}
            <button
              onClick={() => {
                removeFlow(flow.id);
              }}
            >
              <XMarkIcon className="h-4" />
            </button>
          </div>
        )
      ) : (
        <div className="h-full py-2 pt-3 flex justify-center items-center">
          <button
            className="px-3 h-full border-gray-300 -ml-px"
            onClick={onClick}
          >
            <PlusIcon className="h-5" />
          </button>
        </div>
      )}
    </>
  );
}
