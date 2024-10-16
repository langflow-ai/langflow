import { Case } from "@/shared/components/caseComponent";
import { useDarkStore } from "@/stores/darkStore";
import * as SliderPrimitive from "@radix-ui/react-slider";
import clsx from "clsx";
import { useEffect } from "react";
import { SliderComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";
import { InputProps } from "../parameterRenderComponent/types";
import { getMinOrMaxValue } from "./utils/get-min-max-value";

const THRESHOLDS = [0.25, 0.5, 0.75, 1];
const BACKGROUND_COLORS = ["#4f46e5", "#7c3aed", "#a21caf", "#c026d3"];
const TEXT_COLORS = ["#fff", "#fff", "#fff", "#fff"];
const PERCENTAGES = [0.125, 0.375, 0.625, 0.875];

const DARK_COLOR_BACKGROUND = "#09090b";
const DARK_COLOR_TEXT = "#52525b";
const LIGHT_COLOR_BACKGROUND = "#e4e4e7";
const LIGHT_COLOR_TEXT = "#000";

const DEFAULT_SLIDER_BUTTONS_OPTIONS = [
  { id: 0, label: "Precise" },
  { id: 1, label: "Balanced" },
  { id: 2, label: "Creative" },
  { id: 3, label: "Wild" },
];

const MIN_LABEL = "Precise";
const MAX_LABEL = "Wild";
const MIN_LABEL_ICON = "pencil-ruler";
const MAX_LABEL_ICON = "palette";

type ColorType = "background" | "text";

export default function SliderComponent({
  value,
  disabled,
  rangeSpec,
  editNode = false,
  minLabel = MIN_LABEL,
  maxLabel = MAX_LABEL,
  minLabelIcon = MIN_LABEL_ICON,
  maxLabelIcon = MAX_LABEL_ICON,
  sliderButtons = false,
  sliderButtonsOptions = DEFAULT_SLIDER_BUTTONS_OPTIONS,
  sliderInput = false,
  handleOnNewValue,
}: InputProps<string[] | number[], SliderComponentType>): JSX.Element {
  const min = rangeSpec?.min ?? -2;
  const max = rangeSpec?.max ?? 2;

  sliderButtonsOptions =
    sliderButtons && sliderButtonsOptions && sliderButtonsOptions.length > 0
      ? sliderButtonsOptions
      : DEFAULT_SLIDER_BUTTONS_OPTIONS;

  minLabelIcon = minLabelIcon || MIN_LABEL_ICON;
  maxLabelIcon = maxLabelIcon || MAX_LABEL_ICON;
  minLabel = minLabel || MIN_LABEL;
  maxLabel = maxLabel || MAX_LABEL;

  const valueAsNumber = getMinOrMaxValue(Number(value), min, max);
  const step = rangeSpec?.step ?? 0.1;

  useEffect(() => {
    if (disabled && value !== "") {
      handleOnNewValue({ value: "" }, { skipSnapshot: true });
    }
  }, [disabled]);

  const handleChange = (newValue: number[]) => {
    handleOnNewValue({ value: newValue[0] });
  };

  const handleOptionClick = (option: number) => {
    const selectedPercentage = PERCENTAGES[option];

    if (selectedPercentage !== undefined) {
      const calculatedValue = min + (max - min) * selectedPercentage;
      handleOnNewValue({ value: calculatedValue });
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
        ? DARK_COLOR_BACKGROUND
        : DARK_COLOR_TEXT
      : colorType === "background"
        ? LIGHT_COLOR_BACKGROUND
        : LIGHT_COLOR_TEXT;

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
      <Case condition={!sliderButtons && !sliderInput}>
        <div className="relative bottom-2 flex items-center justify-end">
          <span
            data-testid={`default_slider_display_value${editNode ? "_advanced" : ""}`}
            className="font-mono text-sm"
          >
            {valueAsNumber.toFixed(2)}
          </span>
        </div>
      </Case>
      <Case condition={sliderButtons && !sliderInput}>
        <div className="relative bottom-1 flex items-center pb-2">
          <span
            data-testid={`button_slider_display_value${editNode ? "_advanced" : ""}`}
            className="font-mono text-2xl"
          >
            {valueAsNumber.toFixed(2)}
          </span>
        </div>
      </Case>

      <div className="flex cursor-default items-center justify-center">
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
            data-testid={`slider_track${editNode ? "_advanced" : ""}`}
            className={clsx(
              "relative h-1 w-full grow rounded-full",
              isDark ? "bg-zinc-800" : "bg-zinc-200",
            )}
          >
            <SliderPrimitive.Range className="absolute h-full rounded-full bg-gradient-to-r from-indigo-600 to-pink-500" />
          </SliderPrimitive.Track>
          <SliderPrimitive.Thumb
            data-testid={`slider_thumb${editNode ? "_advanced" : ""}`}
            className={clsx(
              "block h-6 w-6 rounded-full border-2 border-muted bg-pink-500 shadow-lg",
            )}
          />
        </SliderPrimitive.Root>
        {sliderInput && (
          <input
            data-testid={`slider_input_value${editNode ? "_advanced" : ""}`}
            type="number"
            value={valueAsNumber.toFixed(2)}
            onChange={(e) => handleChange([parseFloat(e.target.value)])}
            className={clsx(
              "ml-2 h-10 w-16 rounded-md border px-2 py-1 text-sm arrow-hide",
              isDark
                ? "border-zinc-700 bg-zinc-800 text-white"
                : "border-zinc-300 bg-white text-black",
            )}
            min={min}
            max={max}
            step={step}
            disabled={disabled}
          />
        )}
      </div>

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
                key={option.id}
                onClick={() => handleOptionClick(option.id)}
                style={{
                  background: getButtonBackground(option.id),
                  color: getButtonTextColor(option.id),
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
            className="mr-1 h-4 w-4"
            name={minLabelIcon}
            aria-hidden="true"
          />
          <span data-testid="min_label">{minLabel}</span>
        </div>
        <div className="flex items-center justify-end">
          <span data-testid="max_label">{maxLabel}</span>
          <IconComponent
            className="ml-1 h-4 w-4"
            name={maxLabelIcon}
            aria-hidden="true"
          />
        </div>
      </div>
    </div>
  );
}
