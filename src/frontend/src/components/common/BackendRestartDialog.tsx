import { useEffect, useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useBackendHealth } from "@/hooks/use-backend-health";

interface BackendRestartDialogProps {
  isOpen: boolean;
  onClose: () => void;
  reason?: string;
}

export default function BackendRestartDialog({
  isOpen,
  onClose,
  reason = "Backend is restarting after package operation",
}: BackendRestartDialogProps) {
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [debugInfo, setDebugInfo] = useState<string>("");
  const [timeoutReached, setTimeoutReached] = useState(false);
  const backendHealth = useBackendHealth(isCheckingHealth);

  useEffect(() => {
    if (isOpen) {
      // Start checking backend health when dialog opens
      setIsCheckingHealth(true);
      setTimeoutReached(false);

      // Auto-close after 30 seconds as a fallback
      const fallbackTimeout = setTimeout(() => {
        console.log("Backend restart dialog timeout reached, auto-closing");
        setTimeoutReached(true);
        setIsCheckingHealth(false);
        onClose();
      }, 30000); // 30 second timeout

      return () => clearTimeout(fallbackTimeout);
    } else {
      setIsCheckingHealth(false);
      setTimeoutReached(false);
    }
  }, [isOpen, onClose]);

  // Debug logging
  useEffect(() => {
    if (isCheckingHealth) {
      const status =
        backendHealth.data === true
          ? "✅ ONLINE"
          : backendHealth.data === false
            ? "❌ OFFLINE"
            : "⏳ CHECKING";
      const info = `Status: ${status} | Checking: ${isCheckingHealth} | Loading: ${backendHealth.isLoading}`;
      setDebugInfo(info);
      console.log("Backend Health:", info);
    }
  }, [backendHealth.data, backendHealth.isLoading, isCheckingHealth]);

  useEffect(() => {
    if (
      isCheckingHealth &&
      backendHealth.data === true &&
      !backendHealth.isLoading
    ) {
      console.log("Backend is back online, closing dialog in 2 seconds...");
      // Backend is back online, wait a bit to ensure stability
      const timeout = setTimeout(() => {
        console.log("Closing backend restart dialog");
        onClose();
        setIsCheckingHealth(false);
      }, 2000); // 2 second delay to ensure backend is fully ready

      return () => clearTimeout(timeout);
    }
  }, [backendHealth.data, backendHealth.isLoading, isCheckingHealth, onClose]);

  const handleManualClose = () => {
    console.log("Manual close of backend restart dialog");
    setIsCheckingHealth(false);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <Dialog open={isOpen} onOpenChange={() => {}}>
      <DialogContent className="sm:max-w-md" closeButtonClassName="hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ForwardedIconComponent
              name="RefreshCw"
              className="h-5 w-5 animate-spin text-warning"
            />
            Backend Restarting
          </DialogTitle>
          <DialogDescription>{reason}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-center gap-3 p-4 rounded-lg bg-muted">
            <ForwardedIconComponent
              name="Loader2"
              className="h-5 w-5 animate-spin text-warning"
            />
            <div>
              <p className="font-medium">
                {backendHealth.data === false
                  ? "Backend is restarting..."
                  : "Reconnecting..."}
              </p>
              <p className="text-sm text-muted-foreground">
                Please wait while the backend restarts. This usually takes a few
                seconds.
              </p>
            </div>
          </div>

          <div className="text-sm text-muted-foreground">
            <p>
              <strong>Note:</strong> Package operations may trigger a backend
              restart in development mode. This is normal behavior.
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
