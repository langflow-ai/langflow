import { useEffect } from "react";
import { DictComponentType } from "../../types/components";

import DictAreaModal from "../../modals/dictAreaModal";
import { classNames, cn } from "../../utils/utils";
import { Button } from "../ui/button";

export default function DictComponent({
  value = [],
  onChange,
  disabled,
  editNode = false,
  id = "",
}: DictComponentType): JSX.Element {
  // Create a reference to the value

  useEffect(() => {
    if (disabled) {
      onChange({});
    }
  }, [disabled]);

  return (
    <div
      className={classNames(
        value.length > 1 && editNode ? "my-1" : "",
        "flex w-full flex-col gap-3",
        disabled ? "pointer-events-none" : "",
      )}
    >
      {
        <div className="flex w-full gap-3" data-testid={id}>
          <DictAreaModal
            value={value}
            onChange={(obj) => {
              onChange(obj);
            }}
            disabled={disabled}
          >
            <Button
              variant="primary"
              size="sm"
              className={cn("w-full", editNode ? "h-fit px-3 py-0.5" : "")}
              data-testid="dict-input"
            >
              <span>Click to edit your dictionary...</span>
            </Button>
          </DictAreaModal>
        </div>
      }
    </div>
  );
}
