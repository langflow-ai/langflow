import { useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/utils/utils";
import { LABEL_COLORS } from "./types";

interface LabelColorPickerProps {
  color: string;
  onChange: (color: string) => void;
}

export function LabelColorPicker({ color, onChange }: LabelColorPickerProps) {
  const { t } = useTranslation();
  const colorInputRef = useRef<HTMLInputElement>(null);
  const isPreset = LABEL_COLORS.includes(color);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={t("textAnnotation.editorPickColor")}
          className="h-4 w-4 shrink-0 rounded-full border hover:border-ring"
          style={{ backgroundColor: color }}
        />
      </PopoverTrigger>
      <PopoverContent align="start" side="bottom" className="w-fit p-2">
        <div className="flex flex-row flex-wrap items-center gap-2">
          {LABEL_COLORS.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => onChange(preset)}
              className={cn(
                "h-4 w-4 rounded-full hover:border hover:border-ring",
                color.toLowerCase() === preset.toLowerCase() &&
                  "border-2 border-foreground",
              )}
              style={{ backgroundColor: preset }}
              aria-label={preset}
            />
          ))}
          <button
            type="button"
            onClick={() => colorInputRef.current?.click()}
            className={cn(
              "relative flex h-4 w-4 items-center justify-center overflow-hidden rounded-full border hover:border-ring",
              !isPreset && "border-2 border-foreground",
            )}
            aria-label={t("textAnnotation.editorPickColor")}
          >
            <div
              className="absolute inset-0"
              style={{
                background:
                  "conic-gradient(from 0deg, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000)",
              }}
            />
            <input
              ref={colorInputRef}
              type="color"
              className="absolute h-0 w-0 opacity-0"
              value={isPreset ? "#ffffff" : color}
              onChange={(e) => onChange(e.target.value)}
            />
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
