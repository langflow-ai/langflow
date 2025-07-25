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
import { useGetHealthQuery } from "@/controllers/API/queries/health";
import {
  useClearInstallationStatus,
  useGetInstallationStatus,
  useInstallPackage,
} from "@/controllers/API/queries/packages";
import useAlertStore from "@/stores/alertStore";
import { usePackageManagerStore } from "@/stores/packageManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";

export default function PackageManagerPage() {
  const [packageName, setPackageName] = useState("");
  const [showInstallDialog, setShowInstallDialog] = useState(false);
  const [showProgressDialog, setShowProgressDialog] = useState(false);
  const [backendWentDown, setBackendWentDown] = useState(false);
  const [installationWasSuccessful, setInstallationWasSuccessful] =
    useState(false);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setIsInstallingPackage = usePackageManagerStore(
    (state) => state.setIsInstallingPackage,
  );
  const setHealthCheckTimeout = useUtilityStore(
    (state) => state.setHealthCheckTimeout,
  );

  const installPackageMutation = useInstallPackage();
  const installationStatus = useGetInstallationStatus(showProgressDialog);
  const healthCheck = useGetHealthQuery({ enableInterval: showProgressDialog });
  const clearInstallationStatusMutation = useClearInstallationStatus();

  const handleInstallClick = () => {
    if (!packageName.trim()) {
      setErrorData({ title: "Package name is required" });
      return;
    }
    setShowInstallDialog(true);
  };

  const handleConfirmInstall = async () => {
    setShowInstallDialog(false);
    // Clear any existing error alerts and stored errors before starting new installation
    setErrorData({ title: "", list: [] });
    localStorage.removeItem("packageInstallationError");
    setShowProgressDialog(true);
    setIsInstallingPackage(true);
    setBackendWentDown(false); // Reset the restart tracking
    setInstallationWasSuccessful(false); // Reset success tracking
    // Clear any existing health check timeout states
    setHealthCheckTimeout(null);

    try {
      // Clear any previous installation status before starting new installation
      await clearInstallationStatusMutation.mutateAsync();

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
      setBackendWentDown(false);
      setInstallationWasSuccessful(false);
    }
  };

  // Check if backend is back online after installation
  const isBackendOnline =
    healthCheck.data?.status === "ok" &&
    !healthCheck.isFetching &&
    !healthCheck.isError;
  const isBackendDown = healthCheck.isError || healthCheck.isFetching;

  // Get installation status from backend (this persists during the installation but resets on restart)
  const installationResult = installationStatus.data?.last_result;
  const currentlySuccessful = installationResult?.status === "success";
  const hasInstallationError = installationResult?.status === "error";

  // Track when installation becomes successful (using useEffect to prevent infinite renders)
  useEffect(() => {
    if (currentlySuccessful && !installationWasSuccessful) {
      setInstallationWasSuccessful(true);
    }
  }, [currentlySuccessful, installationWasSuccessful]);

  // Track when installation has an error (using useEffect to prevent infinite renders)
  useEffect(() => {
    if (
      hasInstallationError &&
      installationResult &&
      !installationWasSuccessful
    ) {
      // Store the error to show after restart
      const rawError = installationResult.message || "Unknown error";
      let cleanError = rawError;

      // For dependency resolution errors, extract key information
      if (rawError.includes("No solution found when resolving dependencies")) {
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
        const errorLine = lines.find((line) => line.includes("×")) || lines[0];
        cleanError = errorLine.replace(/^\s*×\s*/, "").trim();
      }

      // Store error in local state to show after restart
      localStorage.setItem(
        "packageInstallationError",
        JSON.stringify({
          title: "Installation Failed",
          list: [cleanError],
          packageName: packageName,
        }),
      );
    }
  }, [
    hasInstallationError,
    installationResult,
    installationWasSuccessful,
    packageName,
  ]);

  // Track when backend goes down after installation (using useEffect to prevent infinite renders)
  useEffect(() => {
    // Simplified: If installation API succeeded and backend goes down, it means restart is happening
    if (
      showProgressDialog &&
      installPackageMutation.isSuccess &&
      isBackendDown &&
      !backendWentDown
    ) {
      console.log("Setting backendWentDown = true");
      setBackendWentDown(true);
    }
  }, [
    showProgressDialog,
    installPackageMutation.isSuccess,
    isBackendDown,
    backendWentDown,
  ]);

  // Close progress dialog after backend restart (using useEffect to prevent infinite renders)
  useEffect(() => {
    const hasCompletedRestart = backendWentDown && isBackendOnline;

    if (showProgressDialog && hasCompletedRestart) {
      console.log("Closing dialog after restart completion");
      setShowProgressDialog(false);
      setIsInstallingPackage(false);
      setBackendWentDown(false);
      setInstallationWasSuccessful(false);

      // Check if there was an error stored before restart
      const storedError = localStorage.getItem("packageInstallationError");
      if (storedError) {
        // Show error after restart
        const errorData = JSON.parse(storedError);
        setErrorData(errorData);
        localStorage.removeItem("packageInstallationError");
      } else if (installationWasSuccessful) {
        // Show success
        setSuccessData({
          title: `Package '${packageName}' installed successfully! The application has been restarted with the new package.`,
        });
      }
      setPackageName("");
    }
  }, [
    showProgressDialog,
    backendWentDown,
    isBackendOnline,
    installationWasSuccessful,
    packageName,
    setErrorData,
    setSuccessData,
    setIsInstallingPackage,
    healthCheck.data,
    installationStatus.data,
  ]);

  // Show error if installation API call failed (using useEffect to prevent infinite renders)
  useEffect(() => {
    if (showProgressDialog && installPackageMutation.isError) {
      setShowProgressDialog(false);
      setIsInstallingPackage(false);
      setBackendWentDown(false);
      setInstallationWasSuccessful(false);
      const error = installPackageMutation.error as any;
      const errorMessage =
        error?.response?.data?.detail || error?.message || "Unknown error";
      setErrorData({
        title: "Installation Failed",
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
            environment. The application will restart automatically after
            installation.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-3">
            <Input
              placeholder="Package name (e.g., pandas, requests, numpy)"
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

          <Alert>
            <ForwardedIconComponent name="AlertTriangle" className="h-4 w-4" />
            <AlertDescription>
              <strong>Warning:</strong> Installing packages will restart the
              Langflow application. Make sure to save any unsaved work before
              proceeding.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

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
                <li>Restart the Langflow application</li>
                <li>Temporarily interrupt your current session</li>
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
                className="h-5 w-5 animate-spin text-blue-500"
              />
              <div>
                <p className="font-medium">Installing {packageName}</p>
                <p className="text-sm text-muted-foreground">
                  {installPackageMutation.isPending
                    ? "Installation in progress..."
                    : installationWasSuccessful && !backendWentDown
                      ? "Installation complete. Backend is restarting..."
                      : installationWasSuccessful && backendWentDown
                        ? "Backend restarted. Coming back online..."
                        : installPackageMutation.isSuccess &&
                            !installationWasSuccessful &&
                            !hasInstallationError
                          ? "Checking installation status..."
                          : "Waiting for installation to complete..."}
                </p>
              </div>
            </div>

            <Alert>
              <ForwardedIconComponent
                name="AlertTriangle"
                className="h-4 w-4"
              />
              <AlertDescription>
                Do not close this dialog or refresh the page. The application
                will restart automatically after the package is installed.
              </AlertDescription>
            </Alert>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
