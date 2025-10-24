import { type ChangeEvent, memo, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { COLOR_OPTIONS } from "@/constants/constants";
import type { NoteDataType } from "@/types/flow";
import { cn } from "@/utils/utils";
import { getHexFromPreset, isHexColor } from "../color-utils";

export const ColorPickerButtons = memo(
  ({
    bgColor,
    data,
    setNode,
  }: {
    bgColor: string;
    data: NoteDataType;
    setNode: (id: string, updater: any) => void;
  }) => {
    // Convert current color to hex format for the native color picker
    const currentHexColor = useMemo(() => {
      // If it's already a hex color, use it directly
      if (isHexColor(bgColor)) {
        return bgColor;
      }

      // If it's a preset name, convert to hex for the native picker
      const hexValue = getHexFromPreset(bgColor);
      return hexValue || getHexFromPreset("amber") || "#FFFFFF";
    }, [bgColor]);

    // Handle preset color selection
    const handlePresetColorClick = (color: string) => {
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
    };

    // Handle native color picker change
    const handleColorChange = (event: ChangeEvent<HTMLInputElement>) => {
      const newColor = event.target.value;
      setNode(data.id, (old) => ({
        ...old,
        data: {
          ...old.data,
          node: {
            ...old.data.node,
            template: {
              ...old.data.node?.template,
              backgroundColor: newColor,
            },
          },
        },
      }));
    };

    return (
      <div className="flex flex-col gap-4 w-full">
        {/* Original preset color buttons */}
        <div className="flex gap-3 flex-wrap justify-center">
          {Object.entries(COLOR_OPTIONS).map(([color, code]) => (
            <Button
              data-testid={`color_picker_button_${color}`}
              unstyled
              key={color}
              onClick={() => handlePresetColorClick(color)}
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

        {/* Native color picker */}
        <div
          className="flex items-center justify-center gap-3 w-full cursor-pointer"
          onClick={() =>
            document.getElementById("native_color_picker")?.click()
          }
        >
          <input
            id="native_color_picker"
            type="color"
            value={currentHexColor}
            onChange={handleColorChange}
            className="h-4 w-4 rounded-full border border-input bg-background flex-shrink-0"
            data-testid="native_color_picker"
            style={{ display: "none" }}
          />
          <div
            className="h-4 w-4 rounded-full border border-input bg-background flex-shrink-0"
            style={{ backgroundColor: currentHexColor }}
          />
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            Custom Color
          </span>
        </div>
      </div>
    );
  },
);

ColorPickerButtons.displayName = "ColorPickerButtons";
