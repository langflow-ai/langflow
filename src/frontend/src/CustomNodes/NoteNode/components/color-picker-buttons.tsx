import { type ChangeEvent, memo, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { COLOR_OPTIONS } from "@/constants/constants";
import type { NoteDataType } from "@/types/flow";
import { cn } from "@/utils/utils";

// Helper function to check if a value is a hex color
const isHexColor = (value: string): boolean => {
  return /^#[0-9A-Fa-f]{6}$/.test(value);
};

// Helper function to convert preset color names to hex values for the native picker
const getHexFromPreset = (presetName: string): string | null => {
  const colorValue = COLOR_OPTIONS[presetName as keyof typeof COLOR_OPTIONS];
  if (!colorValue) return null;

  // For CSS variables, create a temporary element to get computed color
  if (colorValue.startsWith("hsl(var(--note-")) {
    if (typeof window === "undefined") return "#FFFFFF";

    // Create a temporary element to get the computed color
    const tempEl = document.createElement("div");
    tempEl.style.color = colorValue;
    document.body.appendChild(tempEl);
    const computedColor = getComputedStyle(tempEl).color;
    document.body.removeChild(tempEl);

    // Convert RGB to hex
    const rgb = computedColor.match(/\d+/g);
    if (rgb && rgb.length >= 3) {
      const r = parseInt(rgb[0]).toString(16).padStart(2, "0");
      const g = parseInt(rgb[1]).toString(16).padStart(2, "0");
      const b = parseInt(rgb[2]).toString(16).padStart(2, "0");
      return `#${r}${g}${b}`;
    }
    return "#FFFFFF";
  }

  return colorValue;
};

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
        <div className="flex items-center justify-center gap-3 w-full">
          <input
            type="color"
            value={currentHexColor}
            onChange={handleColorChange}
            className="h-8 w-16 cursor-pointer rounded border border-input bg-background flex-shrink-0"
            data-testid="native_color_picker"
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
