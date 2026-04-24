import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useIngestViaConnector } from "@/controllers/API/queries/knowledge-bases/use-ingest-via-connector";
import type { DeferredConnectorPayload } from "./connectorPayload";

interface OneDriveConnectorFormProps {
  kbName?: string;
  onSubmitted?: () => void;
  onPayloadChange?: (payload: DeferredConnectorPayload | null) => void;
}

/**
 * OneDrive ingestion form.
 *
 * Shares the same OAuth-variable pattern as Google Drive. Tenant
 * defaults to "common" so multi-tenant / personal accounts work
 * without extra setup; enterprise-tenant-only apps should set
 * ``MICROSOFT_OAUTH_TENANT_ID`` to their tenant id.
 */
const OneDriveConnectorForm = ({
  kbName,
  onSubmitted,
  onPayloadChange,
}: OneDriveConnectorFormProps) => {
  const [folderPath, setFolderPath] = useState("");
  const [clientIdVariable, setClientIdVariable] = useState(
    "MICROSOFT_OAUTH_CLIENT_ID",
  );
  const [clientSecretVariable, setClientSecretVariable] = useState(
    "MICROSOFT_OAUTH_CLIENT_SECRET",
  );
  const [refreshTokenVariable, setRefreshTokenVariable] = useState(
    "MICROSOFT_OAUTH_REFRESH_TOKEN",
  );
  const [tenantIdVariable, setTenantIdVariable] = useState(
    "MICROSOFT_OAUTH_TENANT_ID",
  );
  const [recursive, setRecursive] = useState(true);

  const deferred = typeof onPayloadChange === "function";

  const ingestMutation = useIngestViaConnector();
  const submitting = ingestMutation.isPending;
  const errorMessage = ingestMutation.error
    ? extractErrorDetail(ingestMutation.error)
    : null;

  const buildPayload = (): DeferredConnectorPayload => ({
    source_type: "onedrive",
    source_config: {
      folder_path: folderPath.trim() || undefined,
      recursive,
      client_id_variable: clientIdVariable.trim() || undefined,
      client_secret_variable: clientSecretVariable.trim() || undefined,
      refresh_token_variable: refreshTokenVariable.trim() || undefined,
      tenant_id_variable: tenantIdVariable.trim() || undefined,
    },
    source_name: folderPath ? `onedrive:${folderPath}` : "onedrive:root",
  });

  useEffect(() => {
    if (deferred) {
      onPayloadChange?.(buildPayload());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    deferred,
    folderPath,
    recursive,
    clientIdVariable,
    clientSecretVariable,
    refreshTokenVariable,
    tenantIdVariable,
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
      <Field label="Folder path (optional)">
        <Input
          value={folderPath}
          onChange={(e) => setFolderPath(e.target.value)}
          placeholder="/Documents/Research"
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
        <Field label="Tenant ID variable">
          <Input
            value={tenantIdVariable}
            onChange={(e) => setTenantIdVariable(e.target.value)}
            placeholder="Or 'common' for multi-tenant apps"
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
          <Button type="submit" disabled={submitting} size="sm">
            {submitting ? "Starting…" : "Ingest from OneDrive"}
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

export default OneDriveConnectorForm;
