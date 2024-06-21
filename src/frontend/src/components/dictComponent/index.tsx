import { useEffect } from "react";
import { DictComponentType } from "../../types/components";

import DictAreaModal from "../../modals/dictAreaModal";
import { classNames } from "../../utils/utils";
import { Input } from "../ui/input";

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
            <Input
              type="text"
              className={
                editNode
                  ? "input-edit-node input-disable pointer-events-none cursor-pointer"
                  : "input-disable pointer-events-none cursor-pointer"
              }
              placeholder={disabled ? "" : "Click to edit your dictionary..."}
              data-testid="dict-input"
            />
          </DictAreaModal>
        </div>
      }
    </div>
  );
}
