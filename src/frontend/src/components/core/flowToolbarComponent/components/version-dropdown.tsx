import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  useGetFlowVersions,
  PublishedFlowVersion,
} from "@/controllers/API/queries/published-flows/use-get-flow-versions";
import { useRevertToVersion } from "@/controllers/API/queries/published-flows/use-revert-to-version";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import moment from "moment";

interface VersionDropdownProps {
  flowId: string;
  onVersionReverted?: () => void;
}

export default function VersionDropdown({
  flowId,
  onVersionReverted,
}: VersionDropdownProps) {
  const { data: versions, isLoading } = useGetFlowVersions(flowId);
  const { mutate: revertToVersion, isPending } = useRevertToVersion();
  const { mutateAsync: getFlow } = useGetFlow();
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const [selectedVersion, setSelectedVersion] =
    useState<PublishedFlowVersion | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  const activeVersion = versions?.find((v) => v.active);
  const draftedVersion = versions?.find((v) => v.drafted);

  const handleVersionSelect = (version: PublishedFlowVersion) => {
    setSelectedVersion(version);
    setShowConfirmDialog(true);
  };

  const handleConfirmRevert = () => {
    if (!selectedVersion) return;

    revertToVersion(
      { flowId, versionId: selectedVersion.id },
      {
        onSuccess: async () => {
          setShowConfirmDialog(false);
          setSelectedVersion(null);

          // Refetch the flow data without page reload
          try {
            const updatedFlow = await getFlow({ id: flowId });
            if (updatedFlow) {
              setCurrentFlow(updatedFlow);
            }
          } catch (error) {
            console.error("Failed to reload flow after revert:", error);
            // Fallback to page reload if API call fails
            window.location.reload();
          }

          // Still call the callback if provided
          if (onVersionReverted) {
            onVersionReverted();
          }
        },
      }
    );
  };

  // Don't show dropdown if no versions or loading
  if (!versions || versions.length === 0 || isLoading) {
    return null;
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="link"
            className="!px-1 font-medium text-menu hover:text-secondary !py-0 !h-auto !gap-1"
            data-testid="version-dropdown-trigger"
          >
            <ForwardedIconComponent name="History" className="h-4 w-4" />
            Version {draftedVersion?.version || activeVersion?.version}
            {/* <ForwardedIconComponent name="ChevronDown" className="h-4 w-4" /> */}
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="end" className="w-64">
          <DropdownMenuLabel>Select Version</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <div className="max-h-[400px] overflow-auto">
            {versions.map((version) => (
              <DropdownMenuItem
                key={version.id}
                onClick={() => handleVersionSelect(version)}
                disabled={isPending}
                className="flex cursor-pointer items-center justify-between"
                data-testid={`version-item-${version.version}`}
              >
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{version.version}</span>
                    {version.status_name === "Published" && (
                      <Badge variant="default" className="text-xs">
                        Published
                      </Badge>
                    )}
                  </div>
                  <span className="text-xs text-secondary-font">
                    {moment(version.published_at).fromNow()}
                  </span>
                </div>

                {version.drafted && (
                  <ForwardedIconComponent
                    name="Check"
                    className="h-4 w-4 text-menu"
                  />
                )}
              </DropdownMenuItem>
            ))}
          </div>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Confirmation Dialog */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Switch to Version {selectedVersion?.version}?
            </DialogTitle>
          </DialogHeader>
          <p className="my-6 text-secondary-font text-sm">
            Are you sure you want to switch to Version{" "}
            <span className="font-semibold text-primary-font">
              {selectedVersion?.version}
            </span>
            ? Any unsaved changes may be lost.
          </p>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowConfirmDialog(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button onClick={handleConfirmRevert} disabled={isPending}>
              {isPending ? "Switching..." : "Switch Version"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
