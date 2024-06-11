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
  componentName,
  playgroundDisabled,
}: InputListComponentType): JSX.Element {
  useEffect(() => {
    if (disabled && value.length > 0 && value[0] !== "") {
      onChange([""]);
    }
  }, [disabled]);

  // @TODO Recursive Character Text Splitter - the value might be in string format, whereas the InputListComponent specifically requires an array format. To ensure smooth operation and prevent potential errors, it's crucial that we handle the conversion from a string to an array with the string as its element.
  if (typeof value === "string") {
    value = [value];
  }

  if (!value?.length) value = [""];

  return (
    <div
      className={classNames(
        value.length > 1 && editNode ? "my-1" : "",
        "flex flex-col gap-3",
      )}
    >
      {value.map((singleValue, idx) => {
        return (
          <div key={idx} className="flex w-full gap-3">
            <Input
              disabled={disabled || playgroundDisabled}
              type="text"
              value={singleValue}
              className={editNode ? "input-edit-node" : ""}
              placeholder="Type something..."
              onChange={(event) => {
                let newInputList = _.cloneDeep(value);
                newInputList[idx] = event.target.value;
                onChange(newInputList);
              }}
              data-testid={
                `input-list-input${editNode ? "-edit" : ""}_${componentName}-` +
                idx
              }
            />
            {idx === value.length - 1 ? (
              <button
                onClick={(e) => {
                  let newInputList = _.cloneDeep(value);
                  newInputList.push("");
                  onChange(newInputList);
                  e.preventDefault();
                }}
                data-testid={
                  `input-list-plus-btn${
                    editNode ? "-edit" : ""
                  }_${componentName}-` + idx
                }
                disabled={disabled || playgroundDisabled}
              >
                <IconComponent
                  name="Plus"
                  className={"h-4 w-4 hover:text-accent-foreground"}
                />
              </button>
            ) : (
              <button
                data-testid={
                  `input-list-minus-btn${
                    editNode ? "-edit" : ""
                  }_${componentName}-` + idx
                }
                onClick={(e) => {
                  let newInputList = _.cloneDeep(value);
                  newInputList.splice(idx, 1);
                  onChange(newInputList);
                  e.preventDefault();
                }}
                disabled={disabled || playgroundDisabled}
              >
                <IconComponent
                  name="X"
                  className={`h-4 w-4 ${
                    disabled || playgroundDisabled
                      ? ""
                      : "hover:text-accent-foreground"
                  }`}
                />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
