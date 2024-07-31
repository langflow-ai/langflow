import { useEffect, useState } from "react";
import { KeyPairListComponentType } from "../../types/components";

import {
  convertObjToArray,
  convertValuesToNumbers,
  hasDuplicateKeys,
} from "@/utils/reactflowUtils";
import { cloneDeep } from "lodash";
import { classNames } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Input } from "../ui/input";

export default function KeypairListComponent({
  value,
  onChange,
  disabled,
  editNode = false,
  isList = true,
  id,
}: KeyPairListComponentType): JSX.Element {
  useEffect(() => {
    if (disabled && value.length > 0 && value[0] !== "") {
      onChange([{ "": "" }]);
    }
  }, [disabled]);

  const [duplicateKey, setDuplicateKey] = useState(false);

  const myValue =
    Object.keys(value || {})?.length === 0 || !value
      ? [{ "": "" }]
      : convertObjToArray(value, "dict");

  Array.isArray(value) ? value : [value];

  const handleNewValue = (newValue: any) => {
    const valueToNumbers = convertValuesToNumbers(newValue);
    setDuplicateKey(hasDuplicateKeys(valueToNumbers));
    if (isList) {
      onChange(valueToNumbers);
    } else onChange(valueToNumbers[0]);
  };

  const handleChangeKey = (event, idx) => {
    const oldKey = Object.keys(myValue[idx])[0];
    const updatedObj = { [event.target.value]: myValue[idx][oldKey] };

    const newValue = cloneDeep(myValue);
    newValue[idx] = updatedObj;

    handleNewValue(newValue);
  };

  const handleChangeValue = (event, idx) => {
    const key = Object.keys(myValue[idx])[0];
    const updatedObj = { [key]: event.target.value };

    const newValue = cloneDeep(myValue);
    newValue[idx] = updatedObj;

    handleNewValue(newValue);
  };

  return (
    <div
      className={classNames(
        myValue?.length > 1 && editNode ? "mx-2 my-1" : "",
        "flex h-full flex-col gap-3",
      )}
    >
      {myValue?.map((obj, index) => {
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
                  duplicateKey ? "input-invalid" : "",
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
                onChange={(event) => handleChangeValue(event, index)}
              />

              {isList && index === myValue.length - 1 ? (
                <button
                  disabled={disabled}
                  onClick={() => {
                    let newInputList = cloneDeep(myValue);
                    newInputList.push({ "": "" });
                    onChange(newInputList);
                  }}
                  id={
                    editNode
                      ? "editNodeplusbtn" + index.toString()
                      : "plusbtn" + index.toString()
                  }
                  data-testid={id}
                >
                  <IconComponent
                    name="Plus"
                    className={"h-4 w-4 hover:text-accent-foreground"}
                  />
                </button>
              ) : isList ? (
                <button
                  onClick={() => {
                    let newInputList = cloneDeep(myValue);
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
