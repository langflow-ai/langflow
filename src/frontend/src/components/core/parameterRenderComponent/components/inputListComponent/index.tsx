import { useEffect, useRef } from "react";

import _ from "lodash";
import { classNames, cn } from "../../../../../utils/utils";
import { Input } from "../../../../ui/input";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { InputListComponentType, InputProps } from "../../types";
import { ButtonInputList } from "./components/button-input-list";

export default function InputListComponent({
  value = [""],
  handleOnNewValue,
  disabled,
  editNode = false,
  componentName,
  id,
  placeholder,
}: InputProps<string[], InputListComponentType>): JSX.Element {
  useEffect(() => {
    if (disabled && value.length > 0 && value[0] !== "") {
      handleOnNewValue({ value: [""] }, { skipSnapshot: true });
    }
  }, [disabled]);
  const inputRef = useRef<HTMLInputElement>(null);

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
            ref={index === 0 ? inputRef : null}
            className={cn(
              editNode ? "input-edit-node" : "",
              disabled ? "disabled-state" : "",
              "peer relative",
              index === 0 && value.length > 1 && "w-3/4 pr-7 focus:pr-3",
            )}
            placeholder={getPlaceholder(disabled, placeholder)}
            onChange={(event) => handleInputChange(index, event.target.value)}
            data-testid={`${id}_${index}`}
          />
          {index === 0 && value.length > 1 && (
            <ButtonInputList
              index={index}
              value={value}
              addNewInput={addNewInput}
              removeInput={removeInput}
              disabled={disabled}
              editNode={editNode}
              addIcon
              componentName={componentName || ""}
            />
          )}
          <ButtonInputList
            index={index}
            value={value}
            addNewInput={addNewInput}
            removeInput={removeInput}
            disabled={disabled}
            editNode={editNode}
            addIcon={false}
            componentName={componentName || ""}
          />
        </div>
      ))}
    </div>
  );
}
