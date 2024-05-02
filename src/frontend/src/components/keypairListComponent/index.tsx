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
  isList = true,
}: KeyPairListComponentType): JSX.Element {
  useEffect(() => {
    if (disabled && value.length > 0 && value[0] !== "") {
      onChange([{ "": "" }]);
    }
  }, [disabled]);

  const checkValueType = (value) => {
    return Array.isArray(value) ? value : [value];
  };

  const ref = useRef<any>([]);
  ref.current =
    !value || value?.length === 0 ? [{ "": "" }] : checkValueType(value);

  useEffect(() => {
    if (JSON.stringify(value) !== JSON.stringify(ref.current)) {
      ref.current = value;
      onChange(value);
    }
  }, [value]);

  const handleChangeKey = (event, idx) => {
    const oldKey = Object.keys(ref.current[idx])[0];
    const updatedObj = { [event.target.value]: ref.current[idx][oldKey] };
    ref.current[idx] = updatedObj;
    onChange(ref.current);
  };

  const handleChangeValue = (newValue, idx) => {
    const key = Object.keys(ref.current[idx])[0];
    ref.current[idx][key] = newValue;
    onChange(ref.current);
  };

  return (
    <div
      className={classNames(
        ref.current?.length > 1 && editNode ? "mx-2 my-1" : "",
        "flex h-full flex-col gap-3"
      )}
    >
      {ref.current?.map((obj, index) => {
        return Object.keys(obj).map((key, idx) => {
          return (
            <div key={idx} className="flex w-full gap-2">
              <Input
                data-testid={
                  editNode ? "editNodekeypair" + index : "keypair" + index
                }
                id={editNode ? "editNodekeypair" + index : "keypair" + index}
                type="text"
                value={key.trim()}
                className={classNames(
                  editNode ? "input-edit-node" : "",
                  duplicateKey ? "input-invalid" : ""
                )}
                placeholder="Type key..."
                onChange={(event) => handleChangeKey(event, index)}
              />

              <Input
                data-testid={
                  editNode
                    ? "editNodekeypair" + (index + 100).toString()
                    : "keypair" + (index + 100).toString()
                }
                id={
                  editNode
                    ? "editNodekeypair" + (index + 100).toString()
                    : "keypair" + (index + 100).toString()
                }
                type="text"
                disabled={disabled}
                value={obj[key]}
                className={editNode ? "input-edit-node" : ""}
                placeholder="Type a value..."
                onChange={(event) =>
                  handleChangeValue(event.target.value, index)
                }
              />

              {isList && index === ref.current.length - 1 ? (
                <button
                  disabled={disabled}
                  onClick={() => {
                    let newInputList = _.cloneDeep(ref.current);
                    newInputList.push({ "": "" });
                    onChange(newInputList);
                  }}
                  id={
                    editNode
                      ? "editNodeplusbtn" + index.toString()
                      : "plusbtn" + index.toString()
                  }
                  data-testid={
                    editNode
                      ? "editNodeplusbtn" + index.toString()
                      : "plusbtn" + index.toString()
                  }
                >
                  <IconComponent
                    name="Plus"
                    className={"h-4 w-4 hover:text-accent-foreground"}
                  />
                </button>
              ) : isList ? (
                <button
                  onClick={() => {
                    let newInputList = _.cloneDeep(ref.current);
                    newInputList.splice(index, 1);
                    onChange(newInputList);
                  }}
                  data-testid={
                    editNode
                      ? "editNodeminusbtn" + index.toString()
                      : "minusbtn" + index.toString()
                  }
                  id={
                    editNode
                      ? "editNodeminusbtn" + index.toString()
                      : "minusbtn" + index.toString()
                  }
                >
                  <IconComponent
                    name="X"
                    className="h-4 w-4 hover:text-status-red"
                  />
                </button>
              ) : (
                ""
              )}
            </div>
          );
        });
      })}
    </div>
  );
}
