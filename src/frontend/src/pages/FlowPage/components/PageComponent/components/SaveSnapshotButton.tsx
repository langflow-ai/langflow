import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useSidebar } from "@/components/ui/sidebar";
import { usePostCreateSnapshot } from "@/controllers/API/queries/flow-version";
import useAlertStore from "@/stores/alertStore";
import CanvasBanner, { CanvasBannerButton } from "./CanvasBanner";
import SaveVersionDialog from "./SaveVersionDialog";

interface SaveSnapshotButtonProps {
  flowId: string;
}

export default function SaveSnapshotButton({
  flowId,
}: SaveSnapshotButtonProps) {
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { setActiveSection, open, toggleSidebar } = useSidebar();
  const { mutate: createSnapshot, isPending: isCreating } =
    usePostCreateSnapshot();
  const [isSavingDisplay, setIsSavingDisplay] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const isBusy = isSavingDisplay || isCreating;

  const handleDismiss = () => {
    setShowModal(false);
    // Switching the section unmounts the version sidebar, whose cleanup
    // handles clearPreview, restoring auto-save, and restoring the
    // inspection panel.
    setActiveSection("components");
    if (!open) toggleSidebar();
  };

  const handleSave = (description: string | null) => {
    setShowModal(false);
    setIsSavingDisplay(true);
    createSnapshot(
      { flowId, description },
      {
        onSuccess: () => {
          setSuccessData({ title: t("success.versionSaved") });
          setIsSavingDisplay(false);
          setSavedSuccess(true);
        },
        onError: (err: unknown) => {
          const detail = (err as { response?: { data?: { detail?: string } } })
            ?.response?.data?.detail;
          setErrorData({
            title: t("errors.failedToSaveVersion"),
            ...(detail ? { list: [detail] } : {}),
          });
          setIsSavingDisplay(false);
        },
      },
    );
  };

  const renderSaveButtonContent = () => {
    if (isBusy) {
      return (
        <>
          <ForwardedIconComponent
            name="Loader2"
            className="h-3.5 w-3.5 animate-spin"
          />
          {t("flowVersion.saving")}
        </>
      );
    }
    if (savedSuccess) {
      return (
        <>
          <ForwardedIconComponent name="Check" className="h-3.5 w-3.5" />
          {t("flowVersion.saved")}
        </>
      );
    }
    return t("nodeToolbar.save");
  };

  return (
    <>
      <CanvasBanner
        icon="BookMarked"
        title={t("flow.saveVersion")}
        description={t("flowVersion.captureStateDescription")}
        actionSlot={
          <div className="flex items-center gap-2">
            <CanvasBannerButton variant="outline" onClick={handleDismiss}>
              {t("flowVersion.keepBuilding")}
            </CanvasBannerButton>
            <CanvasBannerButton
              onClick={() => setShowModal(true)}
              disabled={isBusy || savedSuccess}
            >
              {renderSaveButtonContent()}
            </CanvasBannerButton>
          </div>
        }
      />

      <SaveVersionDialog
        open={showModal}
        onOpenChange={setShowModal}
        onSave={handleSave}
      />
    </>
  );
}
