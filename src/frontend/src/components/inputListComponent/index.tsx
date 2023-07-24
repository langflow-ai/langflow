import { useEffect } from "react";
import { InputListComponentType } from "../../types/components";

import _ from "lodash";
import IconComponent from "../genericIconComponent";

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

  return (
    <div
      className={
        (disabled ? "pointer-events-none cursor-not-allowed" : "") +
        "flex flex-col gap-3"
      }
    >
      {value.map((i, idx) => {
        return (
          <div key={idx} className="flex w-full gap-3">
            <input
              type="text"
              value={i}
              className={
                "nopan nodrag noundo nocopy " +
                (editNode
                  ? "input-edit-node "
                  : "input-primary " + (disabled ? "input-disable" : ""))
              }
              placeholder="Type something..."
              onChange={(e) => {
                let newInputList = _.cloneDeep(value);
                newInputList[idx] = e.target.value;
                onChange(newInputList);
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
