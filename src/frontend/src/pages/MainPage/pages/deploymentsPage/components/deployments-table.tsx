import { Fragment, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Loading from "@/components/ui/loading";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/utils/utils";
import { type Deployment, type DeploymentType } from "../types";
import DeploymentExpandedRow from "./deployment-expanded-row";

interface DeploymentsTableProps {
  deployments: Deployment[];
  providerMap: Record<string, string>;
  deletingId?: string | null;
  onTestDeployment: (deployment: Deployment) => void;
  onViewDetails?: (deployment: Deployment) => void;
  onUpdateDeployment?: (deployment: Deployment) => void;
  onDeleteDeployment?: (deployment: Deployment) => void;
}

const COLUMNS = [
  "Name",
  "Type",
  "Attached",
  "Provider",
  "Last Modified",
  "Test",
  "Actions",
] as const;

const TYPE_CONFIG: Record<DeploymentType, { icon: string; className: string }> =
  {
    agent: { icon: "Bot", className: "text-accent-pink-foreground" },
    mcp: { icon: "Plug", className: "text-accent-emerald" },
  };

function TypeBadge({ type }: { type: DeploymentType }) {
  const config = TYPE_CONFIG[type] ?? TYPE_CONFIG["agent"];
  return (
    <Badge variant="secondaryStatic" size="tag" className="gap-1">
      <ForwardedIconComponent
        name={config.icon}
        className={cn("h-3 w-3", config.className)}
      />
      {type === "agent" ? "Agent" : "MCP"}
    </Badge>
  );
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function DeploymentsTable({
  deployments,
  providerMap,
  deletingId,
  onTestDeployment,
  onViewDetails,
  onUpdateDeployment,
  onDeleteDeployment,
}: DeploymentsTableProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Attached</TableHead>
          <TableHead>Provider</TableHead>
          <TableHead>Last Modified</TableHead>
          <TableHead>Test</TableHead>
          <TableHead className="w-10" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {deployments.map((deployment) => {
          const isDeleting = deletingId === deployment.id;
          const isExpanded = expandedIds.has(deployment.id);
          const hasAttachments = deployment.attached_count > 0;
          return (
            <Fragment key={deployment.id}>
              <TableRow
                data-testid={`deployment-row-${deployment.id}`}
                className={cn(
                  isDeleting && "pointer-events-none opacity-50",
                  isExpanded && "border-b-0",
                )}
              >
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-medium">{deployment.name}</span>
                    {deployment.description && (
                      <span className="text-xs text-muted-foreground">
                        {deployment.description}
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <TypeBadge type={deployment.type} />
                </TableCell>
                <TableCell>
                  <button
                    type="button"
                    disabled={!hasAttachments}
                    aria-expanded={hasAttachments ? isExpanded : undefined}
                    className={cn(
                      "flex items-center gap-1.5 text-sm",
                      hasAttachments
                        ? "cursor-pointer text-foreground hover:text-primary"
                        : "cursor-default text-muted-foreground",
                    )}
                    onClick={() => toggleExpanded(deployment.id)}
                    data-testid={`toggle-attachments-${deployment.id}`}
                  >
                    {hasAttachments && (
                      <ForwardedIconComponent
                        name={isExpanded ? "ChevronDown" : "ChevronRight"}
                        className="h-3.5 w-3.5"
                      />
                    )}
                    {deployment.attached_count}{" "}
                    {deployment.attached_count === 1 ? "flow" : "flows"}
                  </button>
                </TableCell>
                <TableCell>
                  <span className="text-sm">
                    {providerMap[deployment.provider_id ?? ""] ?? "—"}
                  </span>
                </TableCell>
                <TableCell>
                  <span className="text-sm">
                    {formatDate(deployment.updated_at)}
                  </span>
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    data-testid={`test-deployment-${deployment.id}`}
                    aria-label={`Test ${deployment.name}`}
                    onClick={() => onTestDeployment(deployment)}
                  >
                    <ForwardedIconComponent name="Play" className="h-4 w-4" />
                  </Button>
                </TableCell>
                <TableCell>
                  {isDeleting ? (
                    <div className="flex h-8 w-8 items-center justify-center">
                      <Loading size={16} className="text-muted-foreground" />
                    </div>
                  ) : (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          data-testid={`actions-deployment-${deployment.id}`}
                          aria-label={`Actions for ${deployment.name}`}
                        >
                          <ForwardedIconComponent
                            name="EllipsisVertical"
                            className="h-4 w-4"
                          />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => onViewDetails?.(deployment)}
                        >
                          <ForwardedIconComponent
                            name="Info"
                            className="mr-2 h-4 w-4"
                          />
                          Details
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => onUpdateDeployment?.(deployment)}
                        >
                          <ForwardedIconComponent
                            name="Pencil"
                            className="mr-2 h-4 w-4"
                          />
                          Update
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive"
                          data-testid={`delete-deployment-${deployment.id}`}
                          onClick={() => onDeleteDeployment?.(deployment)}
                        >
                          <ForwardedIconComponent
                            name="Trash2"
                            className="mr-2 h-4 w-4"
                          />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </TableCell>
              </TableRow>
              {isExpanded && (
                <DeploymentExpandedRow
                  deploymentId={deployment.id}
                  colSpan={COLUMNS.length}
                />
              )}
            </Fragment>
          );
        })}
      </TableBody>
    </Table>
  );
}
