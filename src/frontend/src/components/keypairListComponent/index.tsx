import { useEffect, useRef } from "react";
import { KeyPairListComponentType } from "../../types/components";

import _ from "lodash";
import { classNames } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Input } from "../ui/input";

export default function KeypairListComponent({
  value,
  onChange,
  disabled,
  editNode = false,
  duplicateKey,
}: KeyPairListComponentType): JSX.Element {
  useEffect(() => {
    if (disabled) {
      onChange([""]);
    }
  }, [disabled]);

  const ref = useRef(value.length === 0 ? [{ "": "" }] : value);

  useEffect(() => {
    if (JSON.stringify(value) !== JSON.stringify(ref.current)) {
      ref.current = value;
      onChange(value);
    }
  }, [value]);

  const handleChangeKey = (event, idx) => {
    const newInputList = _.cloneDeep(ref.current);
    const oldKey = Object.keys(newInputList[idx])[0];
    const updatedObj = { [event.target.value]: newInputList[idx][oldKey] };
    newInputList[idx] = updatedObj;
    onChange(newInputList);
  };

  const handleChangeValue = (newValue, idx) => {
    const newInputList = _.cloneDeep(ref.current);
    const key = Object.keys(newInputList[idx])[0];
    newInputList[idx][key] = newValue;
    onChange(newInputList);
  };

  return (
    <div
      className={classNames(
        ref.current?.length > 1 && editNode ? "my-1" : "",
        "flex h-full flex-col gap-3"
      )}
    >
      {ref.current?.map((obj, index) => {
        return Object.keys(obj).map((key, idx) => {
          return (
            <div key={idx} className="flex w-full gap-3">
              <Input
                type="text"
                value={key.trim()}
                className={classNames(
                  editNode ? "input-edit-node" : "",
                  duplicateKey ? "input-invalid" : ""
                )}
                placeholder="Type key..."
                onChange={(event) => handleChangeKey(event, index)}
                onKeyDown={(e) => {
                  if (e.ctrlKey && e.key === "Backspace") {
                    e.preventDefault();
                    e.stopPropagation();
                  }
                }}
              />

              <Input
                type="text"
                value={obj[key]}
                className={editNode ? "input-edit-node" : ""}
                placeholder="Type a value..."
                onChange={(event) =>
                  handleChangeValue(event.target.value, index)
                }
              />

              {index === ref.current.length - 1 ? (
                <button
                  onClick={() => {
                    let newInputList = _.cloneDeep(ref.current);
                    newInputList.push({ "": "" });
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
                    let newInputList = _.cloneDeep(ref.current);
                    newInputList.splice(index, 1);
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
        });
      })}
    </div>
  );
}
