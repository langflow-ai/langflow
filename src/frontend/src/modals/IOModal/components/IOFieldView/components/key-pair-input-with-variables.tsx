import { nanoid } from "nanoid";
import { useEffect, useState } from "react";
import IconComponent from "../../../../../components/common/genericIconComponent";
import InputComponent from "../../../../../components/core/parameterRenderComponent/components/inputComponent";
import { Input } from "../../../../../components/ui/input";
import { useGetGlobalVariables } from "../../../../../controllers/API/queries/variables";
import { classNames } from "../../../../../utils/utils";

export type KeyPairRow = {
  id: string;
  key: string;
  value: string;
  error: boolean;
};

export type IOKeyPairInputWithVariablesProps = {
  value: KeyPairRow[];
  onChange: (value: KeyPairRow[]) => void;
  duplicateKey: boolean;
  isList: boolean;
  isInputField?: boolean;
  testId?: string;
  enableGlobalVariables?: boolean;
};

const IOKeyPairInputWithVariables = ({
  value,
  onChange,
  duplicateKey,
  isList = true,
  isInputField,
  testId,
  enableGlobalVariables = false,
}: IOKeyPairInputWithVariablesProps) => {
  const { data: globalVariables = [] } = useGetGlobalVariables();
  const [selectedGlobalVariables, setSelectedGlobalVariables] = useState<
    Record<string, string>
  >({});

  const globalVariableOptions = globalVariables.map((gv) => gv.name);

  // Initialize selectedGlobalVariables when value changes or global variables load
  useEffect(() => {
    if (globalVariables.length > 0 && value.length > 0) {
      const initialSelected: Record<string, string> = {};
      value.forEach((item) => {
        // Check if the value matches a global variable name
        if (globalVariableOptions.includes(item.value)) {
          initialSelected[item.id] = item.value;
        }
      });
      setSelectedGlobalVariables(initialSelected);
    }
  }, [globalVariables.length, value.length]);

  const handleKeyChange = (id: string, newKey: string) => {
    const item = value.find((item) => item.id === id);
    if (item) {
      const isDuplicate =
        value.filter((kv) => kv.id !== id && kv.key === newKey).length > 0;
      const newValue = value.map((row) =>
        row.id === id ? { ...row, key: newKey, error: isDuplicate } : row,
      );
      onChange(newValue);
    }
  };

  const handleValueChange = (id: string, newValue: string) => {
    const item = value.find((item) => item.id === id);
    if (item) {
      // Keep error state for value changes
      const newValues = value.map((row) =>
        row.id === id ? { ...row, value: newValue } : row,
      );
      onChange(newValues);
    }
  };

  const handleGlobalVariableSelect = (id: string, variableName: string) => {
    setSelectedGlobalVariables((prev) => ({
      ...prev,
      [id]: variableName,
    }));
    // Update the value with the global variable reference
    handleValueChange(id, variableName);
  };

  const handleAddRow = () => {
    const newValue = [
      ...value,
      { key: "", value: "", id: nanoid(), error: false },
    ];
    onChange(newValue);
  };

  const handleDeleteRow = (item: KeyPairRow) => {
    const seen = new Set<string>();
    const newValue = value
      .filter((value) => value.id !== item.id)
      .map((row) => {
        const isDuplicate = row.key !== "" && seen.has(row.key);
        seen.add(row.key);
        return { ...row, error: isDuplicate };
      });
    onChange(newValue);

    // Clean up selected global variable for this row
    setSelectedGlobalVariables((prev) => {
      const newState = { ...prev };
      delete newState[item.id];
      return newState;
    });
  };

  return (
    <div className={classNames("flex h-full flex-col gap-3")}>
      {value.map((item, idx) => {
        return (
          <div key={item.id} className="flex w-full gap-2">
            <Input
              type="text"
              value={item.key.trim()}
              className={classNames(item.error ? "input-invalid" : "")}
              placeholder={
                item.error ? "Duplicate or empty key" : "Type key..."
              }
              onChange={(event) => handleKeyChange(item.id, event.target.value)}
              disabled={!isInputField}
              data-testid={testId ? `${testId}-key-${idx}` : undefined}
            />

            {enableGlobalVariables ? (
              <InputComponent
                value={item.value}
                onChange={(newValue) => handleValueChange(item.id, newValue)}
                disabled={!isInputField}
                placeholder="Type a value..."
                selectedOption={selectedGlobalVariables[item.id] || ""}
                setSelectedOption={(option) =>
                  handleGlobalVariableSelect(item.id, option)
                }
                options={globalVariableOptions}
                optionsPlaceholder="Search global variables..."
                optionsIcon="Globe"
                nodeStyle
                password={false}
                id={`${testId}-value-${idx}`}
                editNode={false}
              />
            ) : (
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
            )}

            {isList && isInputField && idx === value.length - 1 ? (
              <button
                type="button"
                onClick={handleAddRow}
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
                onClick={() => handleDeleteRow(item)}
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

export default IOKeyPairInputWithVariables;
