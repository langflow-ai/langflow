import { Button } from "@/components/ui/button";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

type ViewMode = "list" | "grid";

export function ViewToggle({
  value,
  onChange,
}: {
  value: ViewMode;
  onChange: (v: ViewMode) => void;
}) {
  const modes: ViewMode[] = ["list", "grid"];

  return (
    <div className="relative flex h-fit rounded-lg border border-accent">
      {/* Sliding background */}
      <div
        className={cn(
          "absolute h-[30px] w-[30px] rounded-md bg-accent transition-transform duration-300",
          value === "list" ? "translate-x-0" : "translate-x-full"
        )}
      />

      {modes.map((mode) => (
        <Button
          key={mode}
          unstyled
          size="icon"
          className="relative z-10 flex-1 rounded-md p-[7px] text-secondary-font"
          onClick={() => onChange(mode)}
          aria-label={`Switch to ${mode} view`}
        >
          <ForwardedIconComponent
            name={mode === "list" ? "Menu" : "LayoutGrid"}
            className="h-4 w-4"
          />
        </Button>
      ))}
    </div>
  );
}
