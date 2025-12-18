import { memo, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { COLOR_OPTIONS } from "@/constants/constants";
import type { NoteDataType } from "@/types/flow";
import { cn } from "@/utils/utils";

interface ColorPickerButtonsProps {
  bgColor: string;
  data: NoteDataType;
  /** Flow store's setNode function for updating node data */
  setNode: (id: string, updater: (node: any) => any) => void;
}

export const ColorPickerButtons = memo(
  ({ bgColor, data, setNode }: ColorPickerButtonsProps) => {
    const colorInputRef = useRef<HTMLInputElement>(null);
    const isCustomColor =
      bgColor && !Object.keys(COLOR_OPTIONS).includes(bgColor);

    /** Updates the node's background color in the flow store */
    const updateBackgroundColor = useCallback(
      (color: string, isCustom: boolean) => {
        setNode(data.id, (node) => ({
          ...node,
          data: {
            ...node.data,
            node: {
              ...node.data.node,
              template: {
                ...node.data.node?.template,
                backgroundColor: color,
                customColor: isCustom ? color : undefined,
              },
            },
          },
        }));
      },
      [data.id, setNode],
    );

    const handleCustomColorChange = (
      e: React.ChangeEvent<HTMLInputElement>,
    ) => {
      updateBackgroundColor(e.target.value, true);
    };

    return (
      <div className="flex flex-row items-center gap-3">
        {/* Preset color options */}
        {Object.entries(COLOR_OPTIONS).map(([colorKey, colorValue]) => (
          <Button
            key={colorKey}
            data-testid={`color_picker_button_${colorKey}`}
            unstyled
            onClick={() => updateBackgroundColor(colorKey, false)}
          >
            <div
              className={cn(
                "h-4 w-4 rounded-full hover:border hover:border-ring",
                bgColor === colorKey && "border-2 border-blue-500",
                colorValue === null && "border",
              )}
              style={{ backgroundColor: colorValue ?? "#00000000" }}
            />
          </Button>
        ))}
        {/* Custom color picker with rainbow gradient indicator */}
        <Button
          data-testid="color_picker_button_custom"
          unstyled
          onClick={() => colorInputRef.current?.click()}
          className="relative"
        >
          <div
            className={cn(
              "relative flex h-4 w-4 items-center justify-center overflow-hidden rounded-full border hover:border-ring",
              isCustomColor && "border-2 border-blue-500",
            )}
          >
            <div
              className="absolute inset-0"
              style={{
                background:
                  "conic-gradient(from 0deg, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000)",
              }}
            />
          </div>
          <input
            ref={colorInputRef}
            type="color"
            className="absolute h-0 w-0 opacity-0"
            onChange={handleCustomColorChange}
            value={isCustomColor ? bgColor : "#ffffff"}
          />
        </Button>
      </div>
    );
  },
);

ColorPickerButtons.displayName = "ColorPickerButtons";
