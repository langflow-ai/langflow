import { useEffect } from "react";
import { KeyPairListComponent } from "../../types/components";

import _ from "lodash";
import { TypeModal } from "../../constants/enums";
import GenericModal from "../../modals/genericModal";
import { classNames } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Input } from "../ui/input";

export default function KeypairListComponent({
  value,
  onChange,
  disabled,
  editNode = false,
}: KeyPairListComponent): JSX.Element {
  useEffect(() => {
    if (disabled) {
      onChange([""]);
    }
  }, [disabled]);

  const handleChangeKey = (event, idx) => {
    const newInputList = _.cloneDeep(value);
    const oldKey = Object.keys(newInputList[idx])[0];
    let counter = 1;
    let newKey = event.target.value;
    while (newInputList.some(obj => Object.keys(obj)[0] === newKey)) {
      newKey = `${event.target.value}_${counter}`;
      counter++;
    }
    newInputList[idx] = { [newKey]: newInputList[idx][oldKey] };
    onChange(newInputList);
  };
  
  const handleChangeValue = (newValue, idx) => {
    const newInputList = _.cloneDeep(value);
    const key = Object.keys(newInputList[idx])[0];
    newInputList[idx][key] = newValue;
    onChange(newInputList);
  };

  return (
    <div
      className={classNames(
        value.length > 1 && editNode ? "my-1" : "",
        "flex flex-col gap-3"
      )}
    >
      {value.map((obj, index) => {
        return Object.keys(obj).map((key, idx) => {
          return (
            <div key={idx} className="flex w-full gap-3">
              <Input
                disabled={disabled}
                type="text"
                value={key}
                className={editNode ? "input-edit-node" : ""}
                placeholder="Type key..."
                onChange={(event) => handleChangeKey(event, index)}
                onKeyDown={(e) => {
                  if (e.ctrlKey && e.key === "Backspace") {
                    e.preventDefault();
                    e.stopPropagation();
                  }
                }}
              />
              <GenericModal
                type={TypeModal.TEXT}
                value={obj[key]}
                buttonText="Save"
                modalTitle="Edit Value"
                setValue={(value: string) => {
                  handleChangeValue(value, index);
                }}
              >
                <Input
                  disabled={true}
                  type="text"
                  value={obj[key]}
                  className={editNode ? "input-edit-node cursor-pointer" : "cursor-pointer"}
                  placeholder="Click to input a value..."
                />
              </GenericModal>

              {index === value.length - 1 ? (
                <button
                  onClick={() => {
                    let newInputList = _.cloneDeep(value);
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
                    let newInputList = _.cloneDeep(value);
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
