import { useContext, useEffect, useState } from "react";
import { InputListComponentType } from "../../types/components";
import { TabsContext } from "../../contexts/tabsContext";

import _ from "lodash";
import { INPUT_STYLE } from "../../constants";
import { X, Plus } from "lucide-react";
import { PopUpContext } from "../../contexts/popUpContext";

export default function InputListComponent({
  value,
  onChange,
  disabled,
  editNode = false,
  onAddInput,
}: InputListComponentType) {
  const [inputList, setInputList] = useState(value ?? [""]);
  const { closePopUp } = useContext(PopUpContext);

  useEffect(() => {
    if (disabled) {
      setInputList([""]);
      onChange([""]);
    }
  }, [disabled, onChange]);

  useEffect(() => {
    setInputList(value);
  }, [closePopUp]);

  return (
    <div
      className={
        (disabled ? "pointer-events-none cursor-not-allowed" : "") +
        "flex flex-col gap-3 py-2"
      }
    >
      {inputList.map((i, idx) => (
        <div key={idx} className="flex w-full gap-3">
          <input
            type="text"
            value={i}
            className={
              editNode
                ? "form-input  block w-full cursor-pointer truncate rounded-md border-[1px] border-ring pb-0.5 pt-0.5 text-center text-ring shadow-sm placeholder:text-center sm:text-sm" +
                  INPUT_STYLE
                : "form-input block w-full rounded-md border-ring bg-background shadow-sm focus:border-ring focus:ring-ring sm:text-sm" +
                  (disabled ? " bg-input" : "") +
                  "focus:placeholder-transparent"
            }
            placeholder="Type something..."
            onChange={(e) => {
              setInputList((old) => {
                let newInputList = _.cloneDeep(old);
                newInputList[idx] = e.target.value;
                onChange(newInputList);
                return newInputList;
              });
            }}
          />
          {idx === inputList.length - 1 ? (
            <button
              onClick={() => {
                setInputList((old) => {
                  let newInputList = _.cloneDeep(old);
                  newInputList.push("");
                  onAddInput(newInputList);
                  return newInputList;
                });
                onChange(inputList);
              }}
            >
              <Plus className={"h-4 w-4 hover:text-ring"} />
            </button>
          ) : (
            <button
              onClick={() => {
                setInputList((old) => {
                  let newInputList = _.cloneDeep(old);
                  newInputList.splice(idx, 1);
                  onAddInput(newInputList);
                  return newInputList;
                });
                onChange(inputList);
              }}
            >
              <X className="h-4 w-4 hover:text-status-red" />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
