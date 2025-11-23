import { useState } from "react";
import { Button } from "@/components/ui/button";
import IconComponent from "@/components/common/genericIconComponent";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import PublishDropdown from "./deploy-dropdown";
import PlaygroundButton from "./playground-button";
import VersionDropdown from "./version-dropdown";
import { useCheckFlowPublished } from "@/controllers/API/queries/published-flows";
import { useGetFlowLatestStatus } from "@/controllers/API/queries/flow-versions";
import SubmitForApprovalModal from "@/modals/submitForApprovalModal";
import PublishFlowModal from "@/modals/publishFlowModal";

export default function FlowToolbarOptions() {
  const [open, setOpen] = useState<boolean>(false);
  const [openSubmitModal, setOpenSubmitModal] = useState<boolean>(false);
  const [openPublishModal, setOpenPublishModal] = useState<boolean>(false);
  const hasIO = useFlowStore((state) => state.hasIO);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlow?.id);
  const currentFlowName = useFlowsManagerStore((state) => state.currentFlow?.name);

  // Check if flow is published to show version dropdown
  const { data: publishedData } = useCheckFlowPublished(currentFlowId);
  const isPublished = publishedData?.is_published || false;

  // Check flow approval status
  const { data: flowStatusData } = useGetFlowLatestStatus(currentFlowId);
  const latestStatus = flowStatusData?.latest_status;
  const isUnderReview = latestStatus === "Submitted";
  const isApproved = latestStatus === "Approved";
  // Show button when: Draft, Rejected, Published, no status, or Under Review (disabled)
  // Hide only when Approved (waiting to be published)
  const showSubmitButton = !isApproved;
  // Show publish button when approved (for both first publish and re-publish)
  const showPublishButton = isApproved;

  return (
    <div className="flex items-center gap-1.5">
      <div className="flex h-full w-full gap-1.5 rounded-sm transition-all">
        <PlaygroundButton
          hasIO={hasIO}
          open={open}
          setOpen={setOpen}
          canvasOpen
        />
      </div>

      {/* Submit for Review Button - show when not approved/published, disabled when under review */}
      {showSubmitButton && (
        <Button
          variant="ghost"
          size="md"
          className="!px-2.5 font-normal"
          onClick={() => setOpenSubmitModal(true)}
          disabled={isUnderReview}
          data-testid="submit-for-review-button"
        >
          {/* <IconComponent name="Send" className="mr-1.5 h-4 w-4" /> */}
          Submit for Review
        </Button>
      )}

      {/* Publish to Marketplace Button - show when approved but not yet published */}
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
  );
}
