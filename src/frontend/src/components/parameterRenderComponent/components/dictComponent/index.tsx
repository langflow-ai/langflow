import { useEffect } from "react";

import DictAreaModal from "../../../../modals/dictAreaModal";
import { classNames, cn, toTitleCase } from "../../../../utils/utils";
import ForwardedIconComponent from "../../../genericIconComponent";
import { Button } from "../../../ui/button";
import { InputProps } from "../../types";

export default function DictComponent({
  value = [],
  handleOnNewValue,
  disabled,
  editNode = false,
  id = "",
  name = "",
}: InputProps<object | object[] | string, { name: string }>): JSX.Element {
  useEffect(() => {
    if (disabled) {
      handleOnNewValue({ value: {} }, { skipSnapshot: true });
    }
  }, [disabled]);
  const placeholderName = `Edit ${toTitleCase(name)}`;

  console.log(placeholderName);
  return (
    <div
      className={classNames(
        "flex w-full flex-col gap-3",
        disabled ? "pointer-events-none" : "",
      )}
    >
      {
        <div className="flex w-full gap-3" data-testid={id}>
          <DictAreaModal
            value={(value || "").toString() === "{}" ? {} : value}
            onChange={(obj) => {
              handleOnNewValue({ value: obj });
            }}
            disabled={disabled}
          >
            <Button
              variant="primary"
              size="sm"
              className={cn(
                "w-full font-normal",
                editNode ? "h-fit px-3 py-0.5" : "",
              )}
              data-testid="dict-input"
            >
              <ForwardedIconComponent
                strokeWidth={2}
                name="Code"
                className="h-4 w-4"
              />
              {placeholderName}
            </Button>
          </DictAreaModal>
        </div>
      }
    </div>
  );
}
