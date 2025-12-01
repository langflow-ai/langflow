import { useState } from "react";
import { useNavigate } from "react-router-dom";
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
  useRejectVersion,
  useCancelSubmission,
} from "@/controllers/API/queries/flow-versions";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { USER_ROLES } from "@/types/auth";
import SubmitForApprovalModal from "@/modals/submitForApprovalModal";
import PublishFlowModal from "@/modals/publishFlowModal";
import { CheckCircle } from "lucide-react";
import { CrossCircledIcon } from "@radix-ui/react-icons";

export default function FlowToolbarOptions() {
  const navigate = useNavigate();
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
  const isFlowCreatedByCurrentUser = isFlowOwner;

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

  // Mutations for reject/cancel
  const { mutate: rejectVersion, isPending: isRejecting } = useRejectVersion();
  const { mutate: cancelSubmission, isPending: isCancelling } =
    useCancelSubmission();
  const { mutateAsync: getFlowMutation } = useGetFlow();

  // For updating flow after cancel submission
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const setCurrentFlowInFlowStore = useFlowStore(
    (state) => state.setCurrentFlow
  );

  // Button visibility logic based on new role-based requirements
  // Publish to Marketplace button - Marketplace Admin only
  const showPublishToMarketplace =
    isMarketplaceAdmin &&
    (!latestStatus ||
      latestStatus === "Draft" ||
      latestStatus === "Submitted" ||
      latestStatus === "Rejected" ||
      latestStatus === "Published" ||
      latestStatus === "Unpublished");

  // Reject button - Marketplace Admin can reject flows NOT created by them (only when status is Submitted)
  const showRejectButton =
    isMarketplaceAdmin &&
    !isFlowCreatedByCurrentUser &&
    latestStatus === "Submitted";

  // Submit for Review button - Show for non-Marketplace Admin users (Agent Developers)
  const showSubmitForReview =
    !isMarketplaceAdmin &&
    (!latestStatus ||
      latestStatus === "Draft" ||
      latestStatus === "Rejected" ||
      latestStatus === "Published" ||
      latestStatus === "Unpublished");

  // Cancel Submission button - Show for non-Marketplace Admin when Submitted
  const showCancelSubmission = !isMarketplaceAdmin && latestStatus === "Submitted";

  // Handlers for reject
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
          navigate("/all-requests");
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

  const handleCancelSubmission = () => {
    if (!latestVersionId || !currentFlowId) return;

    cancelSubmission(latestVersionId, {
      onSuccess: async () => {
        setSuccessData({
          title: `Submission cancelled for "${currentFlowName}"`,
        });

        // Refetch the updated flow to get the unlocked state
        try {
          const updatedFlow = await getFlowMutation({ id: currentFlowId });
          if (updatedFlow) {
            setCurrentFlow(updatedFlow); // Update flowsManagerStore
            setCurrentFlowInFlowStore(updatedFlow); // Update flowStore
          }
        } catch (error) {
          console.error("Failed to refetch flow after cancel:", error);
        }
      },
      onError: (error: any) => {
        setErrorData({
          title: "Failed to cancel submission",
          list: [
            error?.response?.data?.detail || error.message || "Unknown error",
          ],
        });
      },
    });
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

        {/* Reject Button - Only for Marketplace Admin on Rejected flows NOT created by them */}
        {showRejectButton && (
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
        )}

        {/* Publish to Marketplace Button */}
        {showPublishToMarketplace && (
          <Button
            variant="default"
            size="md"
            className="!px-2.5 font-normal"
            onClick={() => setOpenPublishModal(true)}
            data-testid="publish-to-marketplace-button"
          >
            Publish
          </Button>
        )}

        {/* Submit for Review Button - Agent Developer only */}
        {showSubmitForReview && (
          <Button
            variant="link"
            className="!px-1 font-medium text-menu hover:text-secondary"
            onClick={() => setOpenSubmitModal(true)}
            data-testid="submit-for-review-button"
          >
            Submit for Review
          </Button>
        )}

        {/* Cancel Submission Button - Agent Developer when Submitted */}
        {showCancelSubmission && (
          <Button
            variant="link"
            className="!px-1 font-medium text-menu hover:text-secondary"
            onClick={handleCancelSubmission}
            disabled={isCancelling}
            data-testid="cancel-submission-button"
          >
            <IconComponent name="XCircle" className="mr-1.5 h-4 w-4" />
            Cancel Submission
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
              variant="default"
              onClick={handleRejectConfirm}
              disabled={isRejecting}
              className="bg-error hover:bg-error"
            >
              {isRejecting ? "Rejecting..." : "Reject"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
