import { cn } from "@/utils/utils";
import {
  NumberDecrementStepper,
  NumberIncrementStepper,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
} from "@chakra-ui/number-input";
import { useEffect, useRef, useState } from "react";
import { IntComponentType } from "../../types/components";
import {
  handleKeyDown,
  handleOnlyIntegerInput,
} from "../../utils/reactflowUtils";
import { Input } from "../ui/input";

export default function IntComponent({
  value,
  onChange,
  rangeSpec,
  disabled,
  editNode = false,
  id = "",
}: IntComponentType): JSX.Element {
  const min = -Infinity;

  // Clear component state
  useEffect(() => {
    if (disabled && value !== "") {
      onChange("", undefined, true);
    }
  }, [disabled, onChange]);

  const [cursor, setCursor] = useState<number | null>(null);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    ref.current?.setSelectionRange(cursor, cursor);
  }, [ref, cursor, value]);

  const handleChangeInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCursor(e.target.selectionStart);
    onChange(e.target.value);
  };

  return (
    <div className="w-full">
      <NumberInput
        id={id}
        step={rangeSpec?.step ?? 1}
        min={rangeSpec?.min ?? min}
        max={rangeSpec?.max ?? undefined}
        onChange={(value) => {
          onChange(value);
        }}
        value={value ?? ""}
      >
        <NumberInputField
          className={cn(
            editNode ? "input-edit-node" : "",
            "nopan nodelete nodrag noflow primary-input",
          )}
          onChange={handleChangeInput}
          onKeyDown={(event) => {
            handleKeyDown(event, value, "");
          }}
          onInput={(event: React.ChangeEvent<HTMLInputElement>) => {
            if (Number(event.target.value) < min) {
              event.target.value = min.toString();
            }
          }}
          disabled={disabled}
          placeholder={editNode ? "Integer number" : "Type an integer number"}
          data-testid={id}
          ref={ref}
        />
        <NumberInputStepper paddingRight={10}>
          <NumberIncrementStepper fontSize={8} marginTop={6} />
          <NumberDecrementStepper fontSize={8} marginBottom={6} />
        </NumberInputStepper>
      </NumberInput>
    </div>
  );
}
