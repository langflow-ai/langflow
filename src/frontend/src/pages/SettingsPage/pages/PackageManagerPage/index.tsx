import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  useClearInstallationStatus,
  useGetInstallationStatus,
  useInstallPackage,
} from "@/controllers/API/queries/packages";
import useAlertStore from "@/stores/alertStore";
import { usePackageManagerStore } from "@/stores/packageManagerStore";
import InstalledPackagesTable from "./components/InstalledPackagesTable";

export default function PackageManagerPage() {
  const [packageName, setPackageName] = useState("");
  const [showInstallDialog, setShowInstallDialog] = useState(false);
  const [showProgressDialog, setShowProgressDialog] = useState(false);
  const [lastHandledError, setLastHandledError] = useState<string | null>(null);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const clearTempNotificationList = useAlertStore(
    (state) => state.clearTempNotificationList,
  );
  const setIsInstallingPackage = usePackageManagerStore(
    (state) => state.setIsInstallingPackage,
  );

  const queryClient = useQueryClient();
  const installPackageMutation = useInstallPackage();
  const installationStatus = useGetInstallationStatus(showProgressDialog);
  const clearInstallationStatusMutation = useClearInstallationStatus();

  const handleInstallClick = () => {
    if (!packageName.trim()) {
      setErrorData({ title: "Package name is required" });
      return;
    }
    // Only clear notifications when starting a new installation
    clearTempNotificationList(); // Clear currently displayed notifications
    setLastHandledError(null); // Reset error tracking
    setShowInstallDialog(true);
  };

  const handleConfirmInstall = async () => {
    setShowInstallDialog(false);
    setShowProgressDialog(true);
    setIsInstallingPackage(true);
    setLastHandledError(null); // Reset error tracking

    try {
      // Clear any previous installation status before starting new installation
      await clearInstallationStatusMutation.mutateAsync();

      // Force invalidate the installation status query (this will trigger a refetch)
      await queryClient.invalidateQueries({
        queryKey: ["installation-status"],
      });

      // Small delay to ensure status is cleared
      await new Promise((resolve) => setTimeout(resolve, 200));

      await installPackageMutation.mutateAsync(packageName.trim());
    } catch (error: any) {
      const errorMessage =
        error?.response?.data?.detail || error.message || "Unknown error";
      setErrorData({
        title: "Installation Failed",
        list: [
          errorMessage.length > 200
            ? errorMessage.substring(0, 200) + "..."
            : errorMessage,
        ],
      });
      setShowProgressDialog(false);
      setIsInstallingPackage(false);
    }
  };

  // Get installation status from backend
  const installationResult = installationStatus.data?.last_result;

  // Handle installation completion (success or failure)
  useEffect(() => {
    // Only proceed if we have a definitive status from the backend
    if (
      showProgressDialog &&
      installationResult &&
      (installationResult.status === "completed" ||
        installationResult.status === "failed")
    ) {
      // Ensure this notification is for the current package being installed
      if (installationResult.package_name !== packageName.trim()) {
        console.log(
          `Ignoring stale result for ${installationResult.package_name}, current package is ${packageName}`,
        );
        return;
      }

      const errorKey = `${installationResult.package_name}-${installationResult.status}`;

      // Prevent duplicate notifications
      if (errorKey === lastHandledError) {
        return;
      }

      console.log(
        `Processing installation result: ${installationResult.package_name} - ${installationResult.status}`,
      );

      setShowProgressDialog(false);
      setIsInstallingPackage(false);
      setLastHandledError(errorKey);

      if (installationResult.status === "completed") {
        setSuccessData({
          title: `Package '${installationResult.package_name}' installed successfully! The package is now available for import.`,
        });
        // Refresh the installed packages list to show the newly installed package
        queryClient.invalidateQueries({ queryKey: ["installed-packages"] });
      } else if (installationResult.status === "failed") {
        // Extract and clean the error message
        const rawError = installationResult.message || "Unknown error";
        let cleanError = rawError;

        // For dependency resolution errors, extract key information
        if (
          rawError.includes("No solution found when resolving dependencies")
        ) {
          const pkgName = installationResult.package_name || "package";
          if (rawError.includes("requires-python")) {
            cleanError = `Package '${pkgName}' requires a different Python version than what's currently available. Please check the package documentation for compatibility requirements.`;
          } else {
            cleanError = `Package '${pkgName}' has dependency conflicts that prevent installation. This may be due to version incompatibilities with existing packages.`;
          }
        }
        // For other uv errors, try to extract the first meaningful line
        else if (rawError.includes("×")) {
          const lines = rawError.split("\n");
          const errorLine =
            lines.find((line) => line.includes("×")) || lines[0];
          cleanError = errorLine.replace(/^\s*×\s*/, "").trim();
        }

        setErrorData({
          title: "Installation Failed",
          list: [cleanError],
        });
      }
      setPackageName("");
    }
  }, [
    showProgressDialog,
    installationResult,
    packageName,
    lastHandledError,
    setErrorData,
    setSuccessData,
    setIsInstallingPackage,
  ]);

  // Show error if installation API call failed (not installation itself failed)
  useEffect(() => {
    if (showProgressDialog && installPackageMutation.isError) {
      setShowProgressDialog(false);
      setIsInstallingPackage(false);
      const error = installPackageMutation.error as any;
      const errorMessage =
        error?.response?.data?.detail || error?.message || "Unknown error";

      // Only show API-level errors here, not installation failures
      // Installation failures are handled by the installation status handler
      setErrorData({
        title: "Installation Request Failed",
        list: [
          errorMessage.length > 200
            ? errorMessage.substring(0, 200) + "..."
            : errorMessage,
        ],
      });
      setPackageName("");
    }
  }, [
    showProgressDialog,
    installPackageMutation.isError,
    installPackageMutation.error,
    setErrorData,
    setIsInstallingPackage,
  ]);

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Package Manager</h1>
        <p className="text-muted-foreground">
          Install Python packages into your Langflow environment using uv
          package manager.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ForwardedIconComponent name="Package" className="h-5 w-5" />
            Install Package
          </CardTitle>
          <CardDescription>
            Enter the name of a Python package to install it into your Langflow
            environment. The package will be available immediately after
            installation.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-3">
            <Input
              placeholder="Package name with optional version (e.g., pandas==2.3.1, requests>=2.25.0)"
              value={packageName}
              onChange={(e) => setPackageName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleInstallClick();
                }
              }}
              className="flex-1"
              disabled={installPackageMutation.isPending}
            />
            <Button
              onClick={handleInstallClick}
              disabled={installPackageMutation.isPending || !packageName.trim()}
            >
              {installPackageMutation.isPending ? (
                <>
                  <ForwardedIconComponent
                    name="Loader2"
                    className="mr-2 h-4 w-4 animate-spin"
                  />
                  Installing...
                </>
              ) : (
                "Install Package"
              )}
            </Button>
          </div>

          <p className="text-sm text-muted-foreground">
            Supported version operators: <code>==</code> (exact),{" "}
            <code>&gt;=</code> (minimum), <code>&lt;=</code> (maximum),{" "}
            <code>&gt;</code>, <code>&lt;</code>, <code>!=</code> (not equal)
          </p>

          <Alert>
            <ForwardedIconComponent name="Info" className="h-4 w-4" />
            <AlertDescription>
              <strong>Note:</strong> Packages are installed directly into your
              Langflow environment and will be available immediately for import
              in your flows.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      {/* Installed Packages Table */}
      <InstalledPackagesTable />

      {/* Install Confirmation Dialog */}
      <Dialog open={showInstallDialog} onOpenChange={setShowInstallDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Package Installation</DialogTitle>
            <DialogDescription>
              Are you sure you want to install <strong>{packageName}</strong>?
              <br />
              <br />
              This will:
              <ul className="list-disc list-inside mt-2 space-y-1">
                <li>Install the package using uv package manager</li>
                <li>Make the package available for import in your flows</li>
                <li>Complete without interrupting your current session</li>
              </ul>
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={() => setShowInstallDialog(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmInstall}
              disabled={installPackageMutation.isPending}
            >
              {installPackageMutation.isPending ? (
                <>
                  <ForwardedIconComponent
                    name="Loader2"
                    className="mr-2 h-4 w-4 animate-spin"
                  />
                  Installing...
                </>
              ) : (
                "Install Package"
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Installation Progress Dialog */}
      <Dialog open={showProgressDialog} onOpenChange={() => {}}>
        <DialogContent className="sm:max-w-md" closeButtonClassName="hidden">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ForwardedIconComponent name="Package" className="h-5 w-5" />
              Installing Package
            </DialogTitle>
            <DialogDescription>
              Please wait while the package is being installed...
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 rounded-lg bg-muted">
              <ForwardedIconComponent
                name="Loader2"
                className="h-5 w-5 animate-spin text-primary"
              />
              <div>
                <p className="font-medium">Installing {packageName}</p>
                <p className="text-sm text-muted-foreground">
                  {installPackageMutation.isPending
                    ? "Installation in progress..."
                    : installPackageMutation.isSuccess &&
                        (!installationResult ||
                          (installationResult.status !== "completed" &&
                            installationResult.status !== "failed"))
                      ? "Checking installation status..."
                      : "Waiting for installation to complete..."}
                </p>
              </div>
            </div>

            <Alert>
              <ForwardedIconComponent name="Info" className="h-4 w-4" />
              <AlertDescription>
                Please wait while the package is being installed. This process
                typically takes a few moments to complete.
              </AlertDescription>
            </Alert>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
