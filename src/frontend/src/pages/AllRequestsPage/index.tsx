import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import IconComponent from "@/components/common/genericIconComponent";
import { useGetAllFlowVersions } from "@/controllers/API/queries/flow-versions";
import CustomLoader from "@/customization/components/custom-loader";
import FlowPagination from "@/pages/MarketplacePage/components/FlowPagination";

export default function AllRequestsPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Pagination state
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(12);

  const handleReview = (flowId: string) => {
    navigate(`/flow/${flowId}`);
  };

  // Handle status filter change
  const handleStatusFilterChange = (value: string) => {
    setStatusFilter(value);
    setPageIndex(1); // Reset to first page
  };

  // Pagination handlers
  const handlePageChange = (page: number) => {
    setPageIndex(page);
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    setPageIndex(1); // Reset to first page when changing page size
  };

  // Fetch all flow versions with optional status filter
  const { data, isLoading } = useGetAllFlowVersions(
    pageIndex,
    pageSize,
    statusFilter === "all" ? undefined : statusFilter
  );

  // Extract items and metadata
  const allVersions = data?.items || [];
  const totalCount = data?.total || 0;

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Get status badge styling
  const getStatusBadge = (statusName: string) => {
    switch (statusName) {
      case "Submitted":
        return (
          <span className="inline-flex items-center rounded-full bg-[#FDFDD2] px-2.5 py-0.5 text-xs font-medium text-[#826D29] min-h-6">
            Under Review
          </span>
        );
      case "Approved":
        return (
          <span className="inline-flex items-center rounded-full bg-[#f2fff0] px-2.5 py-0.5 text-xs font-medium text-[#3fa33c] min-h-6">
            Approved
          </span>
        );
      case "Rejected":
        return (
          <span className="inline-flex items-center rounded-full bg-[#fdf4f3] px-2.5 py-0.5 text-xs font-medium text-[#d7503e] min-h-6">
            Rejected
          </span>
        );
      default:
        return statusName;
    }
  };

  const renderTable = () => {
    if (isLoading) {
      return (
        <div className="flex justify-center py-8">
          <CustomLoader />
        </div>
      );
    }

    if (!allVersions || allVersions.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground h-full">
          <IconComponent name="Inbox" className="h-12 w-12 mb-4" />
          <p>No requests found</p>
        </div>
      );
    }

    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Agent Name</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Submitted by</TableHead>
            <TableHead>Submission Date</TableHead>
            <TableHead className="text-center">Versions</TableHead>
            <TableHead className="text-center">Status</TableHead>
            <TableHead>Remark</TableHead>
            <TableHead>Reviewed By</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {allVersions.map((version) => (
            <TableRow key={version.id}>
              <TableCell className="font-medium">{version.title}</TableCell>
              <TableCell className="max-w-xs truncate text-muted-foreground">
                {version.description || (
                  <span className="text-muted-foreground">-</span>
                )}
              </TableCell>
              <TableCell>
                <div>
                  <div>
                    {version.submitted_by_name ||
                      version.submitter_name ||
                      "Unknown"}
                  </div>
                  {(version.submitted_by_email || version.submitter_email) && (
                    <div className="text-xs text-muted-foreground">
                      {version.submitted_by_email || version.submitter_email}
                    </div>
                  )}
                </div>
              </TableCell>
              <TableCell>{formatDate(version.submitted_at)}</TableCell>
              <TableCell className="text-center">{version.version}</TableCell>
              <TableCell className="text-center">
                {getStatusBadge(version.status_name || "")}
              </TableCell>
              <TableCell className="max-w-xs truncate">
                {version.status_name === "Rejected" && version.rejection_reason ? (
                  <span className="text-muted-foreground">
                    {version.rejection_reason}
                  </span>
                ) : (
                  <span>-</span>
                )}
              </TableCell>
              <TableCell>
                {version.status_name === "Approved" || version.status_name === "Rejected" ? (
                  <div>
                    {version.reviewed_by_name || version.reviewer_name || "-"}
                  </div>
                ) : (
                  <span>-</span>
                )}
              </TableCell>
              <TableCell>
                <Button
                  size="sm"
                  variant="link"
                  onClick={() => handleReview(version.original_flow_id)}
                  className="!text-[#7421e3] hover:!text-[#350e84] !p-0 !font-normal"
                >
                  Review
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  };

  return (
    <div className="flex h-full w-full flex-col bg-main-bg p-4 overflow-y-auto">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-[#350E84] dark:text-white text-[21px] font-medium leading-normal">
          All Requests{" "}
          {totalCount > 0 && <span>({totalCount})</span>}
        </h1>

        {/* Status Filter */}
        <Select value={statusFilter} onValueChange={handleStatusFilterChange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="Submitted">Submitted</SelectItem>
            <SelectItem value="Approved">Approved</SelectItem>
            <SelectItem value="Rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-4">
        {/* Table */}
        <div className="max-h-[calc(100vh-280px)] overflow-y-auto">
          {renderTable()}
        </div>

        {/* Bottom pagination */}
        {data && data.total > 0 && (
          <div className="flex items-center justify-between px-1 pb-4">
            <div className="text-sm text-muted-foreground">
              Showing{" "}
              {Math.min((pageIndex - 1) * pageSize + 1, data.total)} -{" "}
              {Math.min(pageIndex * pageSize, data.total)} of {data.total}{" "}
              results
            </div>
            <FlowPagination
              currentPage={pageIndex}
              pageSize={pageSize}
              totalPages={data.pages}
              onPageChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
            />
          </div>
        )}
      </div>
    </div>
  );
}
