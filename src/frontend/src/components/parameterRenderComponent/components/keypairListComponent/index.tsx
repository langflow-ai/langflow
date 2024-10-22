import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import React from "react";
import IconComponent from "../../../genericIconComponent";

const KeyValuePairComponent = ({
  values,
  editNode,
  duplicateKey,
  disabled,
  isList,
  handleChangeKey,
  handleChangeValue,
  addNewKeyValuePair,
  removeKeyValuePair,
  getTestId,
  getInputClassName,
}) => {
  const renderActionButton = (index) => {
    const isFirstItem = index === 0;
    const action = isFirstItem
      ? addNewKeyValuePair
      : () => removeKeyValuePair(index);
    const iconName = isFirstItem ? "Plus" : "Trash2";
    const testId = isFirstItem
      ? getTestId("plusbtn", index)
      : getTestId("minusbtn", index);

    return (
      <button
        disabled={disabled}
        onClick={action}
        id={testId}
        data-testid={testId}
        className={cn(
          "group flex h-6 w-6 items-center justify-center rounded-sm",
          disabled
            ? "pointer-events-none bg-background hover:bg-background"
            : "",
          isFirstItem
            ? "bg-background hover:bg-secondary"
            : "hover:bg-smooth-red",
        )}
      >
        <IconComponent
          name={iconName}
          className={cn(
            "h-4 w-6 text-placeholder",
            !disabled && "hover:cursor-pointer hover:text-foreground",
            isFirstItem
              ? "group-hover:text-foreground"
              : "group-hover:text-destructive",
          )}
          strokeWidth={2}
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
        {isList && renderActionButton(index)}
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

export default KeyValuePairComponent;
