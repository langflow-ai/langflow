import { PlusIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useContext, useEffect, useState } from "react";
import { InputListComponentType } from "../../types/components";
import { TabsContext } from "../../contexts/tabsContext";

import _ from "lodash";

export default function InputListComponent({
  value,
  onChange,
  disabled,
}: InputListComponentType) {
  const [inputList, setInputList] = useState(value ?? [""]);
  useEffect(() => {
    if (disabled) {
      setInputList([""]);
      onChange([""]);
    }
  }, [disabled, onChange]);
  return (
    <div
      className={
        (disabled ? "pointer-events-none cursor-not-allowed" : "") +
        "flex flex-col gap-3"
      }
    >
      {inputList.map((i, idx) => (
        <div key={idx} className="w-full flex gap-3">
          <input
            type="text"
            value={i}
            className={
              "block w-full form-input rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm" +
              (disabled ? " bg-gray-200" : "")
            }
            placeholder="Type something..."
            onChange={(e) => {
              setInputList((old) => {
                let newInputList = _.cloneDeep(old);
                newInputList[idx] = e.target.value;
                return newInputList;
              });
              onChange(inputList);
            }}
          />
          {idx === inputList.length - 1 ? (
            <button
              onClick={() => {
                setInputList((old) => {
                  let newInputList = _.cloneDeep(old);
                  newInputList.push("");
                  return newInputList;
                });
                onChange(inputList);
              }}
            >
              <PlusIcon className="w-4 h-4 hover:text-blue-600" />
            </button>
          ) : (
            <button
              onClick={() => {
                setInputList((old) => {
                  let newInputList = _.cloneDeep(old);
                  newInputList.splice(idx, 1);
                  return newInputList;
                });
                onChange(inputList);
              }}
            >
              <XMarkIcon className="w-4 h-4 hover:text-red-600" />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
