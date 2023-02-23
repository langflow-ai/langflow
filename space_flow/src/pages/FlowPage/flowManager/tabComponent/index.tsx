import { PlusIcon, XMarkIcon } from "@heroicons/react/24/solid";
import { useContext, useRef, useState } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";

var _ = require("lodash");

export default function TabComponent({ selected, flow, onClick }) {
  const { removeFlow, updateFlow,flows } = useContext(TabsContext);
  const [isRename, setIsRename] = useState(false);
  const [value, setValue] = useState("");
  return (
    <>
      {flow ? (
        !selected ? (
          <div
            className="flex justify-between select-none truncate w-44 items-center px-4 my-1.5 border-x border-t border-t-transparent border-gray-300 -ml-px"
            onClick={onClick}
          >
            {flow.name}
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeFlow(flow.id);
              }}
            >
              <XMarkIcon className="h-4 hover:bg-white rounded-full" />
            </button>
          </div>
        ) : (
          <div className="bg-white flex select-none justify-between w-44 items-center border border-b-0 border-gray-300 px-4 py-1.5 rounded-t-xl -ml-px">
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
              {flows.length>1&& <XMarkIcon className="h-4 hover:bg-gray-100 rounded-full" />}
            </button>
          </div>
        )
      ) : (
        <div className="h-full py-1.5 flex justify-center items-center">
          <button
            className="px-3 flex items-center h-full pb-0.5 pt-0.5 border-gray-300 -ml-px border-t border-t-transparent"
            onClick={onClick}
          >
            <PlusIcon className="h-5 rounded-full hover:bg-white" />
          </button>
        </div>
      )}
    </>
  );
}
