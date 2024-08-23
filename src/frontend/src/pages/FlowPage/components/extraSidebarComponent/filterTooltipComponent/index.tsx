export function FilterTooltipComponent({
  isInput,
  color,
  type,
}: {
  isInput: boolean;
  color: string;
  type: string;
}): JSX.Element {
  return (
    <div className="flex flex-col gap-2 py-1">
      <div className="flex items-center gap-2">
        <span>
          Filtering components by {isInput ? "input" : "output"} type:
        </span>
        <div
          className="rounded-md px-2 pb-1 pt-0.5 text-xs text-background"
          style={{ backgroundColor: color }}
        >
          {type}
        </div>
      </div>
      <div className="text-xs text-muted-foreground">
        Click to reset filters
      </div>
    </div>
  );
}
