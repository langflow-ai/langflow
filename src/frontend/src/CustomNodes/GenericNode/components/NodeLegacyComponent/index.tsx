import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import { useGetReplacementComponents } from "../../hooks/use-get-replacement-components";

export default function NodeLegacyComponent({
  legacy,
  replacement,
  setDismissAll,
}: {
  legacy?: boolean;
  replacement?: string[];
  setDismissAll: (value: boolean) => void;
}) {
  const setFilterComponent = useFlowStore((state) => state.setFilterComponent);
  const setFilterType = useFlowStore((state) => state.setFilterType);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);

  const handleFilterComponent = () => {
    setFilterComponent(replacement);
    setFilterType(undefined);
    setFilterEdge([]);
  };

  const foundComponents = useGetReplacementComponents(replacement);
  return (
    <div
      className={cn(
        "flex w-full items-center gap-3 rounded-t-[0.69rem] border-b bg-muted p-2 px-4 py-2",
      )}
    >
      <div className="h-2.5 w-2.5 rounded-full bg-warning" />
      <div className="mb-px flex-1 truncate text-mmd font-medium">Legacy</div>

      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 !text-mmd"
        onClick={(e) => {
          e.stopPropagation();
          setDismissAll(true);
        }}
        aria-label="Dismiss warning bar"
        data-testid="dismiss-warning-bar"
      >
        Dismiss
      </Button>
    </div>
  );
}
