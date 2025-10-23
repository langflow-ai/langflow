import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePublishFlow, type PublishCheckResponse } from "@/controllers/API/queries/published-flows";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { validateFlowForPublish } from "@/utils/flowValidation";
import type { AllNodeType, EdgeType } from "@/types/flow";

interface PublishFlowModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowId: string;
  flowName: string;
  existingPublishedData?: PublishCheckResponse;
}

export default function PublishFlowModal({
  open,
  setOpen,
  flowId,
  flowName,
  existingPublishedData,
}: PublishFlowModalProps) {
  const [marketplaceName, setMarketplaceName] = useState(flowName);
  const [version, setVersion] = useState("");
  const [category, setCategory] = useState("");
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const { mutate: publishFlow, isPending } = usePublishFlow();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const currentFlowManager = useFlowsManagerStore(
    (state) => state.currentFlow
  );

  // Pre-fill form fields when modal opens
  useEffect(() => {
    if (open) {
      if (existingPublishedData?.is_published) {
        // Re-publish: Pre-fill with existing published data
        setMarketplaceName(existingPublishedData.marketplace_flow_name || flowName);
        setVersion(existingPublishedData.version || "");
        setCategory(existingPublishedData.category || "");
      } else {
        // First-time publish: Use defaults
        setMarketplaceName(flowName);
        setVersion("");
        setCategory("");
      }
    }
  }, [open, existingPublishedData, flowName]);

  // Run validation when modal opens
  useEffect(() => {
    if (open && currentFlow) {
      const nodes = (currentFlow.data?.nodes ?? []) as AllNodeType[];
      const edges = (currentFlow.data?.edges ?? []) as EdgeType[];
      const errors = validateFlowForPublish(nodes, edges);
      setValidationErrors(errors);
    }
  }, [open, currentFlow]);

  const handlePublish = () => {
    // Validate required fields
    if (!marketplaceName.trim()) {
      setErrorData({
        title: "Cannot publish flow",
        list: ["Marketplace flow name is required"],
      });
      return;
    }

    // Validate flow before publishing
    if (!currentFlow) {
      setErrorData({
        title: "Cannot publish flow",
        list: ["Flow data not available"],
      });
      return;
    }

    const nodes = (currentFlow.data?.nodes ?? []) as AllNodeType[];
    const edges = (currentFlow.data?.edges ?? []) as EdgeType[];
    const errors = validateFlowForPublish(nodes, edges);

    if (errors.length > 0) {
      setValidationErrors(errors);
      setErrorData({
        title: "Cannot Publish Flow",
        list: errors,
      });
      return;
    }

    // Validation passed - clear any previous errors and proceed with publish
    setValidationErrors([]);

    publishFlow(
      {
        flowId,
        payload: {
          marketplace_flow_name: marketplaceName,
          version: version || undefined,
          category: category || undefined,
        },
      },
      {
        onSuccess: () => {
          setSuccessData({
            title: "Flow published successfully!",
          });
          setOpen(false);
          setMarketplaceName("");
          setVersion("");
          setCategory("");
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to publish flow",
            list: [
              error?.response?.data?.detail || error.message || "Unknown error",
            ],
          });
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Publish "{flowName}" to Marketplace</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="marketplace-name">
              Marketplace Flow Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="marketplace-name"
              placeholder={flowName}
              value={marketplaceName}
              onChange={(e) => setMarketplaceName(e.target.value)}
              required
            />
            <p className="text-xs text-muted-foreground">
              Name for the cloned flow in the marketplace
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="version">Version (Optional)</Label>
            <Input
              id="version"
              placeholder="1.0.0"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Semantic versioning recommended (e.g., 1.0.0, 1.2.3)
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="category">Category (Optional)</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger id="category">
                <SelectValue placeholder="Select category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Healthcare">Healthcare</SelectItem>
                <SelectItem value="Finance">Finance</SelectItem>
                <SelectItem value="Education">Education</SelectItem>
                <SelectItem value="General">General</SelectItem>
                <SelectItem value="Other">Other</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {validationErrors.length === 0 && (
            <div className="rounded-lg bg-muted p-4 text-sm space-y-2">
              <p className="font-medium">What happens when you publish?</p>
              <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                <li>Your flow will be visible to all users in the Marketplace</li>
                <li>To update the marketplace, you'll need to re-publish</li>
              </ul>
            </div>
          )}

          {validationErrors.length > 0 && (
            <div className="rounded-md bg-red-50 p-4 border border-red-200">
              <h4 className="text-sm font-semibold text-red-800 mb-2">
                ⚠️ Cannot Publish - Please Fix These Issues:
              </h4>
              <ul className="list-disc list-inside space-y-1">
                {validationErrors.map((error, index) => (
                  <li key={index} className="text-sm text-red-700">
                    {error}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handlePublish}
            disabled={isPending || validationErrors.length > 0}
          >
            {isPending ? "Publishing..." : "Publish to Marketplace"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
