import _ from "lodash";
import { useEffect, useState } from "react";
import IconComponent from "../../../../../components/common/genericIconComponent";
import { Input } from "../../../../../components/ui/input";
import { classNames } from "../../../../../utils/utils";

export type IOKeyPairInputProps = {
  value: any;
  onChange: (value: any) => void;
  duplicateKey: boolean;
  isList: boolean;
  isInputField?: boolean;
};

const IOKeyPairInput = ({
  value,
  onChange,
  duplicateKey,
  isList = true,
  isInputField,
}: IOKeyPairInputProps) => {
  const checkValueType = (value) => {
    return Array.isArray(value) ? value : [value];
  };

  const [currentData, setCurrentData] = useState<any[]>(() => {
    return !value || value?.length === 0 ? [{ "": "" }] : checkValueType(value);
  });

  // Update internal state when external value changes
  useEffect(() => {
    const newData =
      !value || value?.length === 0 ? [{ "": "" }] : checkValueType(value);
    setCurrentData(newData);
  }, [value]);

  const handleChangeKey = (event, idx) => {
    const oldKey = Object.keys(currentData[idx])[0];
    const updatedObj = { [event.target.value]: currentData[idx][oldKey] };
    const newData = [...currentData];
    newData[idx] = updatedObj;
    setCurrentData(newData);
    onChange(newData);
  };

  const handleChangeValue = (newValue, idx) => {
    const key = Object.keys(currentData[idx])[0];
    const newData = [...currentData];
    newData[idx] = { ...newData[idx], [key]: newValue };
    setCurrentData(newData);
    onChange(newData);
  };

  return (
    <>
      <div className={classNames("flex h-full flex-col gap-3")}>
        {currentData?.map((obj, index) => {
          return Object.keys(obj).map((key, idx) => {
            return (
              <div key={idx} className="flex w-full gap-2">
                <Input
                  type="text"
                  value={key.trim()}
                  className={classNames(duplicateKey ? "input-invalid" : "")}
                  placeholder="Type key..."
                  onChange={(event) => handleChangeKey(event, index)}
                  disabled={!isInputField}
                />

                <Input
                  type="text"
                  value={obj[key]}
                  placeholder="Type a value..."
                  onChange={(event) =>
                    handleChangeValue(event.target.value, index)
                  }
                  disabled={!isInputField}
                />

                {isList && isInputField && index === currentData.length - 1 ? (
                  <button
                    type="button"
                    onClick={() => {
                      let newInputList = _.cloneDeep(currentData);
                      newInputList.push({ "": "" });
                      setCurrentData(newInputList);
                      onChange(newInputList);
                    }}
                  >
                    <IconComponent
                      name="Plus"
                      className={"hover:text-accent-foreground h-4 w-4"}
                    />
                  </button>
                ) : isList && isInputField ? (
                  <button
                    type="button"
                    onClick={() => {
                      let newInputList = _.cloneDeep(currentData);
                      newInputList.splice(index, 1);
                      setCurrentData(newInputList);
                      onChange(newInputList);
                    }}
                  >
                    <IconComponent
                      name="X"
                      className="hover:text-status-red h-4 w-4"
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
    </>
  );
};

export default IOKeyPairInput;
