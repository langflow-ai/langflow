import { PlusIcon, XMarkIcon } from "@heroicons/react/24/solid";
import { useContext, useState } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";
import { FlowType } from "../../../../types/flow";

import _ from "lodash";

export default function TabComponent({
  selected,
  flow,
  onClick,
}: {
  flow: FlowType;
  selected: boolean;
  onClick: () => void;
}) {
  const { removeFlow, updateFlow, flows } = useContext(TabsContext);
  const [isRename, setIsRename] = useState(false);
  const [value, setValue] = useState("");
  return (
    <>
      {flow ? (
        !selected ? (
          <div
            className="dark:text-white flex justify-between select-none truncate w-44 items-center px-4 my-1.5 border-x border-x-gray-300 dark:border-x-gray-600 -ml-px"
            onClick={onClick}
          >
            <span className="w-32 truncate text-left">{flow.name}</span>

            <button
              onClick={(e) => {
                e.stopPropagation();
                removeFlow(flow.id);
              }}
            >
              <XMarkIcon className="h-4 hover:bg-white dark:hover:bg-gray-600 rounded-full" />
            </button>
          </div>
        ) : (
          <div className="bg-white dark:text-white dark:bg-gray-700/60 flex select-none justify-between w-44 items-center border border-b-0 border-gray-300 dark:border-gray-600 px-4 py-1 rounded-t-xl -ml-px">
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
              <div className="flex items-center gap-2">
                <span
                  className="text-left w-32 truncate"
                  onDoubleClick={() => {
                    setIsRename(true);
                    setValue(flow.name);
                  }}
                >
                  {flow.name}
                </span>
              </div>
            )}
            <button
              onClick={() => {
                removeFlow(flow.id);
              }}
            >
              {flows.length > 1 && (
                <XMarkIcon className="h-4 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-full" />
              )}
            </button>
          </div>
        )
      ) : (
        <div className="h-full py-1.5 flex justify-center items-center">
          <button
            className="px-3 flex items-center h-full pb-0.5 pt-0.5 border-x-gray-300 dark:border-x-gray-600 dark:text-white -ml-px"
            onClick={onClick}
          >
            <PlusIcon className="h-5 rounded-full hover:bg-white dark:hover:bg-gray-600" />
          </button>
        </div>
      )}
    </>
  );
}
