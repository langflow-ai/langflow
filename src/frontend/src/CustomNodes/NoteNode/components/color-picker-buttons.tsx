import { memo } from "react";
import { Button } from "@/components/ui/button";
import { COLOR_OPTIONS } from "@/constants/constants";
import type { noteDataType } from "@/types/flow";
import { cn } from "@/utils/utils";

export const ColorPickerButtons = memo(
  ({
    bgColor,
    data,
    setNode,
  }: {
    bgColor: string;
    data: noteDataType;
    setNode: (id: string, updater: any) => void;
  }) => (
    <div className="flew-row flex gap-3">
      {Object.entries(COLOR_OPTIONS).map(([color, code]) => (
        <Button
          data-testid={`color_picker_button_${color}`}
          unstyled
          key={color}
          onClick={() => {
            setNode(data.id, (old) => ({
              ...old,
              data: {
                ...old.data,
                node: {
                  ...old.data.node,
                  template: {
                    ...old.data.node?.template,
                    backgroundColor: color,
                  },
                },
              },
            }));
          }}
        >
          <div
            className={cn(
              "h-4 w-4 rounded-full hover:border hover:border-ring",
              bgColor === color ? "border-2 border-blue-500" : "",
              code === null && "border",
            )}
            style={{
              backgroundColor: code ?? "#00000000",
            }}
          />
        </Button>
      ))}
    </div>
  ),
);

ColorPickerButtons.displayName = "ColorPickerButtons";
