import { getMinOrMaxValue } from "@/components/core/parameterRenderComponent/components/sliderComponent/helpers/get-min-max-value";
import { InputProps } from "@/components/core/parameterRenderComponent/types";
import { Case } from "@/shared/components/caseComponent";
import { useDarkStore } from "@/stores/darkStore";
import { SliderComponentType } from "@/types/components";
import * as SliderPrimitive from "@radix-ui/react-slider";
import clsx from "clsx";
import { useEffect, useState } from "react";
import { SliderLabels } from "./components/slider-labels";
import { buildColorByName } from "./helpers/build-color-by-name";

const THRESHOLDS = [0.25, 0.5, 0.75, 1];
const BACKGROUND_COLORS = ["#4f46e5", "#7c3aed", "#a21caf", "#c026d3"];
const TEXT_COLORS = ["#fff", "#fff", "#fff", "#fff"];
const PERCENTAGES = [0.125, 0.375, 0.625, 0.875];

const DARK_COLOR_BACKGROUND = "#27272a";
const DARK_COLOR_TEXT = "#52525b";
const LIGHT_COLOR_BACKGROUND = "#e4e4e7";
const LIGHT_COLOR_TEXT = "#52525b";

const DEFAULT_SLIDER_BUTTONS_OPTIONS = [
  { id: 0, label: "Precise" },
  { id: 1, label: "Balanced" },
  { id: 2, label: "Creative" },
  { id: 3, label: "Wild" },
];

const MIN_LABEL = "Precise";
const MAX_LABEL = "Creative";
const MIN_LABEL_ICON = "pencil-ruler";
const MAX_LABEL_ICON = "palette";

const DEFAULT_ACCENT_PINK_FOREGROUND_COLOR = "333 71% 51%";
const DEFAULT_ACCENT_INDIGO_FOREGROUND_COLOR = "243 75% 59%";

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
  const step = rangeSpec?.step ?? 0.01;

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

  const [isGrabbing, setIsGrabbing] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [inputValue, setInputValue] = useState(valueAsNumber.toFixed(2));

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  const handleInputBlur = () => {
    const newValue = parseFloat(inputValue);
    if (!isNaN(newValue)) {
      const clampedValue = Math.min(Math.max(newValue, min), max);
      handleOnNewValue({ value: clampedValue });
    }
    setIsEditing(false);
    setInputValue(valueAsNumber.toFixed(2));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleInputBlur();
    } else if (e.key === "Escape") {
      setIsEditing(false);
      setInputValue(valueAsNumber.toFixed(2));
    }
  };

  const percentage = ((valueAsNumber - min) / (max - min)) * 100;

  if (isDark) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }

  const accentIndigoForeground = getComputedStyle(
    document.documentElement,
  ).getPropertyValue("--accent-indigo-foreground");

  const accentPinkForeground = getComputedStyle(
    document.documentElement,
  ).getPropertyValue("--accent-pink-foreground");

  const getThumbColor = (percentage) => {
    if (accentIndigoForeground && accentPinkForeground) {
      return buildColorByName(
        accentIndigoForeground,
        accentPinkForeground,
        percentage,
      );
    }
    return buildColorByName(
      DEFAULT_ACCENT_INDIGO_FOREGROUND_COLOR,
      DEFAULT_ACCENT_PINK_FOREGROUND_COLOR,
      percentage,
    );
  };

  const ringClassInputClass = "ring-[1px] ring-slider-input-border";

  return (
    <div className="w-full rounded-lg pb-2">
      <Case condition={!sliderButtons}>
        <div className="noflow nowheel nopan nodelete nodrag flex items-center justify-end">
          <div
            className={clsx(
              "input-slider-text",
              (isGrabbing || isEditing) && ringClassInputClass,
            )}
          >
            {isEditing ? (
              <input
                type="number"
                value={inputValue}
                onChange={handleInputChange}
                onBlur={handleInputBlur}
                onKeyDown={handleKeyDown}
                className="relative bottom-[1px] w-full cursor-text rounded-sm bg-transparent text-center font-mono text-[0.88rem] arrow-hide"
                autoFocus
              />
            ) : (
              <span
                onClick={() => {
                  setIsEditing(true);
                  setInputValue(valueAsNumber.toFixed(2));
                }}
                data-testid={`default_slider_display_value${editNode ? "_advanced" : ""}`}
                className="relative bottom-[1px] font-mono text-sm hover:cursor-text"
              >
                {valueAsNumber.toFixed(2)}
              </span>
            )}
          </div>
        </div>
      </Case>
      <Case condition={sliderButtons}>
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
              isDark ? "bg-muted" : "bg-border",
            )}
          >
            <SliderPrimitive.Range
              className="absolute h-full rounded-full bg-gradient-to-r from-accent-indigo-foreground to-accent-pink-foreground"
              style={{
                width: `${percentage}%`,
                background: `linear-gradient(to right, rgb(79, 70, 229) 0%, ${getThumbColor(percentage)} ${percentage}%)`,
              }}
            />
          </SliderPrimitive.Track>
          <SliderPrimitive.Thumb
            data-testid={`slider_thumb${editNode ? "_advanced" : ""}`}
            className={clsx(
              "block h-6 w-6 rounded-full border-2 border-background shadow-lg",
              isGrabbing ? "cursor-grabbing" : "cursor-grab",
              valueAsNumber === max && "relative left-1",
            )}
            onPointerDown={() => setIsGrabbing(true)}
            onPointerUp={() => setIsGrabbing(false)}
            style={{
              backgroundColor: getThumbColor(percentage),
            }}
          />
        </SliderPrimitive.Root>
      </div>

      {sliderButtons && (
        <div className="my-3">
          <div className={clsx("flex rounded-md bg-background")}>
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

      <SliderLabels
        minLabel={minLabel}
        maxLabel={maxLabel}
        minLabelIcon={minLabelIcon}
        maxLabelIcon={maxLabelIcon}
      />
    </div>
  );
}
