import IconComponent from "@/components/common/genericIconComponent";

export const SliderLabels = ({
  minLabel,
  maxLabel,
  minLabelIcon,
  maxLabelIcon,
}: {
  minLabel: string;
  maxLabel: string;
  minLabelIcon: string;
  maxLabelIcon: string;
}) => {
  return (
    <>
      <div className="text mt-2 grid grid-cols-2 gap-x-2 text-sm">
        <div className="flex items-center">
          <IconComponent
            className="text-placeholder-foreground mr-1 h-4 w-4"
            name={minLabelIcon}
            aria-hidden="true"
          />
          <span
            data-testid="min_label"
            className="text-placeholder-foreground text-xs"
          >
            {minLabel}
          </span>
        </div>
        <div className="flex items-center justify-end">
          <span
            data-testid="max_label"
            className="text-placeholder-foreground text-xs"
          >
            {maxLabel}
          </span>
          <IconComponent
            className="text-placeholder-foreground ml-1 h-4 w-4"
            name={maxLabelIcon}
            aria-hidden="true"
          />
        </div>
      </div>
    </>
  );
};
