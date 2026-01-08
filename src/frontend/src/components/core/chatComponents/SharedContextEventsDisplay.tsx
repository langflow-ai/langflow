import { AnimatePresence, motion } from "framer-motion";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { SharedContextEventData } from "@/types/chat";
import { cn } from "@/utils/utils";

interface SharedContextEventsDisplayProps {
  events: SharedContextEventData[];
}

const OPERATION_CONFIG: Record<
  SharedContextEventData["operation"],
  { color: string; bgColor: string; icon: string; label: string }
> = {
  get: {
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-500/20",
    icon: "Eye",
    label: "GET",
  },
  set: {
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-500/20",
    icon: "Pencil",
    label: "SET",
  },
  append: {
    color: "text-yellow-600 dark:text-yellow-400",
    bgColor: "bg-yellow-500/20",
    icon: "Plus",
    label: "APPEND",
  },
  delete: {
    color: "text-red-600 dark:text-red-400",
    bgColor: "bg-red-500/20",
    icon: "Trash2",
    label: "DELETE",
  },
  keys: {
    color: "text-gray-600 dark:text-gray-400",
    bgColor: "bg-gray-500/20",
    icon: "List",
    label: "KEYS",
  },
  has_key: {
    color: "text-gray-600 dark:text-gray-400",
    bgColor: "bg-gray-500/20",
    icon: "Search",
    label: "CHECK",
  },
};

function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function SharedContextEventsDisplay({
  events,
}: SharedContextEventsDisplayProps) {
  if (!events?.length) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No shared context activity yet.
      </div>
    );
  }

  // Group by namespace
  const groupedByNamespace = events.reduce(
    (acc, event) => {
      const ns = event.namespace || "default";
      if (!acc[ns]) acc[ns] = [];
      acc[ns].push(event);
      return acc;
    },
    {} as Record<string, SharedContextEventData[]>,
  );

  return (
    <div className="flex flex-col gap-2 p-4">
      {Object.entries(groupedByNamespace).map(([namespace, nsEvents]) => (
        <div key={namespace} className="flex flex-col gap-1">
          {namespace !== "default" && (
            <div className="mb-1 text-xs font-medium text-muted-foreground">
              Namespace: {namespace}
            </div>
          )}

          {/* Timeline */}
          <div className="relative border-l-2 border-border pl-4">
            <AnimatePresence>
              {nsEvents.map((event, index) => {
                const config = OPERATION_CONFIG[event.operation];
                return (
                  <motion.div
                    key={`${event.timestamp}-${index}`}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    transition={{ duration: 0.2, delay: index * 0.05 }}
                    className="relative flex items-center gap-3 py-1.5"
                  >
                    {/* Timeline dot */}
                    <div
                      className={cn(
                        "absolute -left-[21px] h-2.5 w-2.5 rounded-full border-2 border-background",
                        config.bgColor,
                      )}
                    />

                    {/* Operation badge */}
                    <Badge
                      variant="outline"
                      size="xq"
                      className={cn(
                        "min-w-[70px] justify-center",
                        config.bgColor,
                        config.color,
                      )}
                    >
                      <ForwardedIconComponent
                        name={config.icon}
                        className="mr-1 h-3 w-3"
                      />
                      {config.label}
                    </Badge>

                    {/* Key name */}
                    <span className="font-mono text-sm text-foreground">
                      {event.key || "(all keys)"}
                    </span>

                    {/* Timestamp */}
                    <span className="ml-auto text-xs text-muted-foreground">
                      {formatTime(event.timestamp)}
                    </span>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        </div>
      ))}

      {/* Summary */}
      <div className="mt-2 border-t border-border pt-2 text-xs text-muted-foreground">
        {events.length} operation{events.length !== 1 ? "s" : ""} total
      </div>
    </div>
  );
}
