import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { getTracesBySessionGrouped } from "@/controllers/API/queries/observability";
import TraceDetailsModal from "./TraceDetailsModal";

interface GroupItem {
  session_id: string;
  count: number;
  trace_ids: string[];
}

interface ThreadLogsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  nameParam?: string; // optional for future dynamic agent name
  timeframe?: string; // default 24h
}

export default function ThreadLogsDrawer({
  isOpen,
  onClose,
  // Use provided agent name; no hardcoded default
  nameParam,
  timeframe = "24h",
}: ThreadLogsDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  // Trace details modal state
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    // Require an agent name to fetch grouped traces
    if (!nameParam || !nameParam.trim()) {
      setGroups([]);
      return;
    }
    const fetchGroups = async () => {
      setLoading(true);
      setError(null);
      try {
        const json = await getTracesBySessionGrouped({
          name: nameParam,
          timeframe,
        });
        const items: GroupItem[] = Array.isArray(json?.groups)
          ? json.groups
          : [];
        setGroups(items);
      } catch (e: any) {
        setError(e?.message || "Failed to load thread logs");
      } finally {
        setLoading(false);
      }
    };
    fetchGroups();
  }, [isOpen, nameParam, timeframe]);

  if (!isOpen) return null;

  const toggle = (sessionId: string) => {
    setExpanded((prev) => ({ ...prev, [sessionId]: !prev[sessionId] }));
  };

  return (
    <div
      className={`
          fixed right-4 top-[148px] bottom-[16px]
          w-[300px]
          bg-background border rounded-md
          flex flex-col
          transition-all duration-300 ease-out
          ${isOpen ? "translate-x-0 opacity-100" : "translate-x-full opacity-0"}
        `}
    >
      <div className="flex items-center justify-between pt-4 px-4">
        <h3 className="font-medium text-primary text-sm">Thread Logs</h3>
        <Button variant="ghost" size="iconSm" onClick={onClose} title="Close">
          <ForwardedIconComponent name="X" className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto pt-3">
        {loading && (
          <div className="px-4 py-3 text-sm text-muted-foreground">
            Loading…
          </div>
        )}
        {error && (
          <div className="px-4 py-3 text-sm text-destructive">{error}</div>
        )}

        {!loading && !error && (
          <div className="mt-2 space-y-2 px-2">
            {groups.length === 0 ? (
              <div className="px-2 py-3 text-sm text-muted-foreground">
                No sessions found.
              </div>
            ) : (
              groups.map((g) => (
                <div key={g.session_id} className="border rounded-md">
                  <button
                    className="w-full text-left px-3 py-2 flex items-center justify-between hover:bg-muted/40"
                    onClick={() => toggle(g.session_id)}
                  >
                    <div className="min-w-0">
                      <div
                        className="text-sm font-medium truncate"
                        title={g.session_id}
                      >
                        {g.session_id}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {g.count} traces
                      </div>
                    </div>
                    <ForwardedIconComponent
                      name={
                        expanded[g.session_id] ? "ChevronUp" : "ChevronDown"
                      }
                      className="h-4 w-4"
                    />
                  </button>
                  {expanded[g.session_id] && (
                    <div className="px-3 pb-3">
                      <ul className="space-y-1">
                        {g.trace_ids.map((tid) => (
                          <li key={tid} className="text-xs font-mono break-all">
                            <button
                              className="underline hover:text-primary"
                              title="View trace details"
                              onClick={() => setSelectedTraceId(tid)}
                            >
                              {tid}
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
        {/* Trace Details Modal */}
        <TraceDetailsModal
          open={!!selectedTraceId}
          onOpenChange={(open) => {
            if (!open) setSelectedTraceId(null);
          }}
          traceId={selectedTraceId}
        />
      </div>
    </div>
  );
}
