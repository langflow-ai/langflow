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
  useGetInstallationStatus,
  useInstallPackage,
} from "@/controllers/API/queries/packages";
import { useBackendHealth } from "@/controllers/API/queries/packages/use-backend-health";
import useAlertStore from "@/stores/alertStore";
import { usePackageManagerStore } from "@/stores/packageManagerStore";
import InstalledPackagesTable from "./components/installed-package-table";
import { TEXTS } from "./helpers/constants";
import useBackendRestarting from "./hooks/use-backend-restarting";
import useCheckInstallationResult from "./hooks/use-check-installation-result";

const POLLING_INTERVAL = 5000;

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
  const isBackendRestarting = usePackageManagerStore(
    (state) => state.isBackendRestarting,
  );
  const setIsBackendRestarting = usePackageManagerStore(
    (state) => state.setIsBackendRestarting,
  );
  const restartDetectedAt = usePackageManagerStore(
    (state) => state.restartDetectedAt,
  );
  const setRestartDetectedAt = usePackageManagerStore(
    (state) => state.setRestartDetectedAt,
  );

  const queryClient = useQueryClient();
  const installPackageMutation = useInstallPackage();
  const installationStatus = useGetInstallationStatus(showProgressDialog);

  const backendHealth = useBackendHealth(showProgressDialog, POLLING_INTERVAL);

  const handleInstallClick = () => {
    if (!packageName.trim()) {
      setErrorData({ title: TEXTS.PACKAGE_NAME_REQUIRED });
      return;
    }
    clearTempNotificationList();
    setLastHandledError(null);
    installPackageMutation.reset();
    setShowInstallDialog(true);
  };

  const handleConfirmInstall = async () => {
    setShowInstallDialog(false);
    setShowProgressDialog(true);
    setIsInstallingPackage(true);
    setLastHandledError(null);

    try {
      await queryClient.invalidateQueries({
        queryKey: ["installation-status"],
      });

      await installPackageMutation.mutateAsync(packageName.trim());
    } catch (error: any) {
      const errorMessage =
        error?.response?.data?.detail || error.message || TEXTS.UNKNOWN_ERROR;
      setErrorData({
        title: TEXTS.INSTALLATION_FAILED,
        list: [
          errorMessage.length > 200
            ? errorMessage.substring(0, 200) + "..."
            : errorMessage,
        ],
      });
      setShowProgressDialog(false);
      setIsInstallingPackage(false);
      setPackageName("");
    }
  };

  const installationResult = installationStatus.data?.last_result;

  useCheckInstallationResult(
    showProgressDialog,
    queryClient,
    installationResult,
    packageName,
    lastHandledError,
    setSuccessData,
    setErrorData,
    setShowProgressDialog,
    setIsInstallingPackage,
    setPackageName,
    setLastHandledError,
  );

  useBackendRestarting(
    showProgressDialog,
    setIsBackendRestarting,
    setRestartDetectedAt,
    backendHealth,
    isBackendRestarting,
    restartDetectedAt,
    queryClient,
  );

  const renderVersionOperatorsText = () => {
    return (
      <>
        {TEXTS.VERSION_OPERATORS_TEXT}{" "}
        {TEXTS.VERSION_OPERATORS_LIST.map((item, index) => (
          <span key={item.operator}>
            <code>{item.operator}</code> ({item.description})
            {index < TEXTS.VERSION_OPERATORS_LIST.length - 1 && ", "}
          </span>
        ))}
      </>
    );
  };

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">{TEXTS.PAGE_TITLE}</h1>
        <p className="text-muted-foreground">{TEXTS.PAGE_DESCRIPTION}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ForwardedIconComponent name="Package" className="h-5 w-5" />
            {TEXTS.INSTALL_PACKAGE_TITLE}
          </CardTitle>
          <CardDescription>{TEXTS.INSTALL_PACKAGE_DESCRIPTION}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-3">
            <Input
              placeholder={TEXTS.PACKAGE_INPUT_PLACEHOLDER}
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
                  {TEXTS.INSTALLING_BUTTON_TEXT}
                </>
              ) : (
                TEXTS.INSTALL_BUTTON_TEXT
              )}
            </Button>
          </div>

          <p className="text-sm text-muted-foreground">
            {renderVersionOperatorsText()}
          </p>

          <Alert>
            <ForwardedIconComponent name="Info" className="h-4 w-4" />
            <AlertDescription>
              <strong>Note:</strong> {TEXTS.NOTE_ALERT_TEXT}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      <InstalledPackagesTable />

      <Dialog open={showInstallDialog} onOpenChange={setShowInstallDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{TEXTS.CONFIRM_INSTALL_TITLE}</DialogTitle>
            <DialogDescription>
              {TEXTS.CONFIRM_INSTALL_DESCRIPTION} <strong>{packageName}</strong>
              ?
              <br />
              <br />
              {TEXTS.CONFIRM_INSTALL_ACTIONS}
              <ul className="list-disc list-inside mt-2 space-y-1">
                <li>{TEXTS.CONFIRM_INSTALL_ACTION_1}</li>
                <li>{TEXTS.CONFIRM_INSTALL_ACTION_2}</li>
                <li>{TEXTS.CONFIRM_INSTALL_ACTION_3}</li>
              </ul>
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={() => setShowInstallDialog(false)}
            >
              {TEXTS.CANCEL_BUTTON_TEXT}
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
                  {TEXTS.INSTALLING_BUTTON_TEXT}
                </>
              ) : (
                TEXTS.INSTALL_BUTTON_TEXT
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
                className="h-5 w-5 animate-spin text-primary"
              />
              <div>
                <p className="font-medium">
                  {TEXTS.INSTALLING_PACKAGE_TEXT} {packageName}
                </p>
                <p className="text-sm text-muted-foreground">
                  {isBackendRestarting
                    ? TEXTS.BACKEND_RESTARTING_TEXT
                    : installPackageMutation.isPending
                      ? TEXTS.INSTALLATION_IN_PROGRESS_TEXT
                      : installPackageMutation.isSuccess &&
                          (!installationResult ||
                            (installationResult.status !== "completed" &&
                              installationResult.status !== "failed"))
                        ? TEXTS.CHECKING_STATUS_TEXT
                        : TEXTS.WAITING_COMPLETION_TEXT}
                </p>
              </div>
            </div>

            <Alert>
              <ForwardedIconComponent name="Info" className="h-4 w-4" />
              <AlertDescription>
                {isBackendRestarting
                  ? TEXTS.BACKEND_RESTART_ALERT_TEXT
                  : TEXTS.INSTALLATION_WAIT_ALERT_TEXT}
              </AlertDescription>
            </Alert>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
