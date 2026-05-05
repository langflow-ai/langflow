import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import { cn } from "@/utils/utils";
import { statusBgColors, statusColors } from "../helpers";
import type { MemoryDetailsHeaderProps } from "../types";

export function MemoryDetailsHeader({
  memory,
  deleteMutation,
  updateMemoryMutation,
  handleToggleActive,
}: MemoryDetailsHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-border bg-background px-6 py-3">
      <div className="flex items-center gap-3">
        <IconComponent name="Brain" className="h-5 w-5 text-muted-foreground" />
        <div>
          <h2 className="text-sm font-semibold">{memory.name}</h2>
          {memory.description && (
            <p className="text-xs text-muted-foreground">
              {memory.description}
            </p>
          )}
        </div>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-xs font-medium",
            statusBgColors[memory.status] || "bg-muted",
            statusColors[memory.status] || "text-muted-foreground",
          )}
        >
          {memory.status}
        </span>
        <div className="ml-2 flex items-center gap-2">
          <Switch
            checked={memory.is_active}
            onCheckedChange={handleToggleActive}
            disabled={updateMemoryMutation.isPending}
            aria-label={`memory capture enabled for ${memory.name}`}
          />
          <span
            className={cn(
              "text-xs font-medium",
              memory.is_active ? "text-primary" : "text-muted-foreground",
            )}
          >
            {memory.is_active ? "Enabled" : "Disabled"}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <DeleteConfirmationModal
          description={`memory \"${memory.name}\"`}
          onConfirm={(e) => {
            e.stopPropagation();
            deleteMutation.mutate({ memoryId: memory.id });
          }}
          asChild
        >
          <Button
            variant="outline"
            size="sm"
            disabled={deleteMutation.isPending}
          >
            <IconComponent name="Trash2" className="mr-1.5 h-3.5 w-3.5" />
            Delete
          </Button>
        </DeleteConfirmationModal>
      </div>
    </div>
  );
}
