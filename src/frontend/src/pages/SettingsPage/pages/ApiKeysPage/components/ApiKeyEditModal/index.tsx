import { isAxiosError } from "axios";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type IApiKeysDataArray,
  usePatchApiKey,
  useRegenerateApiKey,
} from "@/controllers/API/queries/api-keys";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";

type ApiKeyEditModalProps = {
  initialData: IApiKeysDataArray | null;
  open: boolean;
  setOpen: (open: boolean) => void;
  onUpdated: () => void;
  /** When set, per-key IP fields are not editable (global env restriction is active). */
  envIpRestrictionEnabled: boolean;
};

/** Match backend `ApiKeyRead.mask_api_key` (first 8 chars, then asterisks). */
function maskApiKeyLikeTable(plaintext: string): string {
  if (plaintext.length <= 8) {
    return plaintext;
  }
  return `${plaintext.slice(0, 8)}${"*".repeat(plaintext.length - 8)}`;
}

export default function ApiKeyEditModal({
  initialData,
  open,
  setOpen,
  onUpdated,
  envIpRestrictionEnabled,
}: ApiKeyEditModalProps) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [allowedIps, setAllowedIps] = useState("");
  const { mutate, isPending } = usePatchApiKey();
  const { mutate: regenerate, isPending: isRegenerating } =
    useRegenerateApiKey();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const [regeneratedFullKey, setRegeneratedFullKey] = useState<string | null>(
    null,
  );
  const [regeneratedMaskedKey, setRegeneratedMaskedKey] = useState<
    string | null
  >(null);
  const [copyIconIsReady, setCopyIconIsReady] = useState(true);
  const regenerateInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (initialData && open) {
      setName(
        initialData.name != null && initialData.name !== ""
          ? initialData.name
          : "",
      );
      setAllowedIps(initialData.allowed_ips ?? "");
    }
  }, [initialData, open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setRegeneratedFullKey(null);
    setRegeneratedMaskedKey(null);
    setCopyIconIsReady(true);
  }, [open, initialData?.id]);

  function handleRegenerate() {
    if (!initialData) {
      return;
    }
    regenerate(
      { keyId: initialData.id },
      {
        onSuccess: (data) => {
          setRegeneratedFullKey(data.api_key);
          setRegeneratedMaskedKey(null);
          setCopyIconIsReady(true);
          setSuccessData({ title: t("settings.apiKeyRegenerateSuccess") });
          onUpdated();
        },
        onError: (error: unknown) => {
          setErrorData({
            title: t("settings.apiKeyRegenerateError"),
            list: [formatPatchError(error)],
          });
        },
      },
    );
  }

  async function handleCopyRegeneratedKey() {
    if (!regeneratedFullKey) {
      return;
    }
    await navigator.clipboard.writeText(regeneratedFullKey);
    regenerateInputRef.current?.focus();
    regenerateInputRef.current?.select();
    setSuccessData({
      title: t("alerts.apiKeyCopied"),
    });
    setRegeneratedMaskedKey(maskApiKeyLikeTable(regeneratedFullKey));
    setRegeneratedFullKey(null);
    setCopyIconIsReady(false);
    setTimeout(() => {
      setCopyIconIsReady(true);
    }, 3000);
  }

  function handleSubmit() {
    if (!initialData) {
      return;
    }
    const namePayload = name.trim() || null;
    const allowedPayload = allowedIps.trim() || null;
    if (envIpRestrictionEnabled) {
      mutate(
        { keyId: initialData.id, name: namePayload },
        {
          onSuccess: () => {
            setOpen(false);
            setSuccessData({ title: t("settings.apiKeyEditSuccess") });
            onUpdated();
          },
          onError: (error: unknown) => {
            setErrorData({
              title: t("settings.apiKeyEditError"),
              list: [formatPatchError(error)],
            });
          },
        },
      );
    } else {
      mutate(
        {
          keyId: initialData.id,
          name: namePayload,
          allowed_ips: allowedPayload,
        },
        {
          onSuccess: () => {
            setOpen(false);
            setSuccessData({ title: t("settings.apiKeyEditSuccess") });
            onUpdated();
          },
          onError: (error: unknown) => {
            setErrorData({
              title: t("settings.apiKeyEditError"),
              list: [formatPatchError(error)],
            });
          },
        },
      );
    }
  }

  if (!initialData) {
    return null;
  }

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="x-small"
      onSubmit={handleSubmit}
    >
      <BaseModal.Header description={t("settings.apiKeyEditDescription")}>
        <ForwardedIconComponent
          name="Key"
          className="h-6 w-6 pr-1 text-primary"
          aria-hidden="true"
        />
        {t("settings.apiKeyEditTitle")}
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex h-full w-full flex-col gap-4">
          <div className="space-y-2">
            <Label htmlFor="api-key-edit-name">
              {t("settings.apiKeyEditNameLabel")}
            </Label>
            <Input
              id="api-key-edit-name"
              data-testid="api-key-edit-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("settings.apiKeyEditNamePlaceholder")}
            />
          </div>
          {envIpRestrictionEnabled ? (
            <p
              className="text-sm text-muted-foreground"
              data-testid="api-key-edit-ip-restriction-env-notice"
            >
              {t("settings.apiKeyEditEnvNotice")}
            </p>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="api-key-edit-allowed-ips">
                {t("settings.apiKeyEditIpLabel")}
              </Label>
              <p className="text-xs text-muted-foreground">
                {t("settings.apiKeyEditIpHelp")}
              </p>
              <Textarea
                id="api-key-edit-allowed-ips"
                data-testid="api-key-edit-allowed-ips"
                value={allowedIps}
                onChange={(e) => setAllowedIps(e.target.value)}
                placeholder={t("settings.apiKeyEditIpPlaceholder")}
                className="min-h-[5rem] font-mono text-sm"
              />
            </div>
          )}

          <div
            className="space-y-2 rounded-md border border-border p-3"
            data-testid="api-key-regenerate-section"
          >
            <Label htmlFor="api-key-regenerate-value">
              {t("settings.apiKeyRegenerateLabel")}
            </Label>
            <p className="text-xs text-muted-foreground">
              {t("settings.apiKeyRegenerateDescription")}
            </p>
            {regeneratedFullKey == null && regeneratedMaskedKey == null && (
              <Button
                type="button"
                variant="outline"
                onClick={handleRegenerate}
                disabled={isRegenerating}
                data-testid="api-key-regenerate-button"
                className="w-full sm:w-auto"
              >
                {isRegenerating && (
                  <ForwardedIconComponent
                    name="Loader2"
                    className="mr-2 h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                )}
                {t("settings.apiKeyRegenerateButton")}
              </Button>
            )}
            {regeneratedFullKey != null && (
              <div className="flex items-center gap-2">
                <Input
                  id="api-key-regenerate-value"
                  ref={regenerateInputRef}
                  readOnly
                  value={regeneratedFullKey}
                  className="font-mono text-sm"
                  data-testid="api-key-regenerate-plaintext"
                />
                <Button
                  type="button"
                  onClick={(e) => {
                    void handleCopyRegeneratedKey();
                    e.stopPropagation();
                  }}
                  unstyled
                  data-testid="api-key-regenerate-copy"
                >
                  {copyIconIsReady ? (
                    <ForwardedIconComponent
                      name="Copy"
                      className="h-4 w-4"
                      aria-hidden="true"
                    />
                  ) : (
                    <ForwardedIconComponent
                      name="Check"
                      className="h-4 w-4"
                      aria-hidden="true"
                    />
                  )}
                </Button>
              </div>
            )}
            {regeneratedMaskedKey != null && (
              <Input
                id="api-key-regenerate-value-masked"
                readOnly
                value={regeneratedMaskedKey}
                className="font-mono text-sm"
                data-testid="api-key-regenerate-masked"
              />
            )}
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: t("settings.apiKeyEditUpdate"),
          dataTestId: "api-key-edit-save",
          disabled: isPending,
          loading: isPending,
        }}
      />
    </BaseModal>
  );
}

function formatPatchError(error: unknown): string {
  if (isAxiosError(error) && error.response?.data) {
    const data = error.response.data;
    if (typeof data === "object" && data !== null && "detail" in data) {
      const d = (data as { detail: unknown }).detail;
      if (Array.isArray(d)) {
        return d.map(String).join(", ");
      }
      if (typeof d === "string") {
        return d;
      }
      return String(d);
    }
  }
  return "Unknown error";
}
