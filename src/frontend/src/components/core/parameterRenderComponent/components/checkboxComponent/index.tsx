import { useEffect } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/utils/utils";
import type { CheckboxComponentType, InputProps } from "../../types";

export default function CheckboxComponent({
  disabled,
  value,
  options = [],
  handleOnNewValue,
  editNode = false,
  id = "",
}: InputProps<string[], CheckboxComponentType>): JSX.Element {
  // Ensure value is always an array
  const treatedValue = Array.isArray(value) ? value : value ? [value] : [];

  useEffect(() => {
    if (disabled && treatedValue.length > 0) {
      handleOnNewValue({ value: [] }, { skipSnapshot: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled]);

  const handleCheckboxChange = (option: string, checked: boolean) => {
    if (checked) {
      // Add option to the array if not already present
      if (!treatedValue.includes(option)) {
        handleOnNewValue({ value: [...treatedValue, option] });
      }
    } else {
      // Remove option from the array
      handleOnNewValue({ value: treatedValue.filter((v) => v !== option) });
    }
  };

  if (options.length === 0) {
    return (
      <div>
        <span className="text-sm italic">
          No checkbox options are available for display.
        </span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "grid grid-cols-2 gap-2",
        editNode ? "input-edit-node" : "",
      )}
      onClick={(e) => e.stopPropagation()}
    >
      {options.map((option, index) => {
        const isChecked = treatedValue.includes(option);
        return (
          <div
            key={`${option}-${index}`}
            className="flex items-center space-x-2"
          >
            <Checkbox
              id={`${id}-checkbox-${index}`}
              data-testid={`${id}-checkbox-${index}`}
              checked={isChecked}
              disabled={disabled}
              onCheckedChange={(checked) =>
                handleCheckboxChange(option, checked as boolean)
              }
            />
            <label
              htmlFor={`${id}-checkbox-${index}`}
              className={cn(
                "text-sm font-medium leading-none cursor-pointer",
                disabled && "cursor-not-allowed opacity-50",
                !isChecked && "text-muted-foreground",
              )}
            >
              {option}
            </label>
          </div>
        );
      })}
    </div>
  );
}
