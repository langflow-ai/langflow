import _ from "lodash";
import { useRef } from "react";
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

  const ref = useRef<any>([]);
  ref.current =
    !value || value?.length === 0 ? [{ "": "" }] : checkValueType(value);

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
    <>
      <div className={classNames("flex h-full flex-col gap-3")}>
        {ref.current?.map((obj, index) => {
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

                {isList && isInputField && index === ref.current.length - 1 ? (
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
                ) : isList && isInputField ? (
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
