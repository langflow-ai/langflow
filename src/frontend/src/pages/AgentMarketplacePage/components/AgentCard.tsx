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

import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { PublishedAgentHeader } from "@/controllers/API/queries/published-agent/use-get-publshed-agent";

interface AgentCardProps {
  agent: PublishedAgentHeader;
}

export default function AgentCard({ agent }: AgentCardProps) { 
  const navigate = useCustomNavigate();

  const status = "Published";

  const statusColors = {
    Published: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    Deployed: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  };

  const handleCardClick = () => {
    navigate(`/flow/${agent.flow_id}`); // Use agent.flow_id instead of flow.id
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
            {agent.display_name || `Agent ${agent.id.slice(0, 8)}`} {/* Use agent.display_name */}
          </h3>
          <div className="flex items-center gap-2">
            <Badge className={statusColors[status]}>
              {status}
            </Badge>
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <span>Created {new Date(agent.created_at).toLocaleDateString()}</span> {/* Use agent.created_at */}
            </div>
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
            <DropdownMenuItem onClick={() => navigate(`/flow/${agent.flow_id}`)}>
              View Details
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate(`/flow/${agent.flow_id}`)}>
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
        {agent.description || "No description provided"} {/* Use agent.description */}
      </p>

      {/* Category Tag */}
      {agent.category_id && (
        <div className="flex flex-wrap gap-2 mt-auto">
          <span className="rounded-md bg-gray-100 dark:bg-gray-800 px-2 py-1 text-xs text-gray-700 dark:text-gray-300">
            {agent.category_id}
          </span>
        </div>
      )}
    </div>
  );
}