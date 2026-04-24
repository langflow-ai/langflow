import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useIngestViaConnector } from "@/controllers/API/queries/knowledge-bases/use-ingest-via-connector";
import type { DeferredConnectorPayload } from "./connectorPayload";

interface GoogleDriveConnectorFormProps {
  kbName?: string;
  onSubmitted?: () => void;
  onPayloadChange?: (payload: DeferredConnectorPayload | null) => void;
}

/**
 * Google Drive ingestion form.
 *
 * Credentials are referenced by *variable name* - the three required
 * Langflow variables (client id, client secret, refresh token) need
 * to be configured in provider settings before this form will
 * succeed. A 400 from the backend surfaces inline when any is
 * missing.
 */
const GoogleDriveConnectorForm = ({
  kbName,
  onSubmitted,
  onPayloadChange,
}: GoogleDriveConnectorFormProps) => {
  const [folderId, setFolderId] = useState("");
  const [clientIdVariable, setClientIdVariable] = useState(
    "GOOGLE_OAUTH_CLIENT_ID",
  );
  const [clientSecretVariable, setClientSecretVariable] = useState(
    "GOOGLE_OAUTH_CLIENT_SECRET",
  );
  const [refreshTokenVariable, setRefreshTokenVariable] = useState(
    "GOOGLE_OAUTH_REFRESH_TOKEN",
  );
  const [recursive, setRecursive] = useState(true);

  const deferred = typeof onPayloadChange === "function";

  const ingestMutation = useIngestViaConnector();
  const submitting = ingestMutation.isPending;
  const errorMessage = ingestMutation.error
    ? extractErrorDetail(ingestMutation.error)
    : null;
  const canSubmit = !submitting;

  const buildPayload = (): DeferredConnectorPayload => ({
    source_type: "google_drive",
    source_config: {
      folder_id: folderId.trim() || undefined,
      recursive,
      client_id_variable: clientIdVariable.trim() || undefined,
      client_secret_variable: clientSecretVariable.trim() || undefined,
      refresh_token_variable: refreshTokenVariable.trim() || undefined,
    },
    source_name: folderId ? `gdrive:${folderId}` : "gdrive:root",
  });

  useEffect(() => {
    if (deferred) {
      onPayloadChange?.(buildPayload());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    deferred,
    folderId,
    recursive,
    clientIdVariable,
    clientSecretVariable,
    refreshTokenVariable,
  ]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!kbName) return;
    ingestMutation.mutate(
      { kb_name: kbName, ...buildPayload() },
      { onSuccess: () => onSubmitted?.() },
    );
  };

  return (
    <form
      onSubmit={deferred ? (e) => e.preventDefault() : handleSubmit}
      className="flex flex-col gap-3"
    >
      <Field label="Folder ID (optional)">
        <Input
          value={folderId}
          onChange={(e) => setFolderId(e.target.value)}
          placeholder="Leave blank to walk all accessible files"
        />
      </Field>
      <label className="flex items-center gap-2 text-xs font-medium">
        <input
          type="checkbox"
          checked={recursive}
          onChange={(e) => setRecursive(e.target.checked)}
        />
        Recurse into subfolders
      </label>
      <div className="grid grid-cols-1 gap-2">
        <Field label="Client ID variable">
          <Input
            value={clientIdVariable}
            onChange={(e) => setClientIdVariable(e.target.value)}
          />
        </Field>
        <Field label="Client Secret variable">
          <Input
            value={clientSecretVariable}
            onChange={(e) => setClientSecretVariable(e.target.value)}
          />
        </Field>
        <Field label="Refresh Token variable">
          <Input
            value={refreshTokenVariable}
            onChange={(e) => setRefreshTokenVariable(e.target.value)}
          />
        </Field>
      </div>

      {!deferred && errorMessage && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
          {errorMessage}
        </div>
      )}

      {!deferred && (
        <div className="flex justify-end">
          <Button type="submit" disabled={!canSubmit} size="sm">
            {submitting ? "Starting…" : "Ingest from Google Drive"}
          </Button>
        </div>
      )}
    </form>
  );
};

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function extractErrorDetail(error: Error): string {
  const response = (error as { response?: { data?: { detail?: unknown } } })
    ?.response;
  const detail = response?.data?.detail;
  if (typeof detail === "string") return detail;
  return error.message || "Ingestion failed.";
}

export default GoogleDriveConnectorForm;
