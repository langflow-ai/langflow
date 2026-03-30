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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/utils/utils";
import type { Deployment, DeploymentType } from "../types";

interface DeploymentsTableProps {
  deployments: Deployment[];
  providerName: string;
  onTestDeployment: (deployment: Deployment) => void;
  onDuplicateDeployment?: (deployment: Deployment) => void;
  onUpdateDeployment?: (deployment: Deployment) => void;
  onDeleteDeployment?: (deployment: Deployment) => void;
}

const TYPE_CONFIG: Record<DeploymentType, { icon: string; className: string }> =
  {
    agent: { icon: "Bot", className: "text-error" },
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
  providerName,
  onTestDeployment,
  onDuplicateDeployment,
  onUpdateDeployment,
  onDeleteDeployment,
}: DeploymentsTableProps) {
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
        {deployments.map((deployment) => (
          <TableRow
            key={deployment.id}
            data-testid={`deployment-row-${deployment.id}`}
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
              <span className="text-sm">
                {deployment.attached_count}{" "}
                {deployment.attached_count === 1 ? "item" : "items"}
              </span>
            </TableCell>
            <TableCell>
              <span className="text-sm">{providerName}</span>
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
                    onClick={() => onDuplicateDeployment?.(deployment)}
                  >
                    <ForwardedIconComponent
                      name="Copy"
                      className="mr-2 h-4 w-4"
                    />
                    Duplicate
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
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
