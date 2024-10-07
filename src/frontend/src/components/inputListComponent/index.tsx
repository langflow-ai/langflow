import { useEffect } from "react";
import { InputListComponentType } from "../../types/components";

import _ from "lodash";
import { classNames, cn } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

export default function InputListComponent({
  value,
  onChange,
  disabled,
  editNode = false,
  componentName,
  playgroundDisabled,
  id,
}: InputListComponentType): JSX.Element {
  useEffect(() => {
    if (disabled && value.length > 0 && value[0] !== "") {
      onChange([""], undefined, true);
    }
  }, [disabled]);

  // @TODO Recursive Character Text Splitter - the value might be in string format, whereas the InputListComponent specifically requires an array format. To ensure smooth operation and prevent potential errors, it's crucial that we handle the conversion from a string to an array with the string as its element.
  if (typeof value === "string") {
    value = [value];
  }

  if (!value?.length) value = [""];

  const handleInputChange = (index, newValue) => {
    const newInputList = _.cloneDeep(value);
    newInputList[index] = newValue;
    onChange(newInputList);
  };

  const addNewInput = (e) => {
    e.preventDefault();
    const newInputList = _.cloneDeep(value);
    newInputList.push("");
    onChange(newInputList);
  };

  const removeInput = (index, e) => {
    e.preventDefault();
    const newInputList = _.cloneDeep(value);
    newInputList.splice(index, 1);
    onChange(newInputList);
  };

  const getButtonClassName = () =>
    classNames(
      disabled || playgroundDisabled
        ? "cursor-not-allowed text-muted-foreground"
        : "text-primary hover:text-accent-foreground",
    );

  const getTestId = (type, index) =>
    `input-list-${type}-btn${editNode ? "-edit" : ""}_${componentName}-${index}`;

  return (
    <div
      className={classNames(
        value.length > 1 && editNode ? "my-1" : "",
        "flex w-full flex-col gap-3",
      )}
    >
      {value.map((singleValue, index) => (
        <div key={index} className="flex w-full gap-3">
          <Input
            disabled={disabled || playgroundDisabled}
            type="text"
            value={singleValue}
            className={editNode ? "input-edit-node" : ""}
            placeholder="Type something..."
            onChange={(event) => handleInputChange(index, event.target.value)}
            data-testid={`${id}_${index}`}
          />
          <Button
            unstyled
            className={getButtonClassName()}
            onClick={index === 0 ? addNewInput : (e) => removeInput(index, e)}
            data-testid={getTestId(index === 0 ? "plus" : "minus", index)}
            disabled={disabled || playgroundDisabled}
          >
            <IconComponent
              name={index === 0 ? "Plus" : "X"}
              className="h-4 w-4"
            />
          </Button>
        </div>
      ))}
    </div>
  );
}
