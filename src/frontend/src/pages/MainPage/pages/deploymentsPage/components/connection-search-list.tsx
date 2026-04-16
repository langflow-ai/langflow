import { memo, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import type { ConnectionItem } from "../types";
import { CheckboxSelectItem } from "./radio-select-item";

interface ConnectionSearchListProps {
  connections: ConnectionItem[];
  selectedConnections: Set<string>;
  onToggleConnection: (id: string) => void;
  onSwitchToCreate: () => void;
}

export const ConnectionSearchList = memo(function ConnectionSearchList({
  connections,
  selectedConnections,
  onToggleConnection,
  onSwitchToCreate,
}: ConnectionSearchListProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredConnections = useMemo(() => {
    const sorted = [...connections].sort((a, b) => {
      if (a.isNew && !b.isNew) return -1;
      if (!a.isNew && b.isNew) return 1;
      return 0;
    });
    if (!searchQuery.trim()) return sorted;
    const q = searchQuery.toLowerCase();
    return sorted.filter(
      (c) => c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q),
    );
  }, [connections, searchQuery]);

  if (connections.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
        <ForwardedIconComponent
          name="PlugZap"
          className="h-8 w-8 text-muted-foreground/50"
        />
        <div>
          <p className="text-sm font-medium text-muted-foreground">
            No connections yet
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground/70">
            Create a connection to attach credentials to this flow.
          </p>
        </div>
        <button
          type="button"
          onClick={onSwitchToCreate}
          className="text-xs font-medium text-primary hover:underline"
        >
          Create your first connection
        </button>
      </div>
    );
  }

  return (
    <div className={cn(filteredConnections.length > 0 && "pr-3")}>
      <div className="min-w-0">
        <Input
          icon="Search"
          placeholder="Search connections..."
          className="bg-muted"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>
      {filteredConnections.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No connections match &ldquo;{searchQuery}&rdquo;
        </p>
      ) : (
        <div className="mt-2 space-y-1.5">
          {filteredConnections.map((conn) => (
            <CheckboxSelectItem
              key={conn.connectionId}
              value={conn.id}
              checked={selectedConnections.has(conn.id)}
              onChange={() => onToggleConnection(conn.id)}
              data-testid={`connection-item-${conn.id}`}
            >
              <div className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium leading-tight">
                  {conn.name}
                </span>
              </div>
            </CheckboxSelectItem>
          ))}
        </div>
      )}
    </div>
  );
});
