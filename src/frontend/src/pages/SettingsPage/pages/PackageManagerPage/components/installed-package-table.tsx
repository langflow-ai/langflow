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
  useGetInstallationStatus,
  useGetInstalledPackages,
  useRestoreLangflow,
} from "@/controllers/API/queries/packages";
import { useBackendHealth } from "@/controllers/API/queries/packages/use-backend-health";
import useAlertStore from "@/stores/alertStore";
import { usePackageManagerStore } from "@/stores/packageManagerStore";
import { TEXTS } from "../helpers/installed-packages-table.constants";
import useCheckRestoreResult from "../hooks/use-check-restore-result";
import useClearInstalledPackages from "../hooks/use-clear-installed-packages";
import useRestoreApiError from "../hooks/use-restore-api-error";

const CHECK_RESTORE_TIMEOUT = 60000;

export default function InstalledPackagesTable() {
  const [showRestoreDialog, setShowRestoreDialog] = useState(false);
  const [showProgressDialog, setShowProgressDialog] = useState(false);
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
  const restoreLangflowMutation = useRestoreLangflow();
  const shouldPollStatus =
    showProgressDialog &&
    !lastHandledError?.includes(`restore-api-error`) &&
    !restoreLangflowMutation.isError;
  const installationStatus = useGetInstallationStatus(shouldPollStatus);

  const backendHealth = useBackendHealth(showProgressDialog, 2000);

  const handleRestoreClick = () => {
    clearTempNotificationList();
    setLastHandledError(null);
    setShowRestoreDialog(true);
  };

  const handleConfirmRestore = async () => {
    setShowRestoreDialog(false);
    setShowProgressDialog(true);
    setIsInstallingPackage(true);
    setLastHandledError(null);

    try {
      await queryClient.invalidateQueries({
        queryKey: ["installation-status"],
      });

      await restoreLangflowMutation.mutateAsync(true);

      setTimeout(() => {
        setShowBackendRestartDialog(true);
      }, 1000);
    } catch (error: any) {
      const errorMessage =
        error?.response?.data?.detail || error.message || TEXTS.UNKNOWN_ERROR;
      setErrorData({
        title: TEXTS.RESTORE_FAILED,
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

  const installationResult = installationStatus?.data?.last_result;

  useCheckRestoreResult(
    showProgressDialog,
    queryClient,
    installationResult,
    lastHandledError,
    setShowProgressDialog,
    setIsInstallingPackage,
    setSuccessData,
    setErrorData,
    setLastHandledError,
  );

  useClearInstalledPackages(
    showProgressDialog,
    backendHealth,
    queryClient,
    installationResult,
    setShowProgressDialog,
    setIsInstallingPackage,
    setSuccessData,
  );

  useRestoreApiError(
    showProgressDialog,
    restoreLangflowMutation,
    setShowProgressDialog,
    setIsInstallingPackage,
    setErrorData,
    setLastHandledError,
    lastHandledError,
  );

  useEffect(() => {
    if (!showProgressDialog) return;

    const timeoutId = setTimeout(() => {
      setShowProgressDialog(false);
      setIsInstallingPackage(false);
      setErrorData({
        title: TEXTS.RESTORE_TIMEOUT,
        list: [TEXTS.RESTORE_TIMEOUT_DESCRIPTION],
      });
    }, CHECK_RESTORE_TIMEOUT);

    return () => clearTimeout(timeoutId);
  }, [showProgressDialog, setErrorData, setIsInstallingPackage]);

  if (installedPackagesQuery.isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ForwardedIconComponent name="Package" className="h-5 w-5" />
            {TEXTS.CARD_TITLE}
          </CardTitle>
          <CardDescription>{TEXTS.LOADING_DESCRIPTION}</CardDescription>
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
            {TEXTS.CARD_TITLE}
          </CardTitle>
          <CardDescription>{TEXTS.ERROR_DESCRIPTION}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const installedPackages = installedPackagesQuery.data || [];

  return (
    <>
      {installedPackages.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ForwardedIconComponent name="Package" className="h-5 w-5" />
              {TEXTS.CARD_TITLE}
            </CardTitle>
            <CardDescription>{TEXTS.CARD_DESCRIPTION}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="mb-4 flex justify-end">
              <Button
                variant="outline"
                onClick={handleRestoreClick}
                disabled={
                  restoreLangflowMutation.isPending ||
                  installedPackages.length === 0
                }
              >
                <ForwardedIconComponent
                  name="RotateCcw"
                  className="mr-2 h-4 w-4"
                />
                {TEXTS.RESTORE_BUTTON_TEXT}
              </Button>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{TEXTS.TABLE_HEADER_PACKAGE_NAME}</TableHead>
                  <TableHead>{TEXTS.TABLE_HEADER_VERSION}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {installedPackages.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={2}
                      className="text-center py-8 text-muted-foreground"
                    >
                      <div className="flex flex-col items-center gap-2">
                        <ForwardedIconComponent
                          name="Package"
                          className="h-8 w-8 opacity-50"
                        />
                        <p>{TEXTS.EMPTY_STATE_TITLE}</p>
                        <p className="text-sm">
                          {TEXTS.EMPTY_STATE_DESCRIPTION}
                        </p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  installedPackages.map((pkg) => (
                    <TableRow key={pkg.name}>
                      <TableCell className="font-medium">{pkg.name}</TableCell>
                      <TableCell>{pkg.version}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Restore Confirmation Dialog */}
      <Dialog open={showRestoreDialog} onOpenChange={setShowRestoreDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{TEXTS.CONFIRM_RESTORE_TITLE}</DialogTitle>
            <DialogDescription>
              {TEXTS.CONFIRM_RESTORE_DESCRIPTION}
              <br />
              <br />
              <strong>{TEXTS.CONFIRM_RESTORE_WARNING}:</strong>
              <ul className="list-disc list-inside mt-2 space-y-1">
                <li>{TEXTS.CONFIRM_RESTORE_ACTION_1}</li>
                <li>{TEXTS.CONFIRM_RESTORE_ACTION_2}</li>
                <li>{TEXTS.CONFIRM_RESTORE_ACTION_3}</li>
                <li>{TEXTS.CONFIRM_RESTORE_ACTION_4}</li>
              </ul>
              <br />
              {TEXTS.CONFIRM_RESTORE_IRREVERSIBLE}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={() => setShowRestoreDialog(false)}
            >
              {TEXTS.CANCEL_BUTTON_TEXT}
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmRestore}
              disabled={restoreLangflowMutation.isPending}
            >
              {restoreLangflowMutation.isPending ? (
                <>
                  <ForwardedIconComponent
                    name="Loader2"
                    className="mr-2 h-4 w-4 animate-spin"
                  />
                  {TEXTS.RESTORING_BUTTON_TEXT}
                </>
              ) : (
                TEXTS.RESTORE_BUTTON_TEXT
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Restore Progress Dialog */}
      <Dialog open={showProgressDialog} onOpenChange={() => {}}>
        <DialogContent className="sm:max-w-md" closeButtonClassName="hidden">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ForwardedIconComponent name="RotateCcw" className="h-5 w-5" />
              {TEXTS.PROGRESS_DIALOG_TITLE}
            </DialogTitle>
            <DialogDescription>
              {TEXTS.PROGRESS_DIALOG_DESCRIPTION}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 rounded-lg bg-muted">
              <ForwardedIconComponent
                name="Loader2"
                className="h-5 w-5 animate-spin text-destructive"
              />
              <div>
                <p className="font-medium">{TEXTS.RESTORING_LANGFLOW_TEXT}</p>
                <p className="text-sm text-muted-foreground">
                  {restoreLangflowMutation.isPending
                    ? TEXTS.RESTORE_IN_PROGRESS_TEXT
                    : restoreLangflowMutation.isSuccess &&
                        (!installationResult ||
                          (installationResult.status !== "completed" &&
                            installationResult.status !== "failed"))
                      ? TEXTS.CHECKING_RESTORE_STATUS_TEXT
                      : TEXTS.WAITING_RESTORE_COMPLETION_TEXT}
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
        reason={TEXTS.BACKEND_RESTART_REASON}
      />
    </>
  );
}
