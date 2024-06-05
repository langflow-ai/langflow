import { cn } from "../../../../utils/utils";
import ShadTooltip from "../../../shadTooltipComponent";
import { Toggle } from "../../../ui/toggle";

export default function ResetColumns({
  resetGrid,
}: {
  resetGrid: () => void;
}): JSX.Element {
  return (
    /*<div className="absolute left-2 bottom-1 cursor-pointer">
          <div
            className="flex h-10 items-center justify-center px-2 pl-3 rounded-md border border-ring/60 text-sm text-[#bccadc] ring-offset-background placeholder:text-muted-foreground hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => setShow(!show)}
          >
            <ForwardedIconComponent name="Settings"></ForwardedIconComponent>
            <ForwardedIconComponent name={show ? "ChevronLeft" : "ChevronRight"} className="transition-all"></ForwardedIconComponent>
          </div>
        </div>*/
    <div className={cn("absolute bottom-4 left-6")}>
      <span
        className="cursor-pointer underline"
        onClick={() => {
          resetGrid();
        }}
      >
        Reset Columns
      </span>
    </div>
  );
}
