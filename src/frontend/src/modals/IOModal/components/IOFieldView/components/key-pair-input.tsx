import _ from "lodash";
import { nanoid } from "nanoid";
import { useEffect, useState } from "react";
import IconComponent from "../../../../../components/common/genericIconComponent";
import { Input } from "../../../../../components/ui/input";
import { classNames } from "../../../../../utils/utils";

export type IOKeyPairInputProps = {
  value: Record<string, string>;
  onChange: (value: Record<string, string>) => void;
  duplicateKey: boolean;
  isList: boolean;
  isInputField?: boolean;
  testId?: string;
};

type Row = { id: string; key: string; value: string };

const arrayToObject = (arr: Row[]) => {
  return arr.reduce((obj, item) => {
    obj[item.key] = item.value;
    return obj;
  }, {});
};

const objectToArray = (obj: Record<string, string>, oldData: Row[] = []) => {
  const keys = Object.keys(obj || {});
  if (keys.length === 0) {
    return [{ key: "", value: "", id: nanoid() }];
  }
  return keys.map((key) => {
    const oldItem = oldData.find((item) => item.key === key);
    return oldItem || { key, value: obj[key] || "", id: nanoid() };
  });
};

const IOKeyPairInput = ({
  value,
  onChange,
  duplicateKey,
  isList = true,
  isInputField,
  testId,
}: IOKeyPairInputProps) => {
  const [data, setData] = useState<Row[]>(objectToArray(value, []));

  useEffect(() => {
    setData((oldData) => objectToArray(value, oldData));
  }, [value, setData]);

  const handleKeyChange = (id: string, newKey: string) => {
    const item = data.find((item) => item.id === id);
    if (item) {
      const newData = data.map((item) =>
        item.id === id ? { ...item, key: newKey } : item,
      );
      setData(newData);
      if (newData.filter((kv) => kv.key === newKey).length > 1) {
        return; // Prevent updating on duplicate keys
      }
      onChange(arrayToObject(newData));
    }
  };

  const handleValueChange = (id: string, newValue: string) => {
    const item = data.find((item) => item.id === id);
    if (item) {
      const newData = data.map((item) =>
        item.id === id ? { ...item, value: newValue } : item,
      );
      setData(newData);
      if (newData.filter((kv) => kv.key === item.key).length > 1) {
        return; // Prevent updating on duplicate keys
      }
      onChange(arrayToObject(newData));
    }
  };

  return (
    <div className={classNames("flex h-full flex-col gap-3")}>
      {data.map((item, idx) => {
        return (
          <div key={item.id} className="flex w-full gap-2">
            <Input
              type="text"
              value={item.key.trim()}
              className={classNames(duplicateKey ? "input-invalid" : "")}
              placeholder="Type key..."
              onChange={(event) => handleKeyChange(item.id, event.target.value)}
              disabled={!isInputField}
              data-testid={testId ? `${testId}-key-${idx}` : undefined}
            />

            <Input
              type="text"
              value={item.value}
              placeholder="Type a value..."
              onChange={(event) =>
                handleValueChange(item.id, event.target.value)
              }
              disabled={!isInputField}
              data-testid={testId ? `${testId}-value-${idx}` : undefined}
            />

            {isList && isInputField && idx === data.length - 1 ? (
              <button
                type="button"
                onClick={() => {
                  const newData = [
                    ...data,
                    { key: "", value: "", id: nanoid() },
                  ];
                  setData(newData);
                  onChange(arrayToObject(newData));
                }}
                data-testid={testId ? `${testId}-plus-btn-0` : undefined}
              >
                <IconComponent
                  name="Plus"
                  className={"h-4 w-4 hover:text-accent-foreground"}
                />
              </button>
            ) : isList && isInputField ? (
              <button
                type="button"
                onClick={() => {
                  const newData = data.filter((value) => value.id !== item.id);
                  setData(newData);
                  onChange(arrayToObject(newData));
                }}
                data-testid={testId ? `${testId}-minus-btn-${idx}` : undefined}
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
      })}
    </div>
  );
};

export default IOKeyPairInput;
