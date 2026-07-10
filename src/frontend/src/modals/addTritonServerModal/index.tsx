import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { usePatchTritonServer } from "@/controllers/API/queries/triton/use-patch-triton-server";
import { usePostTritonServer } from "@/controllers/API/queries/triton/use-post-triton-server";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import type { TritonServerType } from "@/types/triton";

type AddTritonServerModalProps = {
  open?: boolean;
  setOpen?: (open: boolean) => void;
  initialData?: TritonServerType;
  onSuccess?: () => void;
};

export default function AddTritonServerModal({
  open,
  setOpen,
  initialData,
  onSuccess,
}: AddTritonServerModalProps): JSX.Element {
  const { t } = useTranslation();
  const isEdit = Boolean(initialData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutateAsync: addServer, isPending: isAddPending } =
    usePostTritonServer();
  const { mutateAsync: patchServer, isPending: isPatchPending } =
    usePatchTritonServer();

  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [authToken, setAuthToken] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (open) {
      setName(initialData?.name ?? "");
      setBaseUrl(initialData?.base_url ?? "");
      setAuthToken("");
      setNotes(initialData?.notes ?? "");
    }
  }, [open, initialData]);

  const isPending = isAddPending || isPatchPending;
  const canSubmit =
    name.trim().length > 0 && baseUrl.trim().length > 0 && !isPending;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    try {
      if (isEdit && initialData) {
        const payload: Record<string, string | null> = {
          name: name.trim(),
          base_url: baseUrl.trim(),
        };
        if (notes.trim() !== (initialData.notes ?? "")) {
          payload.notes = notes.trim() === "" ? null : notes.trim();
        }
        // Only send auth_token when the user typed a new value.
        // Empty string in PATCH means "clear"; blank+untouched means "keep".
        if (authToken.trim() !== "") {
          payload.auth_token = authToken.trim();
        }
        await patchServer({ server_id: initialData.id, payload });
      } else {
        await addServer({
          name: name.trim(),
          base_url: baseUrl.trim(),
          auth_token: authToken.trim() === "" ? null : authToken.trim(),
          notes: notes.trim() === "" ? null : notes.trim(),
        });
      }
      setSuccessData({ title: t("triton.servers.savedSuccess") });
      setOpen?.(false);
      onSuccess?.();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrorData({
        title: isEdit
          ? t("triton.servers.errorUpdating")
          : t("triton.servers.errorAdding"),
        list: [msg],
      });
    }
  };

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="medium"
      onSubmit={handleSubmit}
    >
      <BaseModal.Header
        description={
          isEdit ? t("triton.modal.editTitle") : t("triton.modal.addTitle")
        }
      >
        <span className="pr-2">
          {isEdit ? t("triton.modal.editTitle") : t("triton.modal.addTitle")}
        </span>
        <ForwardedIconComponent
          name="Nvidia"
          className="h-5 w-5 text-primary"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-4 px-1 pb-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="triton-name">{t("triton.modal.nameLabel")}</Label>
            <Input
              id="triton-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("triton.modal.namePlaceholder")}
              data-testid="triton-server-name-input"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="triton-url">{t("triton.modal.urlLabel")}</Label>
            <Input
              id="triton-url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={t("triton.modal.urlPlaceholder")}
              data-testid="triton-server-url-input"
            />
            <span className="text-xs text-muted-foreground">
              {t("triton.modal.urlHelp")}
            </span>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="triton-token">{t("triton.modal.tokenLabel")}</Label>
            <Input
              id="triton-token"
              type="password"
              value={authToken}
              onChange={(e) => setAuthToken(e.target.value)}
              placeholder={
                isEdit
                  ? t("triton.modal.tokenKeepBlank")
                  : t("triton.modal.tokenPlaceholder")
              }
              data-testid="triton-server-token-input"
            />
            <span className="text-xs text-muted-foreground">
              {t("triton.modal.tokenHelp")}
            </span>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="triton-notes">{t("triton.modal.notesLabel")}</Label>
            <Textarea
              id="triton-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t("triton.modal.notesPlaceholder")}
              rows={3}
              data-testid="triton-server-notes-input"
            />
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: isEdit ? t("modal.saveButton") : t("modal.addButton"),
          loading: isPending,
          disabled: !canSubmit,
          onClick: handleSubmit,
          dataTestId: "triton-server-save-btn",
        }}
      />
    </BaseModal>
  );
}
