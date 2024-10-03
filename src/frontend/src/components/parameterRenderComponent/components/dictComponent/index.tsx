import { useEffect } from "react";

import DictAreaModal from "../../../../modals/dictAreaModal";
import { classNames, cn } from "../../../../utils/utils";
import ForwardedIconComponent from "../../../genericIconComponent";
import { Button } from "../../../ui/button";
import { InputProps } from "../../types";

export default function DictComponent({
  value = [],
  handleOnNewValue,
  disabled,
  editNode = false,
  id = "",
}: InputProps<object | object[] | string>): JSX.Element {
  useEffect(() => {
    if (disabled) {
      handleOnNewValue({ value: {} });
    }
  }, [disabled]);

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
              <ForwardedIconComponent name="BookMarked" className="h-4 w-4" />
              Edit Dictionary
            </Button>
          </DictAreaModal>
        </div>
      }
    </div>
  );
}
