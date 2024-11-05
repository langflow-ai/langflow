import { useEffect } from "react";

import { ICON_STROKE_WIDTH } from "@/constants/constants";
import _ from "lodash";
import { classNames, cn } from "../../../../utils/utils";
import IconComponent from "../../../genericIconComponent";
import { Button } from "../../../ui/button";
import { Input } from "../../../ui/input";
import { InputListComponentType, InputProps } from "../../types";

export default function InputListComponent({
  value = [""],
  handleOnNewValue,
  disabled,
  editNode = false,
  componentName,
  id,
}: InputProps<string[], InputListComponentType>): JSX.Element {
  useEffect(() => {
    if (disabled && value.length > 0 && value[0] !== "") {
      handleOnNewValue({ value: [""] }, { skipSnapshot: true });
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
    handleOnNewValue({ value: newInputList });
  };

  const addNewInput = (e) => {
    e.preventDefault();
    const newInputList = _.cloneDeep(value);
    newInputList.push("");
    handleOnNewValue({ value: newInputList });
  };

  const removeInput = (index, e) => {
    e.preventDefault();
    const newInputList = _.cloneDeep(value);
    newInputList.splice(index, 1);
    handleOnNewValue({ value: newInputList });
  };

  const getButtonClassName = () =>
    classNames(disabled ? "text-hard-zinc" : "text-placeholder-foreground");

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
        <div key={index} className="flex w-full items-center gap-3">
          <Input
            disabled={disabled}
            type="text"
            value={singleValue}
            className={cn(
              editNode ? "input-edit-node" : "",
              disabled ? "disabled-state" : "",
            )}
            placeholder="Type something..."
            onChange={(event) => handleInputChange(index, event.target.value)}
            data-testid={`${id}_${index}`}
          />
          <div
            onClick={index === 0 ? addNewInput : (e) => removeInput(index, e)}
            className={cn(
              "hit-area-icon group flex items-center justify-center text-center",
              disabled
                ? "pointer-events-none bg-background hover:bg-background"
                : "",
              index === 0
                ? "bg-background hover:bg-muted"
                : "hover:bg-smooth-red",
            )}
          >
            <Button
              unstyled
              size="icon"
              className={cn(
                "hit-area-icon flex items-center justify-center",
                getButtonClassName(),
              )}
              data-testid={getTestId(index === 0 ? "plus" : "minus", index)}
              disabled={disabled}
            >
              <IconComponent
                name={index === 0 ? "Plus" : "Trash2"}
                className={cn(
                  "icon-size justify-self-center text-muted-foreground",
                  !disabled && "hover:cursor-pointer hover:text-foreground",
                  index === 0
                    ? "group-hover:text-foreground"
                    : "group-hover:text-destructive",
                )}
                strokeWidth={ICON_STROKE_WIDTH}
              />
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
