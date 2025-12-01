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
import ShadTooltip from "@/components/common/shadTooltipComponent";
import IconComponent from "@/components/common/genericIconComponent";
import { useGetAllFlowVersions } from "@/controllers/API/queries/flow-versions";
import CustomLoader from "@/customization/components/custom-loader";
import FlowPagination from "@/pages/MarketplacePage/components/FlowPagination";

export default function AllRequestsPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [openTooltipId, setOpenTooltipId] = useState<string | null>(null);

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
          <span className="inline-flex items-center rounded-full bg-process-bg px-2.5 py-0.5 text-xs font-medium text-process min-h-6">
            Under Review
          </span>
        );
      case "Published":
        return (
          <span className="inline-flex items-center rounded-full bg-[#f2fff0] px-2.5 py-0.5 text-xs font-medium text-[#3fa33c] min-h-6">
            Published
          </span>
        );
      case "Rejected":
        return (
          <span className="inline-flex items-center rounded-full bg-error-bg px-2.5 py-0.5 text-xs font-medium text-error min-h-6">
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
        <div className="flex justify-center py-8 h-full">
          <CustomLoader />
        </div>
      );
    }

    if (!allVersions || allVersions.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-secondary-font h-full">
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
            <TableHead className="text-center">Statuss</TableHead>
            <TableHead>Remark</TableHead>
            <TableHead>Reviewed By</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {allVersions.map((version) => (
            <TableRow key={version.id}>
              <TableCell className="font-medium">{version.title}</TableCell>
              <TableCell className="max-w-xs truncate text-secondary-font">
                {version.description || (
                  <span className="text-secondary-font">-</span>
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
                    <div className="text-xs text-secondary-font">
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
              <TableCell>
                {version.status_name === "Rejected" &&
                version.rejection_reason ? (
                  <ShadTooltip
                    content={version.rejection_reason}
                    side="bottom"
                    open={openTooltipId === version.id}
                    setOpen={(isOpen) =>
                      setOpenTooltipId(isOpen ? version.id : null)
                    }
                    delayDuration={0}
                  >
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenTooltipId(
                          openTooltipId === version.id ? null : version.id
                        );
                      }}
                      className="inline-flex items-center gap-1 text-secondary-font cursor-pointer"
                    >
                      {version.rejection_reason
                        .split(" ")
                        .slice(0, 2)
                        .join(" ")}
                      ...
                    </span>
                  </ShadTooltip>
                ) : (
                  <span>-</span>
                )}
              </TableCell>
              <TableCell>
                {version.status_name === "Published" ? (
                  <div>
                    {version.published_by_name || "-"}
                  </div>
                ) : version.status_name === "Rejected" ? (
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
    <div className="flex h-full w-full flex-col bg-background-mainBg p-4 overflow-y-auto">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-menu text-xl font-medium leading-normal">
          All Requests {totalCount > 0 && <span>({totalCount})</span>}
        </h2>

        {/* Status Filter */}
        <Select value={statusFilter} onValueChange={handleStatusFilterChange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="Submitted">Under Review</SelectItem>
            <SelectItem value="Published">Published</SelectItem>
            <SelectItem value="Rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-4 h-full">
        {/* Table */}
        <div className="max-h-[calc(100vh-168px)] h-full overflow-y-auto">
          {renderTable()}
        </div>

        {/* Bottom pagination */}
        {data && data.total > 0 && (
          <div className="flex items-center justify-between mt-auto">
            <div className="text-sm font-medium text-primary-font">
              Showing {Math.min((pageIndex - 1) * pageSize + 1, data.total)} -{" "}
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
