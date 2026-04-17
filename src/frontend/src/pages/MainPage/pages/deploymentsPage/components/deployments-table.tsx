import { useCallback, useState } from "react";
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Deployment } from "../types";
import DeploymentTableRow from "./deployment-table-row";

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

  const toggleExpanded = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

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
          <DeploymentTableRow
            key={deployment.id}
            deployment={deployment}
            providerName={providerMap[deployment.provider_id ?? ""] ?? "—"}
            deletingId={deletingId}
            colSpan={COLUMNS.length}
            isExpanded={expandedIds.has(deployment.id)}
            onToggleExpanded={toggleExpanded}
            onTestDeployment={onTestDeployment}
            onViewDetails={onViewDetails}
            onUpdateDeployment={onUpdateDeployment}
            onDeleteDeployment={onDeleteDeployment}
          />
        ))}
      </TableBody>
    </Table>
  );
}
