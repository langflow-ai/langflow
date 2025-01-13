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
          <Button
            onClick={addNewInput}
            variant="ghost"
            size="iconMd"
            className={cn(
              "absolute group -translate-y-7 translate-x-[15.0rem]",
              getButtonClassName(disabled),
            )}
            data-testid={getTestId("plus", index, editNode, componentName)}
            disabled={disabled}
          >
            <IconComponent
              name="Plus"
              className={cn(
                "icon-size justify-self-center text-muted-foreground",
                !disabled && "hover:cursor-pointer hover:text-foreground",
                "group-hover:text-foreground",
              )}
              strokeWidth={ICON_STROKE_WIDTH}
            />
          </Button>
      </ShadTooltip>
    </>
  );
};
