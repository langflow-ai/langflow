import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import IconComponent from "@/components/common/genericIconComponent";
import {
  useGetPendingReviews,
  useGetVersionsByStatus,
  useApproveVersion,
  useRejectVersion,
  type FlowVersionRead,
} from "@/controllers/API/queries/flow-versions";
import useAlertStore from "@/stores/alertStore";
import CustomLoader from "@/customization/components/custom-loader";
import FlowPagination from "@/pages/MarketplacePage/components/FlowPagination";

export default function AllRequestsPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("submitted");
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [selectedVersion, setSelectedVersion] =
    useState<FlowVersionRead | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");

  // Pagination state
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(12);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const handleReview = (flowId: string) => {
    navigate(`/flow/${flowId}`);
  };

  // Reset to page 1 when switching tabs
  const handleTabChange = (value: string) => {
    setActiveTab(value);
    setPageIndex(1);
  };

  // Pagination handlers
  const handlePageChange = (page: number) => {
    setPageIndex(page);
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    setPageIndex(1); // Reset to first page when changing page size
  };

  // Fetch data for each tab with pagination
  const { data: pendingReviewsData, isLoading: loadingPending } =
    useGetPendingReviews(pageIndex, pageSize);
  const { data: approvedVersionsData, isLoading: loadingApproved } =
    useGetVersionsByStatus("Approved", pageIndex, pageSize);
  const { data: rejectedVersionsData, isLoading: loadingRejected } =
    useGetVersionsByStatus("Rejected", pageIndex, pageSize);

  // Extract items and metadata
  const pendingReviews = pendingReviewsData?.items || [];
  const approvedVersions = approvedVersionsData?.items || [];
  const rejectedVersions = rejectedVersionsData?.items || [];

  // Get current tab data for pagination
  const getCurrentTabData = () => {
    switch (activeTab) {
      case "submitted":
        return pendingReviewsData;
      case "approved":
        return approvedVersionsData;
      case "rejected":
        return rejectedVersionsData;
      default:
        return null;
    }
  };

  const currentTabData = getCurrentTabData();

  // Calculate total count across all tabs
  const totalCount =
    (pendingReviewsData?.total || 0) +
    (approvedVersionsData?.total || 0) +
    (rejectedVersionsData?.total || 0);

  // Mutations
  const { mutate: approveVersion, isPending: isApproving } =
    useApproveVersion();
  const { mutate: rejectVersion, isPending: isRejecting } = useRejectVersion();

  const handleApprove = (version: FlowVersionRead) => {
    approveVersion(version.id, {
      onSuccess: () => {
        setSuccessData({ title: `"${version.title}" has been approved` });
      },
      onError: (error: any) => {
        setErrorData({
          title: "Failed to approve",
          list: [
            error?.response?.data?.detail || error.message || "Unknown error",
          ],
        });
      },
    });
  };

  const handleRejectClick = (version: FlowVersionRead) => {
    setSelectedVersion(version);
    setRejectionReason("");
    setRejectModalOpen(true);
  };

  const handleRejectConfirm = () => {
    if (!selectedVersion) return;

    rejectVersion(
      {
        versionId: selectedVersion.id,
        payload: rejectionReason
          ? { rejection_reason: rejectionReason }
          : undefined,
      },
      {
        onSuccess: () => {
          setSuccessData({
            title: `"${selectedVersion.title}" has been rejected`,
          });
          setRejectModalOpen(false);
          setSelectedVersion(null);
          setRejectionReason("");
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to reject",
            list: [
              error?.response?.data?.detail || error.message || "Unknown error",
            ],
          });
        },
      }
    );
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const renderSubmittedTable = () => {
    if (loadingPending) {
      return (
        <div className="flex justify-center py-8">
          <CustomLoader />
        </div>
      );
    }

    if (!pendingReviews || pendingReviews.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground h-full">
          <IconComponent name="Inbox" className="h-12 w-12 mb-4" />
          <p>No pending submissions</p>
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
            <TableHead>Action</TableHead>
            {/* Tags column - commented out for now
            <TableHead>Tags</TableHead>
            
            <TableHead className="text-right">Action</TableHead>*/}
          </TableRow>
        </TableHeader>
        <TableBody>
          {pendingReviews.map((version) => (
            <TableRow key={version.id}>
              <TableCell className="font-medium">{version.title}</TableCell>
              <TableCell className="max-w-xs truncate text-muted-foreground">
                {version.description || (
                  <span className="text-muted-foreground">-</span>
                )}
              </TableCell>
              <TableCell>
                <>
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
                </>
              </TableCell>
              <TableCell>{formatDate(version.submitted_at)}</TableCell>
              <TableCell className="text-center">{version.version}</TableCell>
              <TableCell className="text-center">
                <span className="inline-flex items-center rounded-full bg-[#FDFDD2] px-2.5 py-0.5 text-xs font-medium text-[#826D29] min-h-6">
                  Under Review
                </span>
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
              {/* Tags cell - commented out for now
              <TableCell>
                {version.tags?.length ? (
                  <div className="flex flex-wrap gap-1">
                    {version.tags.slice(0, 2).map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs"
                      >
                        {tag}
                      </span>
                    ))}
                    {version.tags.length > 2 && (
                      <span className="text-xs text-muted-foreground">
                        +{version.tags.length - 2}
                      </span>
                    )}
                  </div>
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </TableCell>
              
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleApprove(version)}
                    disabled={isApproving}
                    className="text-green-600 hover:text-green-700 hover:bg-green-50"
                  >
                    <IconComponent name="Check" className="h-4 w-4 mr-1" />
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleRejectClick(version)}
                    disabled={isRejecting}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  >
                    <IconComponent name="X" className="h-4 w-4 mr-1" />
                    Reject
                  </Button>
                </div>
              </TableCell>
              */}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  };

  const renderApprovedTable = () => {
    if (loadingApproved) {
      return (
        <div className="flex justify-center py-8">
          <CustomLoader />
        </div>
      );
    }

    if (!approvedVersions || approvedVersions.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <IconComponent name="CheckCircle" className="h-12 w-12 mb-4" />
          <p>No approved submissions</p>
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
            <TableHead>Reviewed By</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {approvedVersions.map((version) => (
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
                <span className="inline-flex items-center rounded-full bg-[#f2fff0] px-2.5 py-0.5 text-xs font-medium text-[#3fa33c] min-h-6">
                  Approved
                </span>
              </TableCell>
              <TableCell>
                {version.reviewed_by_name || version.reviewer_name || "Unknown"}
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

  const renderRejectedTable = () => {
    if (loadingRejected) {
      return (
        <div className="flex justify-center py-8">
          <CustomLoader />
        </div>
      );
    }

    if (!rejectedVersions || rejectedVersions.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <IconComponent name="XCircle" className="h-12 w-12 mb-4" />
          <p>No rejected submissions</p>
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
            <TableHead>Rejection Reason</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rejectedVersions.map((version) => (
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
                <span className="inline-flex items-center rounded-full bg-[#fdf4f3] px-2.5 py-0.5 text-xs font-medium text-[#d7503e] min-h-6">
                  Rejected
                </span>
              </TableCell>
              <TableCell className="max-w-xs truncate">
                {version.rejection_reason || (
                  <span className="text-muted-foreground">
                    No reason provided
                  </span>
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
      <h1 className="text-[#350E84] dark:text-white text-[21px] font-medium leading-normal mb-2">
        All Requests{" "}
        {totalCount > 0 && <span className="">({totalCount})</span>}
      </h1>

      <Tabs value={activeTab} onValueChange={handleTabChange} className="flex-1">
        <TabsList className="mb-4 border-b border-[#efefef] w-full gap-8">
          <TabsTrigger value="submitted">
            Submitted
            {pendingReviewsData && pendingReviewsData.total > 0 && (
              <span className="ml-1">({pendingReviewsData.total})</span>
            )}
          </TabsTrigger>
          <TabsTrigger value="approved">
            Approved
            {approvedVersionsData && approvedVersionsData.total > 0 && (
              <span className="ml-1">({approvedVersionsData.total})</span>
            )}
          </TabsTrigger>
          <TabsTrigger value="rejected">
            Rejected
            {rejectedVersionsData && rejectedVersionsData.total > 0 && (
              <span className="ml-1">({rejectedVersionsData.total})</span>
            )}
          </TabsTrigger>
        </TabsList>

        <div className="flex flex-col gap-4">
          {/* Results info and pagination */}
          {/* {currentTabData && currentTabData.total > 0 && (
            <div className="flex items-center justify-between px-1">
              <div className="text-sm text-muted-foreground">
                Showing{" "}
                {Math.min((pageIndex - 1) * pageSize + 1, currentTabData.total)}{" "}
                - {Math.min(pageIndex * pageSize, currentTabData.total)} of{" "}
                {currentTabData.total} results
              </div>
              <FlowPagination
                currentPage={pageIndex}
                pageSize={pageSize}
                totalPages={currentTabData.pages}
                onPageChange={handlePageChange}
                onPageSizeChange={handlePageSizeChange}
              />
            </div>
          )} */}

          <div className="max-h-[calc(100vh-280px)] overflow-y-auto">
            <TabsContent value="submitted" className="m-0">
              {renderSubmittedTable()}
            </TabsContent>
            <TabsContent value="approved" className="m-0">
              {renderApprovedTable()}
            </TabsContent>
            <TabsContent value="rejected" className="m-0">
              {renderRejectedTable()}
            </TabsContent>
          </div>

          {/* Bottom pagination */}
          {currentTabData && currentTabData.total > 0 && (
            <div className="flex items-center justify-between px-1 pb-4">
              <div className="text-sm text-muted-foreground">
                Showing{" "}
                {Math.min((pageIndex - 1) * pageSize + 1, currentTabData.total)}{" "}
                - {Math.min(pageIndex * pageSize, currentTabData.total)} of{" "}
                {currentTabData.total} results
              </div>
              <FlowPagination
                currentPage={pageIndex}
                pageSize={pageSize}
                totalPages={currentTabData.pages}
                onPageChange={handlePageChange}
                onPageSizeChange={handlePageSizeChange}
              />
            </div>
          )}
        </div>
      </Tabs>

      {/* Reject Modal */}
      <Dialog open={rejectModalOpen} onOpenChange={setRejectModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Submission</DialogTitle>
            <DialogDescription>
              Are you sure you want to reject "{selectedVersion?.title}"? You
              can optionally provide a reason.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Label htmlFor="rejection-reason">
              Rejection Reason (Optional)
            </Label>
            <Textarea
              id="rejection-reason"
              placeholder="Provide a reason for rejection..."
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              rows={3}
              className="mt-2"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleRejectConfirm}
              disabled={isRejecting}
            >
              {isRejecting ? "Rejecting..." : "Reject"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
