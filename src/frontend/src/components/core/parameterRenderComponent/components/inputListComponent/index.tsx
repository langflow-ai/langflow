import _ from "lodash";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "../../../../ui/input";
import { ButtonInputList } from "./components/button-input-list";
import { DropdownMenuInputList } from "./components/dropdown-menu";

import { GRADIENT_CLASS } from "@/constants/constants";
import { cn } from "../../../../../utils/utils";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { InputListComponentType, InputProps } from "../../types";
import { DeleteButtonInputList } from "./components/delete-button-input-list";

export default function InputListComponent({
  value = [""],
  handleOnNewValue,
  disabled,
  editNode = false,
  componentName,
  id,
  placeholder,
  listAddLabel,
}: InputProps<string[], InputListComponentType>): JSX.Element {
  const [dropdownOpen, setDropdownOpen] = useState<number | null>(null);
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (disabled && value.length > 0 && value[0] !== "") {
      handleOnNewValue({ value: [""] }, { skipSnapshot: true });
    }
  }, [disabled, handleOnNewValue, value]);

  if (typeof value === "string") {
    value = [value];
  }
  if (!value?.length) value = [""];

  const handleInputChange = useCallback(
    (index: number, newValue: string) => {
      const newInputList = _.cloneDeep(value);
      newInputList[index] = newValue;
      handleOnNewValue({ value: newInputList });
    },
    [value, handleOnNewValue],
  );

  const addNewInput = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const newInputList = _.cloneDeep(value);
      newInputList.push("");
      handleOnNewValue({ value: newInputList });
    },
    [value, handleOnNewValue],
  );

  const removeInput = useCallback(
    (index: number, e: React.MouseEvent | KeyboardEvent) => {
      e.preventDefault();
      const newInputList = _.cloneDeep(value);
      newInputList.splice(index, 1);
      handleOnNewValue({ value: newInputList });
      setDropdownOpen(null);
    },
    [value, handleOnNewValue],
  );

  // const handleDuplicateInput = useCallback(
  //   (index: number, e: React.MouseEvent | KeyboardEvent) => {
  //     e.preventDefault();
  //     const newInputList = _.cloneDeep(value);
  //     newInputList.splice(index, 0, newInputList[index]);
  //     handleOnNewValue({ value: newInputList });
  //     setDropdownOpen(null);
  //   },
  //   [value, handleOnNewValue],
  // );

  return (
    <div className={cn("w-full", editNode && "max-h-52")}>
      {!editNode && !disabled && (
        <ButtonInputList
          index={0}
          addNewInput={addNewInput}
          disabled={disabled}
          editNode={editNode}
          componentName={componentName || ""}
          listAddLabel={listAddLabel || "Add More"}
        />
      )}

      <div className="mt-2 flex w-full flex-col gap-3">
        {value.map((singleValue, index) => (
          <div key={index} className="flex w-full items-center">
            {focusedIndex !== index && !disabled && (
              <div
                className={cn(
                  "absolute z-50 h-6 w-16",
                  editNode ? "translate-x-[12rem]" : "translate-x-[11.1rem]",
                )}
                style={{
                  pointerEvents: "none",
                  background: GRADIENT_CLASS,
                }}
                aria-hidden="true"
              />
            )}
            <div className="group relative flex-1">
              <Input
                ref={index === 0 ? inputRef : null}
                disabled={disabled}
                type="text"
                value={singleValue}
                className={cn(
                  "w-full pr-10 text-primary",
                  editNode ? "input-edit-node" : "",
                  disabled ? "disabled-state" : "",
                )}
                placeholder={getPlaceholder(disabled, placeholder)}
                onChange={(event) =>
                  handleInputChange(index, event.target.value)
                }
                data-testid={`${id}_${index}`}
                onFocus={() => setFocusedIndex(index)}
                onBlur={() => setFocusedIndex(null)}
              />

              {value.length > 1 && (
                <div className="absolute right-2 top-1/2 -translate-y-1/2">
                  <DeleteButtonInputList
                    index={index}
                    removeInput={(e) => removeInput(index, e)}
                    disabled={disabled}
                    editNode={editNode}
                    componentName={componentName || ""}
                  />
                </div>
              )}

              {/* 
              We will add this back in a future release
              {!disabled && (
                <DropdownMenuInputList
                  index={index}
                  dropdownOpen={dropdownOpen!}
                  setDropdownOpen={setDropdownOpen}
                  editNode={editNode}
                  handleDuplicateInput={handleDuplicateInput}
                  removeInput={removeInput}
                  canDelete={value.length > 1}
                />
              )} */}
            </div>
          </div>
        ))}
        {editNode && !disabled && (
          <Button
            unstyled
            onClick={addNewInput}
            className="btn-add-input-list"
            data-testid={`input-list-add-more-${editNode ? "edit" : "view"}`}
          >
            <span className="mr-2 text-lg">+</span> {listAddLabel || "Add More"}
          </Button>
        )}
      </div>
    </div>
  );
}
