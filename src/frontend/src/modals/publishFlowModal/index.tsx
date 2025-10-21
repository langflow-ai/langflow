import { useState } from "react";
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
import { usePublishFlow } from "@/controllers/API/queries/published-flows";
import useAlertStore from "@/stores/alertStore";

interface PublishFlowModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowId: string;
  flowName: string;
}

export default function PublishFlowModal({
  open,
  setOpen,
  flowId,
  flowName,
}: PublishFlowModalProps) {
  const [version, setVersion] = useState("");
  const [category, setCategory] = useState("");
  const { mutate: publishFlow, isPending } = usePublishFlow();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const handlePublish = () => {
    publishFlow(
      {
        flowId,
        payload: {
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
          setVersion("");
          setCategory("");
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to publish flow",
            list: [error?.response?.data?.detail || error.message || "Unknown error"],
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

          <div className="rounded-lg bg-muted p-4 text-sm space-y-2">
            <p className="font-medium">What happens when you publish?</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground">
              <li>A snapshot of your current flow will be created</li>
              <li>Your flow will be visible to all users in the Marketplace</li>
              <li>The description and tags from your flow will be used</li>
              <li>To update the marketplace, you'll need to unpublish and re-publish</li>
            </ul>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button onClick={handlePublish} disabled={isPending}>
            {isPending ? "Publishing..." : "Publish to Marketplace"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
