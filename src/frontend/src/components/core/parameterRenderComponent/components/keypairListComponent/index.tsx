import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import {
  convertObjToArray,
  convertValuesToNumbers,
  hasDuplicateKeys,
} from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
import IconComponent from "../../../../common/genericIconComponent";

const KeypairListComponent = ({
  value,
  handleOnNewValue,
  disabled,
  editNode = false,
  isList = true,
  id,
  showParameter = true,
  ariaLabelledBy,
}) => {
  const { t } = useTranslation();
  const getTestId = (prefix, index) =>
    `${editNode ? "editNode" : ""}${prefix}${index}`;
  const valueQualifierId = `${id}-value-qualifier`;

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

  // biome-ignore lint/suspicious/noExplicitAny: legacy
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
        // Icon-only button, no visible text — found missing a discernible
        // name by axe while adding an unrelated a11y test to this widget.
        aria-label={
          isFirstItem
            ? t("input.addKeyValuePair")
            : t("input.removeKeyValuePair")
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

  // Row 1 stands in for the field itself, so it needs no positional
  // qualifier; every later row does, or a screen reader user hears the same
  // name on every row of the list and cannot tell them apart.
  const getRowQualifierId = (index: number) =>
    index === 0 ? undefined : `${id}-row-${index}-qualifier`;

  const describedByFor = (index: number, isValue: boolean) => {
    if (!ariaLabelledBy) return undefined;
    return [
      ariaLabelledBy,
      isValue ? valueQualifierId : null,
      getRowQualifierId(index),
    ]
      .filter(Boolean)
      .join(" ");
  };

  const renderKeyValuePair = (obj, index) =>
    Object.keys(obj).map((key, idx) => (
      <div key={idx} className="flex w-full items-center gap-2">
        {index > 0 && (
          <span id={getRowQualifierId(index)} className="sr-only">
            {t("input.rowQualifier", { index: index + 1 })}
          </span>
        )}
        <Input
          data-testid={getTestId("keypair", index)}
          id={getTestId("keypair", index)}
          type="text"
          value={key.trim()}
          disabled={disabled}
          className={getInputClassName(editNode, duplicateKey)}
          placeholder={t("input.typeKey")}
          onChange={(event) => handleChangeKey(event, index)}
          aria-labelledby={describedByFor(index, false)}
        />
        <Input
          data-testid={getTestId("keypair", index + 100)}
          id={getTestId("keypair", index + 100)}
          type="text"
          disabled={disabled}
          value={obj[key]}
          className={editNode ? "input-edit-node" : ""}
          placeholder={t("input.typeValue")}
          onChange={(event) => handleChangeValue(event, index)}
          // The field label alone would make the two inputs of a row
          // indistinguishable — the qualifier turns it into "<field> value"
          // vs "<field>".
          aria-labelledby={describedByFor(index, true)}
        />
        <div className="hit-area-icon">
          {isList && renderActionButton(index)}
        </div>
      </div>
    ));

  if (!showParameter) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex h-full flex-col gap-3",
        values?.length > 1 && editNode && "mx-2 my-1",
      )}
    >
      <span id={valueQualifierId} className="sr-only">
        {t("input.valueQualifier")}
      </span>
      {values?.map((obj, index) => renderKeyValuePair(obj, index))}
    </div>
  );
};

export default KeypairListComponent;
