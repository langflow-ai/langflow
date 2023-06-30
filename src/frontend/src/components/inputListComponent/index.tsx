import { useContext, useEffect, useState } from "react";
import { InputListComponentType } from "../../types/components";
import { TabsContext } from "../../contexts/tabsContext";

import _ from "lodash";
import { INPUT_DISABLE, INPUT_EDIT_NODE, INPUT_STYLE } from "../../constants";
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
        "flex flex-col gap-3 py-2"
      }
    >
      {inputList.map((i, idx) => {
        return (
          <div key={idx} className="w-full flex gap-3">
            <input
              type="text"
              value={i}
              className={editNode
                ? INPUT_EDIT_NODE
                : INPUT_STYLE +
                (disabled ? INPUT_DISABLE : "")}
              placeholder="Type something..."
              onChange={(e) => {
                setInputList((old) => {
                  let newInputList = _.cloneDeep(old);
                  newInputList[idx] = e.target.value;
                  return newInputList;
                });
                onChange(inputList);
              } } />
            {idx === inputList.length - 1 ? (
              <button
                onClick={() => {
                  setInputList((old) => {
                    let newInputList = _.cloneDeep(old);
                    newInputList.push("");
                    return newInputList;
                  });
                  onChange(inputList);
                } }
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
                } }
              >
                <X className="w-4 h-4 hover:text-status-red" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
