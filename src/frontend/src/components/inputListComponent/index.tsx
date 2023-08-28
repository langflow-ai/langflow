import { useEffect } from "react";
import { InputListComponentType } from "../../types/components";

import _ from "lodash";
import { classNames } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Input } from "../ui/input";

export default function InputListComponent({
  value,
  onChange,
  disabled,
  editNode = false,
}: InputListComponentType) {
  useEffect(() => {
    if (disabled) {
      onChange([""]);
    }
  }, [disabled]);

  // In certain cases, the value might be in string format, whereas the InputListComponent specifically requires an array format. To ensure smooth operation and prevent potential errors, it's crucial that we handle the conversion from a string to an array with the string as its element.
  typeof value === 'string' ? value = [value] : value = value;

  return (
    <div
      className={classNames(
        value.length > 1 && editNode ? "my-1" : "",
        "flex flex-col gap-3"
      )}
    >
      {value.map((i, idx) => {
        return (
          <div key={idx} className="flex w-full gap-3">
            <Input
              disabled={disabled}
              type="text"
              value={i}
              className={editNode ? "input-edit-node" : ""}
              placeholder="Type something..."
              onChange={(e) => {
                let newInputList = _.cloneDeep(value);
                newInputList[idx] = e.target.value;
                onChange(newInputList);
              }}
              onKeyDown={(e) => {
                if (e.ctrlKey && e.key === "Backspace") {
                  e.preventDefault();
                  e.stopPropagation();
                }
              }}
            />
            {idx === value.length - 1 ? (
              <button
                onClick={() => {
                  let newInputList = _.cloneDeep(value);
                  newInputList.push("");
                  onChange(newInputList);
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
                  let newInputList = _.cloneDeep(value);
                  newInputList.splice(idx, 1);
                  onChange(newInputList);
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
