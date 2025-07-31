import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import BackendRestartDialog from "@/components/common/BackendRestartDialog";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useClearInstallationStatus,
  useGetInstallationStatus,
  useGetInstalledPackages,
  useUninstallPackage,
} from "@/controllers/API/queries/packages";
import useAlertStore from "@/stores/alertStore";
import { usePackageManagerStore } from "@/stores/packageManagerStore";

export default function InstalledPackagesTable() {
  const [showUninstallDialog, setShowUninstallDialog] = useState(false);
  const [showProgressDialog, setShowProgressDialog] = useState(false);
  const [packageToUninstall, setPackageToUninstall] = useState<string>("");
  const [lastHandledError, setLastHandledError] = useState<string | null>(null);
  const [showBackendRestartDialog, setShowBackendRestartDialog] =
    useState(false);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const clearTempNotificationList = useAlertStore(
    (state) => state.clearTempNotificationList,
  );
  const setIsInstallingPackage = usePackageManagerStore(
    (state) => state.setIsInstallingPackage,
  );

  const queryClient = useQueryClient();
  const installedPackagesQuery = useGetInstalledPackages();
  const uninstallPackageMutation = useUninstallPackage();
  // Only poll for status if progress dialog is shown AND we haven't had an API error AND mutation hasn't failed
  const shouldPollStatus =
    showProgressDialog &&
    !lastHandledError?.includes(`${packageToUninstall}-api-error`) &&
    !uninstallPackageMutation.isError;
  const installationStatus = useGetInstallationStatus(shouldPollStatus);
  const clearInstallationStatusMutation = useClearInstallationStatus();

  const handleUninstallClick = (packageName: string) => {
    setPackageToUninstall(packageName);
    clearTempNotificationList();
    setLastHandledError(null);
    setShowUninstallDialog(true);
  };

  const handleConfirmUninstall = async () => {
    setShowUninstallDialog(false);
    setShowProgressDialog(true);
    setIsInstallingPackage(true);
    setLastHandledError(null); // Reset error tracking for new operation

    try {
      // Clear any previous installation status before starting new uninstallation
      await clearInstallationStatusMutation.mutateAsync();

      // Force invalidate the installation status query (this will trigger a refetch)
      await queryClient.invalidateQueries({
        queryKey: ["installation-status"],
      });

      // Small delay to ensure status is cleared
      await new Promise((resolve) => setTimeout(resolve, 200));

      await uninstallPackageMutation.mutateAsync(packageToUninstall);

      // Show backend restart dialog immediately after uninstall request
      // because uninstall operations typically trigger backend restarts
      setTimeout(() => {
        setShowBackendRestartDialog(true);
      }, 1000); // Small delay to let the success notification show first
    } catch (error: any) {
      const errorMessage =
        error?.response?.data?.detail || error.message || "Unknown error";
      setErrorData({
        title: "Uninstallation Failed",
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
  const installationResult = installationStatus?.data?.last_result;

  // Handle uninstallation completion (success or failure)
  useEffect(() => {
    // Don't process if we already handled an API error for this package
    if (lastHandledError?.includes(`${packageToUninstall}-api-error`)) {
      return;
    }

    // Only proceed if we have a definitive status from the backend and progress dialog is shown
    if (
      showProgressDialog &&
      installationResult &&
      (installationResult.status === "completed" ||
        installationResult.status === "failed" ||
        installationResult.status === "uninstalled")
    ) {
      // Ensure this notification is for the current package being uninstalled
      if (installationResult.package_name !== packageToUninstall) {
        return;
      }

      const errorKey = `${installationResult.package_name}-${installationResult.status}-uninstall`;

      // Prevent duplicate notifications
      if (errorKey === lastHandledError) {
        return;
      }

      setShowProgressDialog(false);
      setIsInstallingPackage(false);
      setLastHandledError(errorKey);

      if (installationResult.status === "uninstalled") {
        setSuccessData({
          title: `Package '${installationResult.package_name}' uninstalled successfully!`,
        });
        // Refresh the installed packages list to remove the uninstalled package
        queryClient.invalidateQueries({ queryKey: ["installed-packages"] });
      } else if (installationResult.status === "completed") {
        // This shouldn't happen for uninstall operations, but handle it just in case
        setSuccessData({
          title: `Package '${installationResult.package_name}' operation completed successfully!`,
        });
        queryClient.invalidateQueries({ queryKey: ["installed-packages"] });
      } else if (installationResult.status === "failed") {
        // Extract and clean the error message
        const rawError = installationResult.message || "Unknown error";
        let cleanError = rawError;

        // For uninstallation errors, provide clean messaging
        if (
          rawError.includes("not found") ||
          rawError.includes("No such package")
        ) {
          cleanError = `Package '${installationResult.package_name}' is not installed or has already been removed.`;
        } else if (rawError.includes("×")) {
          const lines = rawError.split("\n");
          const errorLine =
            lines.find((line) => line.includes("×")) || lines[0];
          cleanError = errorLine.replace(/^\s*×\s*/, "").trim();
        }

        setErrorData({
          title: "Uninstallation Failed",
          list: [cleanError],
        });
      }
      setPackageToUninstall("");
    }
  }, [
    showProgressDialog,
    installationResult,
    packageToUninstall,
    lastHandledError,
    setErrorData,
    setSuccessData,
    setIsInstallingPackage,
    queryClient,
  ]);

  // Show error if uninstallation API call failed
  useEffect(() => {
    if (
      showProgressDialog &&
      uninstallPackageMutation.isError &&
      packageToUninstall
    ) {
      const errorKey = `${packageToUninstall}-api-error-uninstall`;

      // Prevent duplicate error handling
      if (lastHandledError === errorKey) {
        return;
      }

      setShowProgressDialog(false);
      setIsInstallingPackage(false);
      const error = uninstallPackageMutation.error as any;
      const errorMessage =
        error?.response?.data?.detail || error?.message || "Unknown error";

      setErrorData({
        title: "Uninstallation Failed",
        list: [
          errorMessage.length > 200
            ? errorMessage.substring(0, 200) + "..."
            : errorMessage,
        ],
      });
      setPackageToUninstall("");

      // Mark this as handled to prevent success notification
      setLastHandledError(errorKey);
    }
  }, [
    showProgressDialog,
    uninstallPackageMutation.isError,
    uninstallPackageMutation.error,
    setErrorData,
    setIsInstallingPackage,
    packageToUninstall,
    lastHandledError,
  ]);

  if (installedPackagesQuery.isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ForwardedIconComponent name="Package" className="h-5 w-5" />
            Installed Packages
          </CardTitle>
          <CardDescription>Loading installed packages...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center p-8">
            <ForwardedIconComponent
              name="Loader2"
              className="h-6 w-6 animate-spin"
            />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (installedPackagesQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ForwardedIconComponent name="Package" className="h-5 w-5" />
            Installed Packages
          </CardTitle>
          <CardDescription>Failed to load installed packages</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const installedPackages = installedPackagesQuery.data || [];

  // Always render the component to show the table structure

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ForwardedIconComponent name="Package" className="h-5 w-5" />
            Installed Packages
          </CardTitle>
          <CardDescription>
            Manage your installed Python packages
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Package Name</TableHead>
                <TableHead>Version</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {installedPackages.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={3}
                    className="text-center py-8 text-muted-foreground"
                  >
                    <div className="flex flex-col items-center gap-2">
                      <ForwardedIconComponent
                        name="Package"
                        className="h-8 w-8 opacity-50"
                      />
                      <p>No packages installed through the package manager</p>
                      <p className="text-sm">
                        Install packages above to see them listed here
                      </p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                installedPackages.map((pkg) => (
                  <TableRow key={pkg.name}>
                    <TableCell className="font-medium">{pkg.name}</TableCell>
                    <TableCell>{pkg.version}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleUninstallClick(pkg.name)}
                        disabled={uninstallPackageMutation.isPending}
                      >
                        <ForwardedIconComponent
                          name="Trash2"
                          className="mr-2 h-4 w-4"
                        />
                        Uninstall
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Uninstall Confirmation Dialog */}
      <Dialog open={showUninstallDialog} onOpenChange={setShowUninstallDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Package Uninstallation</DialogTitle>
            <DialogDescription>
              Are you sure you want to uninstall{" "}
              <strong>{packageToUninstall}</strong>?
              <br />
              <br />
              <strong>Warning:</strong> This action cannot be undone. If other
              packages depend on this package, they may stop working correctly.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={() => setShowUninstallDialog(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmUninstall}
              disabled={uninstallPackageMutation.isPending}
            >
              {uninstallPackageMutation.isPending ? (
                <>
                  <ForwardedIconComponent
                    name="Loader2"
                    className="mr-2 h-4 w-4 animate-spin"
                  />
                  Uninstalling...
                </>
              ) : (
                "Uninstall Package"
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Uninstallation Progress Dialog */}
      <Dialog open={showProgressDialog} onOpenChange={() => {}}>
        <DialogContent className="sm:max-w-md" closeButtonClassName="hidden">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ForwardedIconComponent name="Package" className="h-5 w-5" />
              Uninstalling Package
            </DialogTitle>
            <DialogDescription>
              Please wait while the package is being uninstalled...
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 rounded-lg bg-muted">
              <ForwardedIconComponent
                name="Loader2"
                className="h-5 w-5 animate-spin text-destructive"
              />
              <div>
                <p className="font-medium">Uninstalling {packageToUninstall}</p>
                <p className="text-sm text-muted-foreground">
                  {uninstallPackageMutation.isPending
                    ? "Uninstallation in progress..."
                    : uninstallPackageMutation.isSuccess &&
                        (!installationResult ||
                          (installationResult.status !== "completed" &&
                            installationResult.status !== "failed"))
                      ? "Checking uninstallation status..."
                      : "Waiting for uninstallation to complete..."}
                </p>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Backend Restart Dialog */}
      <BackendRestartDialog
        isOpen={showBackendRestartDialog}
        onClose={() => setShowBackendRestartDialog(false)}
        reason="Backend restarted after package uninstallation"
      />
    </>
  );
}
