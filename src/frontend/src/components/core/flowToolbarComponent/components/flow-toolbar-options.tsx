import { useState } from "react";
import { Button } from "@/components/ui/button";
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
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useAuthStore from "@/stores/authStore";
import useAlertStore from "@/stores/alertStore";
import PublishDropdown from "./deploy-dropdown";
import PlaygroundButton from "./playground-button";
import VersionDropdown from "./version-dropdown";
import { useCheckFlowPublished } from "@/controllers/API/queries/published-flows";
import {
  useGetFlowLatestStatus,
  useApproveVersion,
  useRejectVersion,
} from "@/controllers/API/queries/flow-versions";
import { USER_ROLES } from "@/types/auth";
import SubmitForApprovalModal from "@/modals/submitForApprovalModal";
import PublishFlowModal from "@/modals/publishFlowModal";

export default function FlowToolbarOptions() {
  const [open, setOpen] = useState<boolean>(false);
  const [openSubmitModal, setOpenSubmitModal] = useState<boolean>(false);
  const [openPublishModal, setOpenPublishModal] = useState<boolean>(false);
  const [openRejectModal, setOpenRejectModal] = useState<boolean>(false);
  const [rejectionReason, setRejectionReason] = useState<string>("");

  const hasIO = useFlowStore((state) => state.hasIO);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlow?.id);
  const currentFlowName = useFlowsManagerStore(
    (state) => state.currentFlow?.name
  );
  // Get user_id from flowStore (working state) as it has the complete flow data
  const flowUserId = useFlowStore((state) => state.currentFlow?.user_id);

  // Get user roles and current user ID
  const userRoles = useAuthStore((state) => state.userRoles);
  const userData = useAuthStore((state) => state.userData);
  const isMarketplaceAdmin = userRoles.includes(USER_ROLES.MARKETPLACE_ADMIN);

  // Check if current user is the flow owner (both are strings from langflow's internal system)
  const currentUserId = userData?.id;
  const isFlowOwner = !!(
    flowUserId &&
    currentUserId &&
    flowUserId === currentUserId
  );

  // Alert store for success/error messages
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Check if flow is published to show version dropdown
  const { data: publishedData } = useCheckFlowPublished(currentFlowId);
  const isPublished = publishedData?.is_published || false;

  // Check flow approval status
  const { data: flowStatusData } = useGetFlowLatestStatus(currentFlowId);
  const latestStatus = flowStatusData?.latest_status;
  const latestVersionId = flowStatusData?.latest_version_id;

  // Mutations for approve/reject
  const { mutate: approveVersion, isPending: isApproving } =
    useApproveVersion();
  const { mutate: rejectVersion, isPending: isRejecting } = useRejectVersion();

  // Button visibility logic based on status and ownership
  // Submit for Review: Show for Draft, Rejected, Published, Submitted, or no status - ONLY if user is flow owner
  // Disabled when status is 'Submitted' (under review)
  const hiddenSubmitStatuses = ["Approved", "Unpublished", "Deleted"];
  const showSubmitButton =
    isFlowOwner && !hiddenSubmitStatuses.includes(latestStatus || "");
  const isUnderReview = latestStatus === "Submitted";

  // Publish to Marketplace: Show only when status is Approved - ONLY if user is flow owner
  const showPublishButton = isFlowOwner && latestStatus === "Approved";

  // Approve and Reject: Only for Marketplace Admin when status is Submitted
  const showApproveRejectButtons =
    isMarketplaceAdmin && latestStatus === "Submitted";

  // Handlers for approve/reject
  const handleApprove = () => {
    if (!latestVersionId) return;

    approveVersion(latestVersionId, {
      onSuccess: () => {
        setSuccessData({ title: `"${currentFlowName}" has been approved` });
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

  const handleRejectClick = () => {
    setRejectionReason("");
    setOpenRejectModal(true);
  };

  const handleRejectConfirm = () => {
    if (!latestVersionId) return;

    rejectVersion(
      {
        versionId: latestVersionId,
        payload: rejectionReason
          ? { rejection_reason: rejectionReason }
          : undefined,
      },
      {
        onSuccess: () => {
          setSuccessData({ title: `"${currentFlowName}" has been rejected` });
          setOpenRejectModal(false);
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

  return (
    <>
      <div className="flex items-center gap-1.5">
        <div className="flex h-full w-full gap-1.5 rounded-sm transition-all">
          <PlaygroundButton
            hasIO={hasIO}
            open={open}
            setOpen={setOpen}
            canvasOpen
          />
        </div>

        {/* Approve and Reject Buttons - show for Marketplace Admin when status is Submitted */}
        {showApproveRejectButtons && (
          <>
            <Button
              variant="ghost"
              size="xs"
              className="!px-2.5 font-normal text-green-600 hover:text-green-700 hover:bg-green-50"
              onClick={handleApprove}
              disabled={isApproving}
              data-testid="approve-button"
            >
              <IconComponent name="Check" className="mr-1.5 h-4 w-4" />
              Approve
            </Button>
            <Button
              variant="ghost"
              size="xs"
              className="!px-2.5 font-normal text-red-600 hover:text-red-700 hover:bg-red-50"
              onClick={handleRejectClick}
              disabled={isRejecting}
              data-testid="reject-button"
            >
              <IconComponent name="X" className="mr-1.5 h-4 w-4" />
              Reject
            </Button>
          </>
        )}

        {/* Submit for Review Button - show for Agent Developer (not Marketplace Admin), disabled when under review */}
        {showSubmitButton && (
          <Button
            variant="ghost"
            size="xs"
            className="!px-2.5 font-normal"
            onClick={() => setOpenSubmitModal(true)}
            disabled={isUnderReview}
            data-testid="submit-for-review-button"
          >
            Submit for Review
          </Button>
        )}

        {/* Publish to Marketplace Button - show when status is Approved */}
        {showPublishButton && (
          <Button
            variant="default"
            size="md"
            className="!px-2.5 font-normal"
            onClick={() => setOpenPublishModal(true)}
            data-testid="publish-to-marketplace-button"
          >
            Publish to Marketplace
          </Button>
        )}

        {/* Version Dropdown - only show if flow is published */}
        {isPublished && currentFlowId && (
          <VersionDropdown flowId={currentFlowId} />
        )}

        <PublishDropdown />

        {/* Submit for Approval Modal */}
        <SubmitForApprovalModal
          open={openSubmitModal}
          setOpen={setOpenSubmitModal}
          flowId={currentFlowId ?? ""}
          flowName={currentFlowName ?? ""}
        />

        {/* Publish Flow Modal */}
        <PublishFlowModal
          open={openPublishModal}
          setOpen={setOpenPublishModal}
          flowId={currentFlowId ?? ""}
          flowName={currentFlowName ?? ""}
          existingPublishedData={publishedData}
          approvalData={flowStatusData}
        />
      </div>

      {/* Reject Modal */}
      <Dialog open={openRejectModal} onOpenChange={setOpenRejectModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Submission</DialogTitle>
            <DialogDescription>
              Are you sure you want to reject "{currentFlowName}"? You can
              optionally provide a reason.
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
            <Button variant="outline" onClick={() => setOpenRejectModal(false)}>
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
    </>
  );
}
