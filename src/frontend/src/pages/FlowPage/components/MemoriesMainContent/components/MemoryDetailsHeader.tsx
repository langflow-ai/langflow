import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import type { MemoryDetailsHeaderProps } from "../types";

export function MemoryDetailsHeader({
  memory,
  sessions,
  selectedSession,
  setSelectedSession,
  deleteMutation,
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
      </div>

      <div className="flex items-center gap-2">
        {sessions && sessions.length > 1 && (
          <select
            aria-label="Session filter"
            className="h-9 rounded-md border border-border bg-background px-2 text-sm"
            value={selectedSession ?? sessions[0] ?? ""}
            onChange={(e) => setSelectedSession(e.target.value)}
          >
            {sessions.map((sid) => (
              <option key={sid} value={sid}>
                {sid.length > 20 ? `${sid.slice(0, 20)}...` : sid}
              </option>
            ))}
          </select>
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={() => handleToggleActive(!memory.is_active)}
          aria-pressed={memory.is_active}
          aria-label="Toggle auto-capture"
        >
          Auto-capture: {memory.is_active ? "Enabled" : "Disabled"}
        </Button>

        <DeleteConfirmationModal
          description={`memory "${memory.name}"`}
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
