import { useEffect, useState, useContext } from "react";
import { InputListComponentType } from "../../types/components";

import _, { set } from "lodash";
import IconComponent from "../genericIconComponent";
import { Input } from "../ui/input";
import { classNames } from "../../utils/utils";
import { PopUpContext } from "../../contexts/popUpContext";

export default function InputListComponent({
  value,
  onChange,
  disabled,
  editNode = false,
  onAddInput,
}: InputListComponentType) {
  const [inputList, setInputList] = useState(value ?? [""]);
  const { closeEdit } = useContext(PopUpContext);

  useEffect(() => {
    if (value) {
      setInputList(value);
    }
  }, [closeEdit]);

  useEffect(() => {
    if (disabled) {
      setInputList([""]);
      onChange([""]);
    }
  }, [disabled, onChange]);

  return (
    <div 
    className={
    classNames(
      inputList.length > 1 && editNode ? "my-1" : "",
      "flex flex-col gap-3"
    )
  }>
      {inputList.map((i, idx) => {
        return (
          <div key={idx} className="flex w-full gap-3">
            <Input
              disabled={disabled}
              type="text"
              value={i}
              className={editNode ? "input-edit-node" : ""}
              placeholder="Type something..."
              onChange={(e) => {
                setInputList((old) => {
                  let newInputList = _.cloneDeep(inputList);
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
                <IconComponent
                  name="Plus"
                  className={"h-4 w-4 hover:text-accent-foreground"}
                />
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
                <IconComponent
                  name="X"
                  className="h-4 w-4 hover:text-status-red"
                />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
