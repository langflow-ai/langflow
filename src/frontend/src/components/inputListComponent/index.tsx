import { useContext, useEffect, useState } from "react";
import { InputListComponentType } from "../../types/components";
import { TabsContext } from "../../contexts/tabsContext";

import _ from "lodash";
import { INPUT_STYLE } from "../../constants";
import { X, Plus } from "lucide-react";

export default function InputListComponent({
  value,
  onChange,
  disabled,
  editNode = false,
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
              editNode
                ? "border-[1px]  truncate cursor-pointer text-center placeholder:text-center text-ring block w-full pt-0.5 pb-0.5 form-input rounded-md border-ring shadow-sm sm:text-sm" +
                  INPUT_STYLE
                : "block w-full form-input bg-background rounded-md border-ring shadow-sm focus:border-ring focus:ring-ring sm:text-sm" +
                  (disabled ? " bg-input" : "") +
                  "focus:placeholder-transparent"
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
              <Plus className={"w-4 h-4 hover:text-ring"} />
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
              <X className="w-4 h-4 hover:text-status-red" />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
