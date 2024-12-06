import { cn } from "@/utils/utils";

export default function ResetColumns({
  resetGrid,
}: {
  resetGrid: () => void;
}): JSX.Element {
  return (
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
