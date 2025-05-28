import { Input } from "@/components/ui/input";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import {
  convertObjToArray,
  convertValuesToNumbers,
  hasDuplicateKeys,
} from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import IconComponent from "../../../../common/genericIconComponent";

const KeypairListComponent = ({
  value,
  handleOnNewValue,
  disabled,
  editNode = false,
  isList = true,
  id,
}) => {
  const getTestId = (prefix, index) =>
    `${editNode ? "editNode" : ""}${prefix}${index}`;

  useEffect(() => {
    if (disabled && value.length > 0 && value[0] !== "") {
      handleOnNewValue({ value: [{ "": "" }] }, { skipSnapshot: true });
    }
  }, [disabled]);

  const [duplicateKey, setDuplicateKey] = useState(false);

  const values =
    Object.keys(value || {})?.length === 0 || !value
      ? [{ "": "" }]
      : convertObjToArray(value, "dict");

  Array.isArray(value) ? value : [value];

  const handleNewValue = (newValue: any) => {
    const valueToNumbers = convertValuesToNumbers(newValue);
    setDuplicateKey(hasDuplicateKeys(valueToNumbers));
    if (isList) {
      handleOnNewValue({ value: valueToNumbers });
    } else handleOnNewValue({ value: valueToNumbers[0] });
  };

  const handleChangeKey = (event, idx) => {
    const oldKey = Object.keys(values[idx])[0];
    const updatedObj = { [event.target.value]: values[idx][oldKey] };

    const newValue = cloneDeep(values);
    newValue[idx] = updatedObj;

    handleNewValue(newValue);
  };

  const handleChangeValue = (event, idx) => {
    const key = Object.keys(values[idx])[0];
    const updatedObj = { [key]: event.target.value };

    const newValue = cloneDeep(values);
    newValue[idx] = updatedObj;

    handleNewValue(newValue);
  };

  const addNewKeyValuePair = () => {
    const newValues = cloneDeep(values);
    newValues.push({ "": "" });
    handleOnNewValue({ value: newValues });
  };

  const removeKeyValuePair = (index) => {
    const newValues = cloneDeep(values);
    newValues.splice(index, 1);
    handleOnNewValue({ value: newValues });
  };

  const getInputClassName = (isEditNode, isDuplicateKey) => {
    return `${isEditNode ? "input-edit-node" : ""} ${isDuplicateKey ? "input-invalid" : ""}`.trim();
  };

  const renderActionButton = (index) => {
    const isFirstItem = index === 0;
    const action = isFirstItem
      ? addNewKeyValuePair
      : () => removeKeyValuePair(index);
    const iconName = isFirstItem ? "Plus" : "Trash2";

    return (
      <button
        disabled={disabled}
        onClick={action}
        id={
          isFirstItem
            ? getTestId("plusbtn", index)
            : getTestId("minusbtn", index)
        }
        data-testid={id}
        className={cn(
          "hit-area-icon group flex items-center justify-center",
          disabled
            ? "pointer-events-none bg-background hover:bg-background"
            : "",
          isFirstItem ? "bg-background hover:bg-muted" : "hover:bg-smooth-red",
        )}
      >
        <IconComponent
          name={iconName}
          className={cn(
            "icon-size justify-self-center text-muted-foreground",
            !disabled && "hover:cursor-pointer hover:text-foreground",
            isFirstItem
              ? "group-hover:text-foreground"
              : "group-hover:text-destructive",
          )}
          strokeWidth={ICON_STROKE_WIDTH}
        />
      </button>
    );
  };

  const renderKeyValuePair = (obj, index) =>
    Object.keys(obj).map((key, idx) => (
      <div key={idx} className="flex w-full items-center gap-2">
        <Input
          data-testid={getTestId("keypair", index)}
          id={getTestId("keypair", index)}
          type="text"
          value={key.trim()}
          className={getInputClassName(editNode, duplicateKey)}
          placeholder="Type key..."
          onChange={(event) => handleChangeKey(event, index)}
        />
        <Input
          data-testid={getTestId("keypair", index + 100)}
          id={getTestId("keypair", index + 100)}
          type="text"
          disabled={disabled}
          value={obj[key]}
          className={editNode ? "input-edit-node" : ""}
          placeholder="Type a value..."
          onChange={(event) => handleChangeValue(event, index)}
        />
        <div className="hit-area-icon">
          {isList && renderActionButton(index)}
        </div>
      </div>
    ));

  return (
    <div
      className={cn(
        "flex h-full flex-col gap-3",
        values?.length > 1 && editNode && "mx-2 my-1",
      )}
    >
      {values?.map((obj, index) => renderKeyValuePair(obj, index))}
    </div>
  );
};

export default KeypairListComponent;
