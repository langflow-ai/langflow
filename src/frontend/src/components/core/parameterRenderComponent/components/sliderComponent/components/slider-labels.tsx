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
      <div className="mt-1 flex items-center justify-between text-[11px] leading-none text-placeholder-foreground">
        <div className="flex items-center gap-1">
          <IconComponent
            className="h-3 w-3"
            name={minLabelIcon}
            aria-hidden="true"
          />
          <span data-testid="min_label">{minLabel}</span>
        </div>
        <div className="flex items-center gap-1">
          <span data-testid="max_label">{maxLabel}</span>
          <IconComponent
            className="h-3 w-3"
            name={maxLabelIcon}
            aria-hidden="true"
          />
        </div>
      </div>
    </>
  );
};
