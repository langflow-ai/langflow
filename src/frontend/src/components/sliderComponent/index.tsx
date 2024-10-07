import { useDarkStore } from "@/stores/darkStore";
import * as SliderPrimitive from "@radix-ui/react-slider";
import clsx from "clsx";
import { useEffect } from "react";
import { FloatComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";

const THRESHOLDS = [0.25, 0.5, 0.75, 1];
const BACKGROUND_COLORS = ["#4f46e5", "#7c3aed", "#a21caf", "#c026d3"];
const TEXT_COLORS = ["#fff", "#fff", "#fff", "#fff"];

type ColorType = "background" | "text";

export default function SliderComponent({
  value,
  onChange,
  disabled,
  rangeSpec,
  editNode = false,
  minLabel = "Precise",
  maxLabel = "Wild",
  minLabelIcon = "pencil-ruler",
  maxLabelIcon = "palette",
  sliderButtons = true,
  sliderButtonsOptions = [
    { value: 0, label: "Precise" },
    { value: 1, label: "Balanced" },
    { value: 2, label: "Creative" },
    { value: 3, label: "Wild" },
  ],
}: FloatComponentType): JSX.Element {
  const step = rangeSpec?.step ?? 0.1;
  const min = rangeSpec?.min ?? 0;
  const max = rangeSpec?.max ?? 2;
  const valueAsNumber = Number(value);

  useEffect(() => {
    if (disabled && value !== "") {
      onChange("", undefined, true);
    }
  }, [disabled]);

  const handleChange = (newValue: number[]) => {
    onChange(newValue[0]);
  };

  const handleOptionClick = (option: number) => {
    const percentages = [0.25, 0.5, 0.75, 1];
    const selectedPercentage = percentages[option];

    if (selectedPercentage !== undefined) {
      const calculatedValue = min + (max - min) * selectedPercentage;
      onChange(calculatedValue);
    }

    return null;
  };

  const isDark = useDarkStore((state) => state.dark);

  const getNormalizedValue = (
    value: number,
    min: number,
    max: number,
  ): number => {
    return (value - min) / (max - min);
  };

  const getColor = (
    optionValue: number,
    normalizedValue: number,
    colorType: ColorType,
  ): string => {
    const colors = colorType === "background" ? BACKGROUND_COLORS : TEXT_COLORS;
    const defaultColor = isDark
      ? colorType === "background"
        ? "#09090b"
        : "#52525b"
      : colorType === "background"
        ? "#e4e4e7"
        : "#000";

    if (normalizedValue <= THRESHOLDS[0] && optionValue === 0) {
      return colors[0];
    }

    for (let i = 1; i < THRESHOLDS.length; i++) {
      if (
        normalizedValue > THRESHOLDS[i - 1] &&
        normalizedValue <= THRESHOLDS[i] &&
        optionValue === i
      ) {
        return colors[i];
      }
    }

    return defaultColor;
  };

  const getButtonBackground = (optionValue: number = 0): string => {
    const normalizedValue = getNormalizedValue(valueAsNumber, min, max);
    return getColor(optionValue, normalizedValue, "background");
  };

  const getButtonTextColor = (optionValue: number = 0): string => {
    const normalizedValue = getNormalizedValue(valueAsNumber, min, max);
    return getColor(optionValue, normalizedValue, "text");
  };

  return (
    <div className="w-full rounded-lg pb-2">
      <div className="relative bottom-2 flex items-center justify-end">
        <span className="font-mono text-sm">{valueAsNumber.toFixed(2)}</span>
      </div>
      <SliderPrimitive.Root
        className="relative flex h-5 w-full touch-none select-none items-center"
        value={[valueAsNumber]}
        onValueChange={handleChange}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
      >
        <SliderPrimitive.Track
          className={clsx(
            "relative h-1 w-full grow rounded-full",
            isDark ? "bg-zinc-800" : "bg-zinc-200",
          )}
        >
          <SliderPrimitive.Range className="absolute h-full rounded-full bg-gradient-to-r from-indigo-600 to-pink-500" />
        </SliderPrimitive.Track>
        <SliderPrimitive.Thumb
          className={clsx(
            "block h-6 w-6 rounded-full border-2 bg-pink-500 shadow-lg",
            isDark ? "border-[#fff]" : "border-zinc-800",
          )}
        />
      </SliderPrimitive.Root>

      {sliderButtons && (
        <div className="my-3">
          <div
            className={clsx(
              "flex rounded-md",
              isDark ? "bg-zinc-950" : "bg-zinc-200",
            )}
          >
            {sliderButtonsOptions?.map((option) => (
              <button
                key={option.value}
                onClick={() => handleOptionClick(option.value)}
                style={{
                  background: getButtonBackground(option.value),
                  color: getButtonTextColor(option.value),
                }}
                className={clsx(
                  "h-9 flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors duration-200",
                )}
                disabled={disabled}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-2 grid grid-cols-2 gap-x-2 text-sm text-gray-500">
        <div className="flex items-center">
          <IconComponent
            className="mr-1 h-3 w-3"
            name={minLabelIcon}
            aria-hidden="true"
          />
          <span>{minLabel}</span>
        </div>
        <div className="flex items-center justify-end">
          <span>{maxLabel}</span>
          <IconComponent
            className="ml-1 h-3 w-3"
            name={maxLabelIcon}
            aria-hidden="true"
          />
        </div>
      </div>
    </div>
  );
}
