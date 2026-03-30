import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
}

const TYPE_CONFIG: Record<DeploymentType, { color: string }> = {
  agent: { color: "border-l-error" },
  mcp: { color: "border-l-accent-emerald" },
};

function TypeBadge({ type }: { type: DeploymentType }) {
  const config = TYPE_CONFIG[type] ?? TYPE_CONFIG["agent"];
  return (
    <Badge
      variant="secondaryStatic"
      size="tag"
      className={cn("border-l-2", config.color)}
    >
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
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
