import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import type { DatasetInfo } from "@/controllers/API/queries/datasets/use-get-datasets";

interface DatasetSelectionOverlayProps {
  selectedDatasets: DatasetInfo[];
  quantitySelected: number;
  onClearSelection: () => void;
  onDeleteSelected: () => void;
}

const DatasetSelectionOverlay = ({
  selectedDatasets,
  quantitySelected,
  onClearSelection,
  onDeleteSelected,
}: DatasetSelectionOverlayProps) => {
  if (quantitySelected === 0) return null;

  return (
    <div
      className={`absolute bottom-0 left-0 right-0 flex h-14 items-center justify-between gap-6 rounded-md border bg-background px-4 shadow-md transition-all duration-300 ${
        quantitySelected > 0
          ? "translate-y-0 opacity-100"
          : "translate-y-4 opacity-0"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold">
          {quantitySelected} selected
        </span>
        <Button variant="ghost" size="icon" onClick={onClearSelection}>
          <ForwardedIconComponent name="X" className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="destructive"
          size="sm"
          onClick={onDeleteSelected}
          className="flex items-center gap-2"
        >
          <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
          Delete
        </Button>
      </div>
    </div>
  );
};

export default DatasetSelectionOverlay;
