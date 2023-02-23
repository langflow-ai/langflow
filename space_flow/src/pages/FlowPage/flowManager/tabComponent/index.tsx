import { PlusIcon, XMarkIcon } from "@heroicons/react/24/solid";
import { useContext, useRef, useState } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";

var _ = require("lodash");

export default function TabComponent({ selected, flow, onClick }) {
  const { removeFlow, updateFlow } = useContext(TabsContext);
  const [isRename, setIsRename] = useState(false);
  const [value, setValue] = useState("");
  return (
    <>
      {flow ? (
        !selected ? (
          <div
            className="flex justify-between select-none truncate w-44 items-center px-4 my-2 mt-3 border-x border-gray-300 -ml-px"
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
          <div className="bg-white flex select-none justify-between w-44 items-center pt-3 border border-b-0 border-gray-300 px-4 py-2 rounded-t-xl -ml-px">
            {isRename ? (
              <input
                autoFocus
                className="bg-transparent focus:border-none active:outline hover:outline focus:outline outline-gray-300 rounded-md  w-28"
                onBlur={() => {
                  setIsRename(false);
                  if (value !== "") {
                    let newFlow = _.cloneDeep(flow);
                    newFlow.name = value;
                    updateFlow(newFlow);
                  }
                }}
                value={value}
                onChange={(e) => {
                  setValue(e.target.value);
                }}
              />
            ) : (
              <span
                className="text-left truncate"
                onDoubleClick={() => {
                  setIsRename(true);
                  setValue(flow.name);
                }}
              >
                {flow.name}
              </span>
            )}
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
