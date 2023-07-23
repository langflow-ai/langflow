import { useContext, useEffect, useState } from "react";
import { InputListComponentType } from "../../types/components";

import _ from "lodash";
import { Plus, X } from "lucide-react";
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
        "flex flex-col gap-3"
      }
    >
      {inputList.map((i, idx) => {
        return (
          <div key={idx} className="flex w-full gap-3">
            <input
              type="text"
              value={i}
              className={
                editNode
                  ? "input-edit-node "
                  : "input-primary " + (disabled ? "input-disable" : "")
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
                <Plus className={"h-4 w-4 hover:text-accent-foreground"} />
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
                <X className="h-4 w-4 hover:text-status-red" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
