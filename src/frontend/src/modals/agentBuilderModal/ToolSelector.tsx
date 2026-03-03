import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import type { ToolSelectorProps } from "./agent-builder-modal-types";

export function ToolSelector({
  tools,
  selectedTools,
  onToggleTool,
  searchQuery,
  onSearchChange,
}: ToolSelectorProps) {
  const suggestedTools = tools.filter((t) => t.is_suggested);
  const filteredTools = searchQuery
    ? tools.filter(
        (t) =>
          t.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          t.category.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : suggestedTools;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1.5">
        {selectedTools.map((className) => {
          const tool = tools.find((t) => t.class_name === className);
          return (
            <button
              key={className}
              type="button"
              onClick={() => onToggleTool(className)}
              className="flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary"
            >
              {tool?.display_name || className}
              <ForwardedIconComponent name="X" className="h-3 w-3" />
            </button>
          );
        })}
      </div>

      <Input
        placeholder="Search components..."
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        data-testid="tool-search-input"
      />

      <div className="max-h-48 overflow-y-auto">
        {filteredTools.length === 0 && (
          <p className="py-3 text-center text-xs text-muted-foreground">
            No components found
          </p>
        )}
        {filteredTools.map((tool) => {
          const isSelected = selectedTools.includes(tool.class_name);
          return (
            <button
              key={tool.class_name}
              type="button"
              onClick={() => onToggleTool(tool.class_name)}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent",
                isSelected && "bg-accent",
              )}
            >
              <ForwardedIconComponent
                name={tool.icon || "Wrench"}
                className="h-4 w-4 shrink-0"
              />
              <div className="flex-1 truncate">
                <span className="font-medium">{tool.display_name}</span>
                <span className="ml-2 text-xs text-muted-foreground">
                  {tool.category}
                </span>
              </div>
              {isSelected && (
                <ForwardedIconComponent
                  name="Check"
                  className="h-4 w-4 shrink-0 text-primary"
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
