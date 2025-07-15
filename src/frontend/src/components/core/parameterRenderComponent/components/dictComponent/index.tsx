import { useEffect } from "react";

import { ICON_STROKE_WIDTH } from "@/constants/constants";
import DictAreaModal from "../../../../../modals/dictAreaModal";
import { classNames, cn, toTitleCase } from "../../../../../utils/utils";
import ForwardedIconComponent from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import type { InputProps } from "../../types";

export default function DictComponent({
  value,
  handleOnNewValue,
  disabled,
  editNode = false,
  id = "",
  name = "",
}: InputProps<object | object[] | string, { name: string }>): JSX.Element {
  useEffect(() => {
    if (disabled || value === null) {
      handleOnNewValue({ value: {} }, { skipSnapshot: true });
    }
  }, [disabled]);
  const placeholderName = `Edit ${toTitleCase(name)}`;

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
                "hover:bg-mute w-full font-medium text-primary",
                editNode ? "h-fit px-3 py-0.5" : "",
              )}
              data-testid={editNode ? `edit_${id}` : `${id}`}
            >
              <ForwardedIconComponent
                strokeWidth={ICON_STROKE_WIDTH}
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
