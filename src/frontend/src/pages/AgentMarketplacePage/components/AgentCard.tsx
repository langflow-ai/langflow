import { MoreVertical, GitBranch } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { FlowType } from "@/types/flow";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

interface AgentCardProps {
  flow: FlowType;
}

export default function AgentCard({ flow }: AgentCardProps) {
  const navigate = useCustomNavigate();

  // Determine status based on flow properties
  const status = flow.endpoint_name ? "Deployed" : "Published";

  const statusColors = {
    Published: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    Deployed: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  };

  const handleCardClick = () => {
    navigate(`/flow/${flow.id}`);
  };

  return (
    <div
      className="group relative flex flex-col rounded-lg border border-border bg-white dark:bg-card p-4 shadow-sm transition-shadow hover:shadow-md cursor-pointer"
      onClick={handleCardClick}
    >
      {/* Header */}
      <div className="mb-3 flex items-start justify-between">
        <div className="flex-1">
          <h3 className="text-base font-semibold text-foreground mb-1">
            {flow.name}
          </h3>
          <div className="flex items-center gap-2">
            <Badge className={statusColors[status]}>
              {status}
            </Badge>
            {flow.updated_at && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <span>Updated {new Date(flow.updated_at).toLocaleDateString()}</span>
              </div>
            )}
          </div>
        </div>

        {/* Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 opacity-0 transition-opacity group-hover:opacity-100"
              onClick={(e) => e.stopPropagation()}
            >
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
            <DropdownMenuItem onClick={() => navigate(`/flow/${flow.id}`)}>
              View Details
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate(`/flow/${flow.id}`)}>
              Edit
            </DropdownMenuItem>
            <DropdownMenuItem>Duplicate</DropdownMenuItem>
            <DropdownMenuItem className="text-destructive">
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Description */}
      <p className="mb-4 text-sm text-muted-foreground line-clamp-2">
        {flow.description || "No description provided"}
      </p>

      {/* Tags */}
      {flow.tags && flow.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-auto">
          {flow.tags.slice(0, 3).map((tag, index) => (
            <span
              key={index}
              className="rounded-md bg-gray-100 dark:bg-gray-800 px-2 py-1 text-xs text-gray-700 dark:text-gray-300"
            >
              {tag}
            </span>
          ))}
          {flow.tags.length > 3 && (
            <span className="rounded-md bg-gray-100 dark:bg-gray-800 px-2 py-1 text-xs text-gray-700 dark:text-gray-300">
              +{flow.tags.length - 3}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
