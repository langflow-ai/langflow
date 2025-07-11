import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cn } from "@/utils/utils";
import { getButtonClassName } from "../helpers/get-class-name";
import { getTestId } from "../helpers/get-test-id";

export const ButtonInputList = ({
  index,
  addNewInput,
  disabled,
  editNode,
  componentName,
  listAddLabel,
}: {
  index: number;
  addNewInput: (e) => void;
  disabled: boolean;
  editNode: boolean;
  componentName: string;
  listAddLabel: string;
}) => {
  return (
    <>
      <ShadTooltip content={listAddLabel} side="top" align="center">
        <div
          onClick={addNewInput}
          className={cn(
            "hit-area-icon group bg-background hover:bg-muted absolute -top-8 right-0 flex items-center justify-center text-center",
            disabled
              ? "bg-background hover:bg-background pointer-events-none"
              : "",
          )}
        >
          <Button
            unstyled
            size="icon"
            className={cn(
              "hit-area-icon flex items-center justify-center",
              getButtonClassName(disabled),
            )}
            data-testid={getTestId("plus", index, editNode, componentName)}
            disabled={disabled}
          >
            <IconComponent
              name="Plus"
              className={cn(
                "icon-size text-muted-foreground justify-self-center",
                !disabled && "hover:text-foreground hover:cursor-pointer",
                "group-hover:text-foreground",
              )}
              strokeWidth={ICON_STROKE_WIDTH}
            />
          </Button>
        </div>
      </ShadTooltip>
    </>
  );
};
